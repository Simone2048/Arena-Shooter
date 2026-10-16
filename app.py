"""Server-authoritative little browser party shooter."""

import asyncio
import math
import os
import random
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse


WIDTH, HEIGHT = 960, 600
TICK = 1 / 30
PLAYER_SPEED = 250.0
BULLET_SPEED = 650.0
PALETTE = ["#ff6b6b", "#53d6c3", "#ffd166", "#7c9cff", "#ff8ac8", "#b4e66e", "#c49bff", "#ff9966", "#64c8ff", "#f1f16b", "#ff577f", "#8be0a0"]
OBSTACLES = [
    (170, 145, 138, 54), (356, 90, 55, 128), (430, 205, 100, 58),
    (592, 94, 112, 55), (745, 174, 58, 122), (115, 337, 95, 60),
    (302, 391, 126, 54), (508, 326, 66, 138), (637, 411, 136, 53),
    (825, 347, 82, 61),
]

rooms = {}


def safe_name(value):
    cleaned = re.sub(r"[^\w -]", "", str(value), flags=re.UNICODE).strip()
    return cleaned[:14] or "Player"


def safe_room(value):
    cleaned = re.sub(r"[^a-zA-Z0-9-]", "", str(value)).lower()[:16]
    return cleaned or "party"


def blocked(x, y, radius=15):
    if x < radius or x > WIDTH - radius or y < radius or y > HEIGHT - radius:
        return True
    for ox, oy, ow, oh in OBSTACLES:
        near_x = max(ox, min(x, ox + ow))
        near_y = max(oy, min(y, oy + oh))
        if (x - near_x) ** 2 + (y - near_y) ** 2 < radius ** 2:
            return True
    return False


def random_spawn():
    for _ in range(100):
        x, y = random.randint(45, WIDTH - 45), random.randint(45, HEIGHT - 45)
        if not blocked(x, y):
            return x, y
    return WIDTH / 2, HEIGHT / 2


def room_for(code):
    now = time.monotonic()
    return rooms.setdefault(code, {"players": {}, "bullets": [], "powerups": [], "feed": [],
                                   "winner": None, "round_reset": 0.0,
                                   "next_powerup": now + random.uniform(3.0, 6.0), "created": now})


async def simulation():
    last = time.monotonic()
    while True:
        await asyncio.sleep(TICK)
        now = time.monotonic()
        dt = min(now - last, 0.05)
        last = now
        for code, room in list(rooms.items()):
            players = room["players"]
            if not players:
                del rooms[code]
                continue
            if room["winner"]:
                if now >= room["round_reset"]:
                    for player in players.values():
                        player["score"] = 0
                        player["hp"] = 3
                        player["x"], player["y"] = random_spawn()
                        player["upgrade"] = ""
                        player["upgrade_until"] = 0.0
                        player["shield_until"] = 0.0
                    room["bullets"].clear()
                    room["powerups"].clear()
                    room["feed"] = ["New round — first to 10 bonks!"]
                    room["winner"] = None
                    room["next_powerup"] = now + random.uniform(3.0, 6.0)
                else:
                    await broadcast(room, code, now)
                    continue
            if len(room["powerups"]) < 2 and now >= room["next_powerup"]:
                x, y = random_spawn()
                kind = random.choice(("speed", "rapid", "shield"))
                room["powerups"].append({"x": x, "y": y, "kind": kind})
                room["next_powerup"] = now + random.uniform(7.0, 11.0)
            for player in list(players.values()):
                if player["hp"] <= 0:
                    if now >= player["respawn"]:
                        player["x"], player["y"] = random_spawn()
                        player["hp"] = 3
                        player["invulnerable"] = now + 1.2
                    continue
                if now >= player["upgrade_until"]:
                    player["upgrade"] = ""
                    player["speed"] = PLAYER_SPEED
                    player["fire_interval"] = 0.22
                mx, my = player["move_x"], player["move_y"]
                length = math.hypot(mx, my)
                if length > 1:
                    mx, my = mx / length, my / length
                nx = player["x"] + mx * player["speed"] * dt
                ny = player["y"] + my * player["speed"] * dt
                if not blocked(nx, player["y"]):
                    player["x"] = nx
                if not blocked(player["x"], ny):
                    player["y"] = ny
                if player["shoot"] and now >= player["cooldown"]:
                    dx, dy = player["aim_x"] - player["x"], player["aim_y"] - player["y"]
                    aim_length = math.hypot(dx, dy) or 1
                    dx, dy = dx / aim_length, dy / aim_length
                    room["bullets"].append({"x": player["x"] + dx * 21, "y": player["y"] + dy * 21,
                                            "vx": dx * BULLET_SPEED, "vy": dy * BULLET_SPEED,
                                            "owner": player["id"], "life": 1.25, "color": player["color"]})
                    player["cooldown"] = now + player["fire_interval"]

            for powerup in list(room["powerups"]):
                for player in players.values():
                    if player["hp"] > 0 and (player["x"] - powerup["x"]) ** 2 + (player["y"] - powerup["y"]) ** 2 < 30 ** 2:
                        kind = powerup["kind"]
                        player["upgrade"] = kind
                        player["upgrade_until"] = now + 8.0
                        player["speed"] = PLAYER_SPEED * (1.45 if kind == "speed" else 1.0)
                        player["fire_interval"] = 0.11 if kind == "rapid" else 0.22
                        player["shield_until"] = now + 8.0 if kind == "shield" else 0.0
                        room["feed"].insert(0, f"{player['name']} grabbed {kind.upper()}!")
                        room["feed"] = room["feed"][:3]
                        room["powerups"].remove(powerup)
                        break

            survivors = []
            for bullet in room["bullets"]:
                bullet["x"] += bullet["vx"] * dt
                bullet["y"] += bullet["vy"] * dt
                bullet["life"] -= dt
                if bullet["life"] <= 0 or blocked(bullet["x"], bullet["y"], 5):
                    continue
                hit = False
                for target in list(players.values()):
                    if target["id"] == bullet["owner"] or target["hp"] <= 0 or now < target["invulnerable"]:
                        continue
                    if (target["x"] - bullet["x"]) ** 2 + (target["y"] - bullet["y"]) ** 2 < 22 ** 2:
                        hit = True
                        if now < target["shield_until"]:
                            room["feed"].insert(0, f"{target['name']}'s shield blocked it!")
                            room["feed"] = room["feed"][:3]
                        else:
                            target["hp"] -= 1
                        if target["hp"] <= 0:
                            target["respawn"] = now + 1.5
                            shooter = players.get(bullet["owner"])
                            if shooter:
                                shooter["score"] += 1
                                room["feed"].insert(0, f"{shooter['name']} bonked {target['name']}!")
                                room["feed"] = room["feed"][:3]
                                if shooter["score"] >= 10:
                                    room["winner"] = shooter["name"]
                                    room["round_reset"] = now + 5.0
                        break
                if not hit:
                    survivors.append(bullet)
            room["bullets"] = survivors
            await broadcast(room, code, now)


async def broadcast(room, code, now):
    players = room["players"]
    snapshot = {"type": "state", "room": code,
                "players": [{**{k: p[k] for k in ("id", "name", "x", "y", "hp", "score", "color", "aim_x", "aim_y", "upgrade")},
                             "invulnerable": p["invulnerable"] > now,
                             "shielded": p["shield_until"] > now} for p in players.values()],
                "bullets": [{k: b[k] for k in ("x", "y", "color")} for b in room["bullets"]],
                "powerups": room["powerups"], "winner": room["winner"], "feed": room["feed"][:3]}
    for player in list(players.values()):
        try:
            await player["ws"].send_json(snapshot)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app):
    task = asyncio.create_task(simulation())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
async def health():
    return {"ok": True}


@app.websocket("/ws/{room_code}")
async def play(ws: WebSocket, room_code: str, name: str = "Player"):
    code = safe_room(room_code)
    await ws.accept()
    room = room_for(code)
    if len(room["players"]) >= 12:
        await ws.send_json({"type": "full"})
        await ws.close(code=1013)
        return
    x, y = random_spawn()
    pid = uuid.uuid4().hex[:10]
    player = {"id": pid, "ws": ws, "name": safe_name(name), "x": x, "y": y, "hp": 3,
              "score": 0, "color": PALETTE[len(room["players"]) % len(PALETTE)],
              "move_x": 0.0, "move_y": 0.0, "aim_x": x + 100, "aim_y": y,
              "shoot": False, "cooldown": 0.0, "respawn": 0.0, "invulnerable": 0.0,
              "upgrade": "", "upgrade_until": 0.0, "shield_until": 0.0,
              "speed": PLAYER_SPEED, "fire_interval": 0.22}
    room["players"][pid] = player
    try:
        await ws.send_json({"type": "welcome", "id": pid, "room": code, "name": player["name"]})
        while True:
            data = await ws.receive_json()
            player["move_x"] = max(-1.0, min(1.0, float(data.get("mx", 0))))
            player["move_y"] = max(-1.0, min(1.0, float(data.get("my", 0))))
            player["aim_x"] = max(0.0, min(WIDTH, float(data.get("ax", x))))
            player["aim_y"] = max(0.0, min(HEIGHT, float(data.get("ay", y))))
            player["shoot"] = bool(data.get("shoot", False))
    except (WebSocketDisconnect, ValueError, TypeError):
        pass
    finally:
        room["players"].pop(pid, None)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


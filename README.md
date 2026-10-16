# BONK! Blast Arena

A small online party shooter: join a room with friends, zip around a one-screen arena, and bonk each other with silly blasters. It runs in a browser, while a lightweight Python server handles movement, shots, hits, and scores. There is no complicated rigid-body physics.

## Play locally

Install Python 3, then in this folder run:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open [http://localhost:8000](http://localhost:8000). Open another tab to try multiplayer on the same computer.

## Put it online for friends

The included `render.yaml` is set up for a free Render web service. Render accepts Python WebSocket services and provides the public `onrender.com` link you can send to friends.

1. Put this project in a GitHub repository.
2. In Render, choose **New → Blueprint**, connect that repository, and deploy the detected `render.yaml`.
3. Open the service's `onrender.com` address. Make a room, then use **Copy invite** to share the room link.

Free services sleep after 15 minutes without incoming traffic. The first visit after a sleep can take about a minute to wake the game. Active rooms are held in memory, so a service restart clears the room and players can rejoin using the same link.

## Controls

- **WASD** or **arrow keys** — move
- **Mouse** — aim
- **Click** or **Space** — fire
- **3 hits** — score a bonk; players respawn automatically
- Share the room link to get everyone into the same match (up to 12 players)


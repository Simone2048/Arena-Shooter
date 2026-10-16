# BONK! Blast Arena

A quick online arena shooter for up to 12 friends. First to 10 KOs wins. Grab speed, rapid-fire, and shield upgrades.

## Controls

- **WASD / arrows** move, **mouse** aims, **click / Space** fires
- Touch screens get an on-screen D-pad and fire button; aim at the nearest rival
- Three hits knock a player out; respawns are automatic

## Run locally

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open [http://localhost:8000](http://localhost:8000).

## Deploy free on Render

The included `render.yaml` configures the service. In Render, choose **New → Blueprint**, select this GitHub repository, and deploy. Share the resulting `onrender.com` URL and room invite with friends.

Free Render services sleep after 15 minutes of inactivity. The first visit after sleep can take about a minute; server restarts clear active matches.


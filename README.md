Esports Odds Alert Bot
======================

Headless Python worker that polls DOME API for esports markets and sends Telegram alerts.

Quick start
-----------
1. Create a virtualenv and install deps:
   - `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and set values (or export env vars in your host):
   - `DOME_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Run:
   - `python app/esports_alert_bot.py`

Deploy (Heroku-style platforms)
------------------------------
This repo includes a `Procfile` with a worker entry:

```
worker: python app/esports_alert_bot.py
```

On Heroku/Render/Railway:
- Set config vars `DOME_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- Scale the worker to 1 dyno/instance.

Notes
-----
- The process runs continuously and sends alert batches every `POLL_INTERVAL_MIN` minutes (default 5).
- Dependencies: requests, python-telegram-bot (v20+), schedule.

Railway deployment
------------------

Deploy with the button, then set the env vars in the service:

```
[Deploy on Railway](https://railway.app/new?template=https://github.com/goku54477/Esports-Odds-Monitor)
```

Manual steps (if not using the button):
- Create a new project → Deploy from GitHub → select this repo
- After build, open the service → Settings → set Start Command:
  - `python app/esports_alert_bot.py`
- Add Environment Variables:
  - `DOME_API_KEY`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
- Deploy, then watch Logs for: "Starting Esports Odds Alert Bot…"


# DEPLOY — Hosting the MVP for First Testers

Pick the row that matches how much you want to set up. Everything below assumes
you can already run `make serve` locally.

| Option | Time | Who can reach it | Stays up when laptop sleeps? | Best for |
|---|---|---|---|---|
| A. Tunnel from your laptop | 2 min | Anyone with the link | No | Showing 1–10 testers today |
| B. Render (free) | 15 min | Anyone with the link | Yes | A shareable MVP that runs itself |
| C. Small VPS | 30–45 min | Anyone | Yes | More control / persistence / custom domain |

Before any option: set a real `ADMIN_TOKEN`. The default `ag-admin-dev` is for
local only — anyone who guesses it gets the operations console.

================================================================================
OPTION A — TUNNEL FROM YOUR LAPTOP (fastest, zero deploy)
================================================================================

Your app runs on your machine; a tunnel gives it a public HTTPS URL. The link
dies when you stop the tunnel or your laptop sleeps — perfect for a live demo or
a quick round of testing, not for leaving running.

STEP 1 — start the app locally (one terminal)
```bash
ADMIN_TOKEN=pick-a-strong-token make serve
# add ANTHROPIC_API_KEY in .env first if you want live (non-demo) answers
```

STEP 2 — open a tunnel (second terminal). Cloudflare's needs no account:
```bash
# macOS:  brew install cloudflared
# linux:  see https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel --url http://localhost:8000
```
It prints a public URL like `https://random-words.trycloudflare.com`.
Share that. `/` is the tester chat; `/admin` is your console.

(ngrok is the common alternative — `ngrok http 8000` — but now requires a free
account and authtoken.)

WHAT TESTERS SEE: the real app over HTTPS. Every question they ask logs to your
local `data/qa_log.jsonl` and shows up live in your `/admin` console.

================================================================================
OPTION B — RENDER (free tier, runs independently)
================================================================================

A real cloud host that stays up without your laptop. The repo already contains
`render.yaml`, so this is close to one-click.

STEP 1 — push the repo to GitHub
```bash
git remote add origin https://github.com/<you>/germany-faq-agent.git
git push -u origin main
```

STEP 2 — create the service on Render
  1. Sign in at https://render.com (free).
  2. New + → Blueprint → connect your GitHub → pick the repo.
  3. Render reads `render.yaml` and proposes the web service + a 1 GB disk.
  4. When prompted for the two secret env vars, set:
       ANTHROPIC_API_KEY  = your key   (leave blank to run in demo mode)
       ADMIN_TOKEN        = a strong token you choose
  5. Click Apply. First build takes a few minutes.

STEP 3 — open the URL Render gives you (e.g. `https://germany-faq-agent.onrender.com`)
  - `/`      → tester chat
  - `/admin` → operations console (enter your ADMIN_TOKEN)
  - `/health`→ should return `{"status":"ok",...}`

WHAT render.yaml already handles for you:
  - start command without `--reload`
  - `$PORT` injection
  - a persistent disk mounted at `/var/data`, with `QA_LOG_PATH` and
    `TRACES_DIR` pointed at it — so the question log and traces survive
    restarts and redeploys (without the disk, the free tier wipes them).

FREE-TIER CAVEAT: Render spins the service down after ~15 min idle; the next
visit takes ~30–50 s to wake. Fine for testing. Upgrade the plan to keep it warm.

REDEPLOY: `git push` — Render rebuilds automatically.

(Railway and Fly.io work the same way with the Dockerfile; Render is the least
fiddly for a Python web service with a disk.)

================================================================================
OPTION C — SMALL VPS (most control)
================================================================================

A €4–6/month box (Hetzner, DigitalOcean, Linode). You own the filesystem, so
persistence and a custom domain are straightforward. Two ways to run it:

C1 — DOCKER (simplest on a fresh box)
```bash
# on the server, with Docker installed and the repo copied/cloned:
docker build -t faq-agent .
docker run -d --name faq \
  -p 80:8000 \
  -e ADMIN_TOKEN=your-strong-token \
  -e ANTHROPIC_API_KEY=sk-ant-...   \
  -e AGENT_MODEL=claude-sonnet-4-6  \
  -v /opt/faq-data:/var/data \
  -e QA_LOG_PATH=/var/data/qa_log.jsonl \
  -e TRACES_DIR=/var/data/traces \
  --restart unless-stopped \
  faq-agent
```
The `-v /opt/faq-data:/var/data` mount keeps logs/traces on the host disk.
App is now on `http://your-server-ip/`.

C2 — BARE (no Docker)
```bash
sudo apt update && sudo apt install -y python3-venv
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ADMIN_TOKEN=your-strong-token ANTHROPIC_API_KEY=sk-ant-... \
  uvicorn api.server:app --host 0.0.0.0 --port 8000
```
For a long-running service, put that command in a systemd unit (so it restarts
on reboot) and run Caddy or nginx in front for HTTPS on a real domain.

HTTPS + DOMAIN (recommended once testers are external): point a domain at the
box and run Caddy — it gets a Let's Encrypt certificate automatically:
```
# /etc/caddy/Caddyfile
faq.yourdomain.com {
    reverse_proxy localhost:8000
}
```

================================================================================
PRE-FLIGHT CHECKLIST (any option)
================================================================================

[ ] ADMIN_TOKEN set to something strong and private (NOT ag-admin-dev)
[ ] Decide demo vs live:
      - no ANTHROPIC_API_KEY  → demo mode, deterministic placeholder answers,
        clearly flagged in the UI. Free. Good for testing flows/UX.
      - ANTHROPIC_API_KEY set  → real Claude answers. Costs ~$0.01 per question.
[ ] AGENT_MODEL = claude-sonnet-4-6  (the May-2025 string is retired)
[ ] Persistence: ensure QA_LOG_PATH + TRACES_DIR point at durable storage if you
      care about keeping tester questions (Option B disk / Option C volume).
[ ] HTTPS in front if testers are outside your network (Render/tunnel give this
      automatically; VPS needs Caddy/nginx).
[ ] Sanity check after deploy:
      curl https://<your-url>/health      → {"status":"ok",...}

================================================================================
COST WHILE TESTING
================================================================================

- Hosting: Option A free, Option B free tier, Option C ~€4–6/mo.
- Model: $0 in demo mode. In live mode, roughly $0.01 per question
  (categorize + generate). 500 tester questions ≈ a few dollars.
  Set a spend limit in the Anthropic console to cap it.

================================================================================
WHAT TO WATCH IN /admin DURING TESTING
================================================================================

Open the console while testers use the app. The signals that tell you whether
the MVP is working:

- Avg grounding < 100%      → answers citing facts not in the SOPs (FM-04).
- Needs-review count rising → low grounding, missing next step, or thumbs-down.
- Helpful rate              → the headline "is this useful" number.
- Questions by category     → what testers actually ask; gaps tell you which
                              SOPs to expand.
- Click any question        → full trace: which SOPs were retrieved and the
                              exact answer. This is how you diagnose a bad answer.

Questions that expose a weak answer should graduate into `data/test_cases.csv`
(see MANUAL.md Part 9.7) so the failure is regression-tested from then on.

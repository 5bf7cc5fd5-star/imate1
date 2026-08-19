# Own Club — Railway Deploy Guide

## What this is
Python backend (stdlib only) + member frontend + admin panel.

- Member app: `/`
- Admin panel: `/admin`
- Health: `/api/health`

**Admin login**
- Email: `k_hmed@yahoo.com`
- Password: set via `ADMIN_PASSWORD` (default `Madahketa@17`)

---

## Deploy on Railway (step by step)

### 1. Create account
Go to https://railway.app and sign up (GitHub login is easiest).

### 2. New project
1. Click **New Project**
2. Choose **Deploy from GitHub repo**  
   **OR** **Empty Project** then upload this folder.

#### Option A — GitHub (recommended)
1. Create a GitHub repo and upload all files from this folder
2. In Railway: **New Project → Deploy from GitHub repo**
3. Select the repo

#### Option B — Railway CLI
```bash
npm i -g @railway/cli
railway login
cd ownclub
railway init
railway up
```

### 3. Set environment variables
In Railway project → **Variables**:

| Variable | Value |
|----------|--------|
| `PORT` | `8080` (Railway often sets this automatically) |
| `IMATE1_SECRET` | long random string (e.g. 40+ chars) |
| `ADMIN_PASSWORD` | `Madahketa@17` (or stronger) |

### 4. Generate domain
1. Open your service → **Settings → Networking**
2. Click **Generate Domain**
3. You get a URL like `https://ownclub-production.up.railway.app`

### 5. Open the app
- **Members:** `https://YOUR-DOMAIN.up.railway.app/`
- **Admin:** `https://YOUR-DOMAIN.up.railway.app/admin`

---

## Important limits (read before taking real money)

1. **Ephemeral storage** — Railway free disk can reset on redeploy. User data may be wiped unless you attach a **Volume** at `/app/data`.
2. **Manual deposit approval** — MoMo/USDT are verified by you via Transaction ID, not automatic payment APIs yet.
3. **Demo architecture** — Suitable for pilot testing. For full production add a real database (Postgres) and payment webhooks.

### Add a volume (keep data)
1. Railway service → **Volumes**
2. Mount path: `/app/data`
3. Redeploy

---

## Local test before deploy
```bash
cd ownclub
python3 server.py
# open http://127.0.0.1:8080
```

## API health
```bash
curl https://YOUR-DOMAIN.up.railway.app/api/health
```

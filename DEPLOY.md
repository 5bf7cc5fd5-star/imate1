# Automatic Railway deploys

## Way 1 — Railway GitHub (simplest)
1. Railway service → Settings → Source
2. Connect repo `5bf7cc5fd5-star/ownclubshares.com`
3. Branch `main`
4. Turn ON **Auto deploys when pushed to GitHub**

Every GitHub upload/push rebuilds the app. No extra clicks.

## Way 2 — GitHub Action (this repo)
1. Railway → Account Settings → Tokens → Create token
2. GitHub repo → Settings → Secrets and variables → Actions
3. New secret name: `RAILWAY_TOKEN`  value: that token
4. Push to `main`

Workflow: `.github/workflows/railway-deploy.yml`

## After a deploy
- App: `/`
- System: `/admin`
- Health: `/api/health`

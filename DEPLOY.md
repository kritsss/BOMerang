# Deploying BOMerang on Render

BOMerang deploys as **one Render web service**: a single Docker container that serves the web app and the API from the same address (`https://<name>.onrender.com`). Data (the SQLite database, uploads and run results) lives on a **persistent disk** mounted at `/data`, so it survives restarts and redeploys. On a paid instance the service never sleeps.

```
browser ──► https://bomerang.onrender.com ──► one container (root Dockerfile)
                                                 ├── /api/*  FastAPI
                                                 ├── /*      built React app
                                                 └── /data   persistent disk (SQLite, uploads, runs)
```

Files involved: `Dockerfile` (repo root), `.dockerignore`, `render.yaml` (optional one-click setup). Local development is unchanged (`make dev`, `docker compose up`).

## Which plan

Measured with this app (peak memory during a full run):

| Spend lines in one project | Plan | Price |
|---|---|---|
| up to ~5,000 | **Starter**, 512 MB | $7/month |
| up to ~30,000–50,000 | **Standard**, 2 GB | $25/month |
| more | Pro, 4 GB | $85/month |

Plus the disk: 1 GB is $0.25/month. If a run is too big for the plan, the service runs out of memory and restarts (Render emails you and the event shows in **Events**). Switch the plan under **Settings → Instance Type**; your data stays.

## Option A: set it up by hand (dashboard)

1. **Push this branch** to GitHub (from your Mac):
   ```bash
   cd ~/Desktop/BOMerang
   git add -A && git commit -m "Render deployment" && git push -u origin feature/Deployment
   ```
2. In Render: **+ New → Web Service → Git Provider → GitHub**, and pick **kritsss/BOMerang** (connect GitHub first if asked).
3. Fill in the form:

   | Field | Value |
   |---|---|
   | Name | `bomerang` (your address becomes `bomerang.onrender.com`, or with a suffix if taken) |
   | Project | optional, leave as is |
   | Language | **Docker** |
   | Branch | `feature/Deployment` (or `main` after you merge) |
   | Region | **Ohio (US East)**, nearest to Chicago |
   | Root Directory | leave **empty** |
   | Instance Type | **Starter** ($7), or **Standard** ($25) for big files (see the table above) |

4. **Environment Variables** (same form, "Add Environment Variable"):

   | Key | Value |
   |---|---|
   | `ANTHROPIC_API_KEY` | your key (copy it from your local `.env`) |
   | `LLM_MODEL` | `claude-sonnet-5-5` |
   | `AI_MAX_ITEMS` | `200` |
   | `BOMERANG_DATA_DIR` | `/data` ← must be `/data`, not `./data`, or your data is lost on every deploy |
   | `BOMERANG_EMBEDDINGS` | `0` |

   Don't add `PORT`, `CORS_ORIGINS` or `API_URL`. Render sets the port itself, and the frontend and API share one address.

5. Open **Advanced** and set:

   | Field | Value |
   |---|---|
   | Health Check Path | `/api/health` |
   | Docker Build Context Directory | `.` |
   | Dockerfile Path | `./Dockerfile` |
   | Docker Command | leave empty |
   | Pre-Deploy Command | leave empty |
   | Auto-Deploy | **On Commit** |
   | Disk → **Add Disk** | Name `bomerang-data`, Mount Path **`/data`**, Size **1** GB |

6. Click **Deploy Web Service**. The first build takes about 5–8 minutes. When the log shows `Uvicorn running on http://0.0.0.0:10000` and the status turns **Live**, open the URL at the top of the page. The header should say AI suggestions are on.

## Option B: one click with the Blueprint

`render.yaml` holds the same settings. In Render: **+ New → Blueprint**, pick the repo and branch, and paste your `ANTHROPIC_API_KEY` when asked. To use Standard instead of Starter, change `plan: starter` to `plan: standard` in `render.yaml` first, or change the instance type afterwards in the dashboard.

## If you already have BOMerang services on Render

Delete the old free backend and frontend services after the new one is live (**Settings → Delete Web Service / Static Site**). They are no longer needed, and the old frontend would point at the old backend.

## Day to day

| Task | How |
|---|---|
| Deploy new code | `git push`. Render rebuilds automatically. |
| Logs | service → **Logs** |
| Change a setting | service → **Environment** → edit → **Save, rebuild, and deploy** |
| Bigger plan | service → **Settings → Instance Type** |
| Backups | Render snapshots the disk automatically every 24 hours: service → **Disks** → **Snapshots** to restore |
| Download all data | service → **Shell** (paid plans): `cd /data && tar czf /tmp/bomerang.tgz .`, or use `scp` over Render SSH |

Each deploy has a short downtime (under a minute) because a service with a disk stops the old instance before starting the new one. Keep **Instances = 1**: a disk can only be attached to one instance.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Build fails in `npm ci` or `pip install` | Open the build log; usually a lockfile or requirements change. Run `docker build .` locally to reproduce. |
| Deploy stuck in "health check failed" | Check that Health Check Path is `/api/health` and that `PORT` is **not** set by hand. |
| "AI suggestions off" | `ANTHROPIC_API_KEY` missing or wrong under **Environment**. |
| Projects disappear after a deploy | `BOMERANG_DATA_DIR` isn't `/data`, or the disk's mount path isn't `/data`. |
| Service restarts during a big run ("Out of memory" in Events) | Move up a plan (see the table above). |

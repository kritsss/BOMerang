# Deploying BOMerang (free, always on)

BOMerang runs on one small Linux server: **Caddy** serves the built web app and forwards `/api/*` to the **FastAPI** container. Data (SQLite database, uploads, run results) lives in a Docker volume, so it survives restarts, reboots and redeploys. Nothing sleeps.

The free server used here is an **Oracle Cloud "Always Free" Ampere A1 VM** (ARM, 2 OCPU, 12 GB RAM). Any Ubuntu server with Docker works the same way.

```
browser ──► :80 / :443  Caddy (web container)
                           ├── /api/*  ──► api:8000  FastAPI + SQLite  ──► volume bomerang-data
                           └── /*      ──► built React app (index.html fallback for deep links)
```

Files involved:

| File | What it is |
|---|---|
| `docker-compose.prod.yml` | Production stack: `api` (not exposed to the internet) + `web` (Caddy on 80/443). Auto-restart, health check, persistent volumes. |
| `web/Dockerfile.prod`, `web/Caddyfile` | Builds the React app and serves it with Caddy; proxies `/api`; HTTPS when you use a domain. |
| `scripts/oracle-setup.sh` | One-time server setup: Docker, firewall ports 80/443, first start. Safe to re-run. |
| `scripts/backup.sh`, `scripts/restore.sh` | Backup of all data (keeps the last 7) and restore. |

`docker-compose.yml` and `make dev` are unchanged and still for local development.

---

## 0. Before you start (on your Mac)

1. Push this branch so the server can download it:
   ```bash
   cd ~/Desktop/BOMerang
   git push -u origin feature/Deployment
   ```
   (Or merge it into `main` first and use `main` below.)
2. Make an SSH key for the server, if you don't already have one you want to use:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/oracle_bomerang -N ""
   cat ~/.ssh/oracle_bomerang.pub      # you'll paste this into Oracle in step 2
   ```

## 1. Create the Oracle Cloud account

1. Sign up at <https://www.oracle.com/cloud/free/>. A card is required for identity verification; Always Free resources are not charged.
2. Pick your **home region** carefully (it can't be changed, and Always Free compute only runs there). A less busy region makes it easier to get an ARM VM.

## 2. Create the VM

In the Oracle Cloud console: **☰ → Compute → Instances → Create instance**. (Labels can differ slightly between console versions.)

1. **Name:** `bomerang`.
2. **Image and shape → Edit:**
   - **Image:** *Canonical Ubuntu 24.04* (not "Minimal").
   - **Shape:** *Change shape → Ampere → VM.Standard.A1.Flex*, **2 OCPUs, 12 GB memory**. It should show "Always Free-eligible".
   - ⚠️ Never run more than **2 OCPU / 12 GB of A1 in total** across all your instances. If you go over when the free trial ends, Oracle disables *all* your A1 instances.
3. **Networking:** create a new virtual cloud network and public subnet (the defaults), and make sure **Assign a public IPv4 address** is on.
4. **Add SSH keys → Paste public keys:** paste the contents of `~/.ssh/oracle_bomerang.pub`.
5. **Boot volume:** the default (≈50 GB) is fine.
6. Click **Create**. When it shows **Running**, copy the **Public IP address**.

> **"Out of capacity" / "Out of host capacity"?** Free ARM capacity runs out in busy regions. Try another *Availability domain* in the same screen, try again in a few hours, or try 1 OCPU / 6 GB now and resize to 2 / 12 later.

## 3. Open ports 80 and 443 in Oracle's cloud firewall

**Instance page → the subnet link → Security Lists → Default Security List → Add Ingress Rules**, and add:

| Source CIDR | IP protocol | Destination port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |
| `0.0.0.0/0` | UDP | `443` (optional, enables HTTP/3) |

(The server has its own firewall too; the setup script opens it.)

## 4. Install and start BOMerang on the server

From your Mac (replace `<IP>` with the public IP):

```bash
ssh -i ~/.ssh/oracle_bomerang ubuntu@<IP>
```

On the server:

```bash
git clone -b feature/Deployment https://github.com/kritsss/BOMerang.git
exit
```

Back on your Mac, copy your `.env` (it holds your API key and is never in git):

```bash
scp -i ~/.ssh/oracle_bomerang ~/Desktop/BOMerang/.env ubuntu@<IP>:~/BOMerang/.env
ssh -i ~/.ssh/oracle_bomerang ubuntu@<IP>
```

On the server:

```bash
cd ~/BOMerang
bash scripts/oracle-setup.sh
```

The first build takes about 5–10 minutes. It ends with `Done. Open http://<IP>`. Open that address; the header should say AI suggestions are on (your key is working).

Then **log out and back in once** (`exit`, then `ssh` again) so you can run `docker` and `make prod-*` without `sudo`.

## 5. HTTPS with a free domain (recommended)

1. Go to <https://www.duckdns.org>, sign in, create a subdomain (e.g. `bomerang-kritika`), and set its **current ip** to your server's public IP.
2. On the server, edit `.env` (`nano ~/BOMerang/.env`) and set:
   ```
   SITE_ADDRESS=bomerang-kritika.duckdns.org
   ```
3. Apply it:
   ```bash
   cd ~/BOMerang && make prod-up
   ```
   Caddy gets and renews the certificate automatically. Open `https://bomerang-kritika.duckdns.org`.

Your own domain works the same way: point an `A` record at the IP and put the domain in `SITE_ADDRESS`.

## 6. Nightly backups

```bash
mkdir -p ~/bomerang-backups
(crontab -l 2>/dev/null; echo "17 3 * * * $HOME/BOMerang/scripts/backup.sh >> $HOME/bomerang-backups/backup.log 2>&1") | crontab -
```

This keeps the last 7 backups in `~/bomerang-backups` on the server. To keep a copy on your Mac too:

```bash
scp -i ~/.ssh/oracle_bomerang "ubuntu@<IP>:~/bomerang-backups/*.tar.gz" ~/Desktop/
```

---

## Day to day (on the server, in `~/BOMerang`)

| Task | Command |
|---|---|
| Deploy new code you pushed to GitHub | `make prod-update` |
| See logs | `make prod-logs` (Ctrl+C to stop) |
| Status / health | `docker compose -f docker-compose.prod.yml ps` |
| Restart | `docker compose -f docker-compose.prod.yml restart` |
| Change a setting in `.env` | edit, then `make prod-up` |
| Back up now | `make prod-backup` |
| Restore a backup (replaces current data) | `bash scripts/restore.sh ~/bomerang-backups/bomerang-YYYYMMDD-HHMMSS.tar.gz` |

The containers restart on their own after a crash or a server reboot.

**Keep the Oracle account active:** log in to the Oracle console every few weeks. Oracle can reclaim Always Free accounts that sit idle for long periods.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Browser can't connect at all | Check step 3 (security list rules), then re-run `bash scripts/oracle-setup.sh` (re-opens the server firewall). |
| Page loads but says the API is unreachable | `docker compose -f docker-compose.prod.yml logs api`. Usually a typo in `.env`. |
| "AI suggestions off" | `ANTHROPIC_API_KEY` missing or wrong in `~/BOMerang/.env`; fix it, then `make prod-up`. |
| HTTPS not working with a domain | The domain must point at the server IP *before* Caddy starts, and ports 80 and 443 must be open. See `make prod-logs`. |
| Disk filling up after many deploys | `docker system prune -f` (removes old images; your data volume is kept). |

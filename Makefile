.PHONY: install dev api web test e2e build prod-up prod-down prod-logs prod-update prod-backup

install:
	python3 -m pip install -r api/requirements.txt
	npm install
	cd web && npm install

dev: ## start API (8000) and web app (5173) together
	@[ -d node_modules ] || npm install
	@[ -d web/node_modules ] || (cd web && npm install)
	npm run dev

api:
	cd api && python3 -m uvicorn main:app --reload --port 8000

web:
	cd web && npm run dev

test:
	cd api && python3 -m pytest -q
	cd web && npx tsc -b && npm test

e2e: ## needs `make dev` running in another terminal and a Chromium (npx playwright install chromium)
	cd web && npx playwright test

build:
	cd web && npm run build

# ---- production (on the server; see DEPLOY.md) ----
PROD = docker compose -f docker-compose.prod.yml

prod-up: ## build and start (or update) the production stack
	$(PROD) up -d --build

prod-down:
	$(PROD) down

prod-logs:
	$(PROD) logs -f --tail=200

prod-update: ## pull the latest code and redeploy
	git pull && $(PROD) up -d --build

prod-backup:
	bash scripts/backup.sh

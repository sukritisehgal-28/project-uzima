.PHONY: install dev test smoke swarm
install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd apps/dashboard && npm install
dev:
	./scripts/dev.sh
test:
	.venv/bin/python -m pytest -q
smoke:
	.venv/bin/python scripts/smoke.py
swarm:
	.venv/bin/python scripts/run_local_swarm.py cardiac_icu

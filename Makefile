# Makefile — SRB Station de Recherche sur Balcon
# Usage : make <cible>

PYTHON    := .venv/Scripts/python
PIP       := .venv/Scripts/pip
PYTEST    := .venv/Scripts/python -m pytest
RUFF      := .venv/Scripts/ruff
MYPY      := .venv/Scripts/mypy

.PHONY: help venv install lint typecheck test audit infra-up infra-down infra-logs acquire clean

help:
	@echo "Cibles disponibles :"
	@echo "  venv        — Recrée le venv avec Python 3.12"
	@echo "  install     — Installe les dépendances dans le venv"
	@echo "  lint        — Lint ruff + formatage"
	@echo "  typecheck   — Analyse statique mypy"
	@echo "  test        — Lance les tests unitaires"
	@echo "  audit       — Audit de sécurité pip-audit"
	@echo "  infra-up    — Démarre InfluxDB via Docker"
	@echo "  infra-down  — Arrête InfluxDB"
	@echo "  infra-logs  — Logs InfluxDB en temps réel"
	@echo "  acquire     — Lance le script d'acquisition série"
	@echo "  clean       — Supprime les caches Python"

# ── Environnement ──────────────────────────────────────────────────────────

venv:
	py -3.12 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-ci.txt
	@echo "Venv Python 3.12 prêt."

install:
	$(PIP) install -r requirements.txt

# ── Qualité ────────────────────────────────────────────────────────────────

lint:
	$(RUFF) format --check src/ tests/
	$(RUFF) check src/ tests/

lint-fix:
	$(RUFF) format src/ tests/
	$(RUFF) check --fix src/ tests/

typecheck:
	$(MYPY) src/common/ src/acquisition/

test:
	$(PYTEST) tests/ -q

audit:
	$(PIP) install pip-audit --quiet
	.venv/Scripts/pip-audit -r requirements-ci.txt

# ── Infrastructure ─────────────────────────────────────────────────────────

infra-up:
	docker compose up -d
	@echo "InfluxDB disponible sur http://localhost:8086"
	@echo "  Login : admin / srb-admin-2026"

infra-down:
	docker compose down

infra-logs:
	docker compose logs -f influxdb

# ── Acquisition ────────────────────────────────────────────────────────────

acquire:
	@if [ ! -f .env ]; then echo "Erreur : fichier .env manquant. Copier .env.example en .env."; exit 1; fi
	@export $$(grep -v '^#' .env | xargs) && $(PYTHON) -m src.acquisition.serial_to_db

# ── Nettoyage ──────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cache Python nettoyé."

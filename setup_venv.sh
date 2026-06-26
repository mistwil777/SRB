#!/usr/bin/env bash
# setup_venv.sh — Recrée le venv avec Python 3.12 et installe toutes les dépendances
# Usage : bash setup_venv.sh

set -e

PYTHON="py -3.12"

echo "=== Vérification Python 3.12 ==="
$PYTHON --version

echo "=== Suppression de l'ancien venv ==="
rm -rf .venv

echo "=== Création du venv Python 3.12 ==="
$PYTHON -m venv .venv

echo "=== Mise à jour pip ==="
.venv/Scripts/python -m pip install --upgrade pip

echo "=== Installation des dépendances CI ==="
.venv/Scripts/pip install -r requirements-ci.txt

echo "=== Installation des dépendances Phase 1 (acquisition) ==="
.venv/Scripts/pip install pyserial influxdb-client PyYAML pydantic

echo "=== Vérification des tests ==="
.venv/Scripts/python -m pytest tests/ -q

echo ""
echo "✓ Venv prêt. Pour l'activer :"
echo "  source .venv/Scripts/activate  (Git Bash)"
echo "  .venv\Scripts\Activate.ps1     (PowerShell)"

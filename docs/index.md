# Documentation SRB — Station de Recherche sur Balcon

> **À qui s'adresse ce guide ?**
> À toi, dans six mois, quand tu auras oublié pourquoi on a fait tel choix.
> Et à toute personne qui rejoindrait le projet.

---

## Navigation

| Document | Contenu |
|----------|---------|
| [01 — Vue d'ensemble](./01_vue_ensemble.md) | Le projet en entier : schéma global, flux de données, philosophie |
| [02 — Hardware & Capteurs](./02_hardware.md) | Arduino, DHT22, BH1750, capteur sol — ce que chaque pièce fait physiquement |
| [03 — Acquisition & Stockage](./03_acquisition.md) | Liaison série, pyserial, JSON, InfluxDB, Docker |
| [04 — Vision par ordinateur](./04_vision.md) | OpenCV, YOLOv8-seg, ce qu'est la segmentation foliaire |
| [05 — Modélisation IA](./05_modelisation.md) | LINTUL-POTATO, Multi-Head IA, PyTorch, RAG / ChromaDB |
| [06 — Infrastructure de développement](./06_infra_dev.md) | Python, venv, Git, GitHub Actions, Makefile |

---

## Le projet en une phrase

> Mesurer automatiquement les conditions de culture d'une pomme de terre sur balcon, photographier sa croissance, et entraîner un modèle d'IA capable de prédire son rendement, sa résistance au stress et sa qualité gustative.

---

## Légende des icônes utilisées dans la doc

| Icône | Signification |
|-------|--------------|
| 🔩 | Composant physique / hardware |
| 🐍 | Code Python |
| 🗄️ | Stockage de données |
| 🤖 | Intelligence artificielle |
| 🛠️ | Outil de développement |
| ⚠️ | Point d'attention important |
| 💡 | Analogie ou explication pédagogique |

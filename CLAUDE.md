# SRB — Station de Recherche sur Balcon

## Contexte projet
Système cyber-physique (IoT + IA) pour l'étude de la croissance de la pomme de terre en milieu contraint.
Objectif : modèle hybride (physique + IA) prédisant Rendement, Résistance au stress et Qualité gustative.

## Architecture cible
- **Module A** : Acquisition IoT via Arduino Mega 2560 → InfluxDB
- **Module B** : Vision OpenCV + YOLOv8-seg → biomasse foliaire
- **Module C** : Digital Twin hybride (LINTUL-POTATO + Multi-Head IA)

## Règles de codage

### Modularité
- Chaque tête du modèle (`head_yield`, `head_stress`, `head_taste`) doit être entraînable indépendamment.
- Les imports entre modules passent par `src/common/` — pas d'import croisé entre `acquisition/`, `vision/`, `modeling/`.

### Robustesse obligatoire
- Reconnexion automatique sur les ports série (backoff exponentiel).
- Logging structuré JSON dans tous les scripts (`src/common/logger.py`).
- Toujours lire la configuration depuis `config/settings.yaml`, jamais de hardcode.

### Déséquilibre des données — règle critique
La donnée **Goût** est rare (quelques dizaines d'observations/an vs milliers pour Rendement).
- La tête `head_taste` utilise systématiquement une stratégie de **fine-tuning séquentiel** : tronc pré-entraîné sur Rendement → fine-tune sur Goût.
- Documenter dans chaque entraînement le ratio `N_taste / N_yield` pour détecter une dérive.
- Ne jamais entraîner les trois têtes conjointement sans pondération de loss (`loss_weight_taste >= 5.0`).

### Diagrammes Mermaid
- Pas de parenthèses `()` dans les labels de noeuds.
- Chaque instruction se termine par `;`.

### Stack autorisée
Python 3.12+ · pyserial · influxdb-client · ultralytics · langchain · chromadb · dask · pydantic · PyYAML
Pas de framework web inutile. Pas de pandas si numpy suffit.

## Phases de livraison
1. **Phase 1** — `src/acquisition/serial_to_db.py` (script robuste, service systemd)
2. **Phase 2** — `src/vision/image_segmenter.py` (segmentation foliaire YOLOv8-seg)
3. **Phase 3** — `src/modeling/lintul/` + `src/modeling/heads/` (Multi-Head IA)

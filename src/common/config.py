"""
Chargeur de configuration centralisé.
Usage : from src.common.config import cfg
"""
import os
from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def load_config(path: str = "config/settings.yaml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Fichier de configuration introuvable : {config_path}")
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # Injection du token InfluxDB depuis l'environnement
    env_token = os.getenv("INFLUXDB_TOKEN")
    if env_token:
        data["influxdb"]["token"] = env_token
    return data


cfg = load_config()

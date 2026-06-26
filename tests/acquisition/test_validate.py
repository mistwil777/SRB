"""
Tests unitaires pour la fonction validate() de serial_to_db.
Aucun hardware requis — tout est mocké.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Patch des modules hardware avant tout import du module cible
sys.modules.setdefault("serial", MagicMock())
sys.modules.setdefault("influxdb_client", MagicMock())
sys.modules.setdefault("influxdb_client.client", MagicMock())
sys.modules.setdefault("influxdb_client.client.write_api", MagicMock())

# Patch du chargeur de config pour éviter de lire le vrai fichier YAML
_fake_cfg = {
    "serial": {"port": "COM3", "baudrate": 9600, "timeout": 2,
               "reconnect_delay_base": 2, "reconnect_delay_max": 60},
    "influxdb": {"url": "http://localhost:8086", "token": "test",
                 "org": "SRB", "bucket": "srb_sensors"},
    "logging": {"level": "DEBUG", "dir": "logs", "max_bytes": 1024, "backup_count": 1},
    "acquisition": {"interval_seconds": 900},
}
with patch.dict("sys.modules", {"src.common.config": MagicMock(cfg=_fake_cfg)}):
    from src.acquisition.serial_to_db import validate  # noqa: E402


# ---------------------------------------------------------------------------
# Payloads de référence
# ---------------------------------------------------------------------------

VALID_PAYLOAD = {
    "ts": 1_700_000_000,
    "soil_moisture": 45.0,
    "temp_air": 22.5,
    "humidity_air": 60.0,
    "lux": 15000.0,
}


# ---------------------------------------------------------------------------
# Cas nominaux
# ---------------------------------------------------------------------------

class TestValidateNominal:
    def test_payload_valide(self):
        assert validate(VALID_PAYLOAD) is True

    def test_valeurs_limites_basses(self):
        payload = {**VALID_PAYLOAD, "soil_moisture": 0, "temp_air": -10,
                   "humidity_air": 0, "lux": 0}
        assert validate(payload) is True

    def test_valeurs_limites_hautes(self):
        payload = {**VALID_PAYLOAD, "soil_moisture": 100, "temp_air": 60,
                   "humidity_air": 100, "lux": 200_000}
        assert validate(payload) is True


# ---------------------------------------------------------------------------
# Champs manquants
# ---------------------------------------------------------------------------

class TestValidateChampsManquants:
    @pytest.mark.parametrize("champ", ["ts", "soil_moisture", "temp_air", "humidity_air", "lux"])
    def test_champ_absent(self, champ):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != champ}
        assert validate(payload) is False

    def test_payload_vide(self):
        assert validate({}) is False


# ---------------------------------------------------------------------------
# Valeurs hors plage
# ---------------------------------------------------------------------------

class TestValidateHorsPlage:
    def test_humidite_sol_negative(self):
        assert validate({**VALID_PAYLOAD, "soil_moisture": -1}) is False

    def test_humidite_sol_superieure_100(self):
        assert validate({**VALID_PAYLOAD, "soil_moisture": 101}) is False

    def test_temperature_trop_basse(self):
        assert validate({**VALID_PAYLOAD, "temp_air": -11}) is False

    def test_temperature_trop_haute(self):
        assert validate({**VALID_PAYLOAD, "temp_air": 61}) is False

    def test_lux_negatif(self):
        assert validate({**VALID_PAYLOAD, "lux": -1}) is False

    def test_lux_trop_eleve(self):
        assert validate({**VALID_PAYLOAD, "lux": 200_001}) is False

    def test_humidite_air_hors_plage(self):
        assert validate({**VALID_PAYLOAD, "humidity_air": 150}) is False


# ---------------------------------------------------------------------------
# Types inattendus
# ---------------------------------------------------------------------------

class TestValidateTypes:
    def test_valeur_string_convertible(self):
        # Arduino peut envoyer des strings numériques
        assert validate({**VALID_PAYLOAD, "soil_moisture": "45.0"}) is True

    def test_valeur_none(self):
        assert validate({**VALID_PAYLOAD, "lux": None}) is False

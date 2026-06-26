"""
Tests unitaires pour write_to_influx() et open_serial() de serial_to_db.
Aucun hardware requis — tout est mocké.

Note technique : Point est importé via `from influxdb_client import Point` dans le
module cible. Patcher `src.acquisition.serial_to_db.Point` via unittest.mock.patch
ne prend pas effet car le nom est déjà lié dans le namespace du module au chargement.
On utilise directement sys.modules["influxdb_client"].Point, qui est le même objet.
"""
import sys
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Patch des modules hardware avant tout import du module cible
# ---------------------------------------------------------------------------
sys.modules.setdefault("serial", MagicMock())
sys.modules.setdefault("influxdb_client", MagicMock())
sys.modules.setdefault("influxdb_client.client", MagicMock())
sys.modules.setdefault("influxdb_client.client.write_api", MagicMock())

# SerialException doit être une vraie classe d'exception pour que les clauses
# `except serial.SerialException` du module cible fonctionnent correctement.
class _SerialException(Exception):
    pass

sys.modules["serial"].SerialException = _SerialException

_fake_cfg = {
    "serial": {"port": "COM3", "baudrate": 9600, "timeout": 2,
               "reconnect_delay_base": 2, "reconnect_delay_max": 60},
    "influxdb": {"url": "http://localhost:8086", "token": "test",
                 "org": "SRB", "bucket": "srb_sensors"},
    "logging": {"level": "DEBUG", "dir": "logs", "max_bytes": 1024, "backup_count": 1},
    "acquisition": {"interval_seconds": 900},
}

with patch.dict("sys.modules", {"src.common.config": MagicMock(cfg=_fake_cfg)}):
    from src.acquisition.serial_to_db import open_serial, write_to_influx  # noqa: E402

# Référence au mock influxdb_client — même objet que serial_to_db.Point
_influxdb_mock = sys.modules["influxdb_client"]

# ---------------------------------------------------------------------------
# Payload de référence
# ---------------------------------------------------------------------------

VALID_PAYLOAD = {
    "ts": 1_700_000_000,
    "soil_moisture": 45.0,
    "temp_air": 22.5,
    "humidity_air": 60.0,
    "lux": 15000.0,
}


# ---------------------------------------------------------------------------
# write_to_influx
# ---------------------------------------------------------------------------

class TestWriteToInflux:
    """
    Stratégie : _influxdb_mock.Point est le même objet que serial_to_db.Point
    (assigné via `from influxdb_client import Point`). On le configure comme
    chainable et on réinitialise ses compteurs avant chaque test via fixture.
    """

    @pytest.fixture(autouse=True)
    def _point_chainable(self):
        """Rend Point.return_value chainable et réinitialise les compteurs."""
        pm = _influxdb_mock.Point
        pm.reset_mock()
        pi = pm.return_value   # instance retournée par Point("environment")
        pi.tag.reset_mock()
        pi.field.reset_mock()
        pi.time.reset_mock()
        # Chaque méthode builder renvoie l'instance elle-même
        pi.tag.return_value = pi
        pi.field.return_value = pi
        pi.time.return_value = pi
        self._point_instance = pi
        yield pi

    def test_write_api_appele_une_fois(self):
        write_api = MagicMock()
        write_to_influx(write_api, VALID_PAYLOAD)
        write_api.write.assert_called_once()

    def test_bucket_et_org_corrects(self):
        write_api = MagicMock()
        write_to_influx(write_api, VALID_PAYLOAD)
        _, kwargs = write_api.write.call_args
        assert kwargs["bucket"] == "srb_sensors"
        assert kwargs["org"] == "SRB"

    def test_measurement_environment(self):
        write_api = MagicMock()
        write_to_influx(write_api, VALID_PAYLOAD)
        _influxdb_mock.Point.assert_called_once_with("environment")

    def test_tag_station_srb_balcon(self):
        write_api = MagicMock()
        write_to_influx(write_api, VALID_PAYLOAD)
        self._point_instance.tag.assert_called_once_with("station", "SRB-balcon")

    def test_quatre_champs_presents_en_float(self):
        write_api = MagicMock()
        write_to_influx(write_api, VALID_PAYLOAD)
        field_calls = {c.args[0]: c.args[1] for c in self._point_instance.field.call_args_list}
        assert field_calls == {
            "soil_moisture": 45.0,
            "temp_air": 22.5,
            "humidity_air": 60.0,
            "lux": 15000.0,
        }

    def test_conversion_timestamp_nanosecondes(self):
        """ts en epoch secondes → multiplié par 10^6 pour InfluxDB NANOSECONDS."""
        write_api = MagicMock()
        write_to_influx(write_api, VALID_PAYLOAD)
        ts_arg = self._point_instance.time.call_args.args[0]
        assert ts_arg == 1_700_000_000 * 10**6

    def test_valeurs_string_castees_en_float(self):
        """Arduino peut envoyer des chaînes numériques — elles doivent être float."""
        write_api = MagicMock()
        payload = {**VALID_PAYLOAD, "soil_moisture": "45.0", "lux": "15000"}
        write_to_influx(write_api, payload)
        field_calls = {c.args[0]: c.args[1] for c in self._point_instance.field.call_args_list}
        assert isinstance(field_calls["soil_moisture"], float)
        assert isinstance(field_calls["lux"], float)


# ---------------------------------------------------------------------------
# open_serial
# ---------------------------------------------------------------------------

class TestOpenSerial:

    def test_succes_immediat(self):
        """Port disponible dès la première tentative."""
        mock_ser = MagicMock()
        with patch("src.acquisition.serial_to_db.serial.Serial", return_value=mock_ser) as mock_cls:
            result = open_serial()
        mock_cls.assert_called_once_with(port="COM3", baudrate=9600, timeout=2)
        assert result is mock_ser

    def test_echec_puis_succes(self):
        """Deux échecs puis succès : sleep appelé deux fois."""
        mock_ser = MagicMock()
        side_effects = [
            _SerialException("port busy"),
            _SerialException("port busy"),
            mock_ser,
        ]
        with patch("src.acquisition.serial_to_db.serial.Serial", side_effect=side_effects):
            with patch("src.acquisition.serial_to_db.time.sleep") as mock_sleep:
                result = open_serial()
        assert result is mock_ser
        assert mock_sleep.call_count == 2

    def test_backoff_exponentiel(self):
        """Le délai double à chaque tentative : 2 s → 4 s → 8 s."""
        mock_ser = MagicMock()
        side_effects = [_SerialException("e")] * 3 + [mock_ser]
        with patch("src.acquisition.serial_to_db.serial.Serial", side_effect=side_effects):
            with patch("src.acquisition.serial_to_db.time.sleep") as mock_sleep:
                open_serial()
        mock_sleep.assert_has_calls([call(2), call(4), call(8)])

    def test_backoff_plafonne_a_max_delay(self):
        """Le délai ne dépasse pas reconnect_delay_max (60 s)."""
        mock_ser = MagicMock()
        # 6 échecs : délais attendus 2, 4, 8, 16, 32, 60 (pas 64)
        side_effects = [_SerialException("e")] * 6 + [mock_ser]
        with patch("src.acquisition.serial_to_db.serial.Serial", side_effect=side_effects):
            with patch("src.acquisition.serial_to_db.time.sleep") as mock_sleep:
                open_serial()
        delays = [c.args[0] for c in mock_sleep.call_args_list]
        assert delays == [2, 4, 8, 16, 32, 60]

    def test_pas_de_sleep_si_succes_immediat(self):
        """Aucun sleep si la connexion réussit du premier coup."""
        with patch("src.acquisition.serial_to_db.serial.Serial", return_value=MagicMock()):
            with patch("src.acquisition.serial_to_db.time.sleep") as mock_sleep:
                open_serial()
        mock_sleep.assert_not_called()

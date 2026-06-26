"""
Phase 1 — Acquisition série vers InfluxDB.
Service permanent avec reconnexion automatique (backoff exponentiel).

Attend un flux JSON toutes les 15 min depuis Arduino Mega 2560 :
{"ts": <epoch_ms>, "soil_moisture": <0-100>, "temp_air": <°C>,
 "humidity_air": <0-100>, "lux": <lux>}
"""
import json
import sys
import time
from pathlib import Path

import serial
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Résolution des chemins pour un lancement depuis la racine du projet
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.common.config import cfg
from src.common.logger import get_logger

log = get_logger("acquisition.serial_to_db")

SERIAL_CFG = cfg["serial"]
INFLUX_CFG = cfg["influxdb"]

REQUIRED_FIELDS = {"ts", "soil_moisture", "temp_air", "humidity_air", "lux"}
FIELD_RANGES = {
    "soil_moisture": (0, 100),
    "temp_air": (-10, 60),
    "humidity_air": (0, 100),
    "lux": (0, 200_000),
}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(payload: dict) -> bool:
    if not REQUIRED_FIELDS.issubset(payload.keys()):
        missing = REQUIRED_FIELDS - payload.keys()
        log.warning("Champs manquants dans le payload", extra={"missing": list(missing)})
        return False
    for field, (lo, hi) in FIELD_RANGES.items():
        value = payload.get(field)
        if value is None or not (lo <= float(value) <= hi):
            log.warning(
                "Valeur hors plage",
                extra={"field": field, "value": value, "range": [lo, hi]},
            )
            return False
    return True


# ---------------------------------------------------------------------------
# Écriture InfluxDB
# ---------------------------------------------------------------------------

def write_to_influx(write_api, payload: dict) -> None:
    point = (
        Point("environment")
        .tag("station", "SRB-balcon")
        .field("soil_moisture", float(payload["soil_moisture"]))
        .field("temp_air", float(payload["temp_air"]))
        .field("humidity_air", float(payload["humidity_air"]))
        .field("lux", float(payload["lux"]))
        .time(int(payload["ts"]) * 10**6, WritePrecision.NS)
    )
    write_api.write(
        bucket=INFLUX_CFG["bucket"],
        org=INFLUX_CFG["org"],
        record=point,
    )
    log.info("Point écrit dans InfluxDB", extra={"ts": payload["ts"]})


# ---------------------------------------------------------------------------
# Connexion série avec backoff
# ---------------------------------------------------------------------------

def open_serial() -> serial.Serial:
    delay = SERIAL_CFG["reconnect_delay_base"]
    max_delay = SERIAL_CFG["reconnect_delay_max"]
    while True:
        try:
            ser = serial.Serial(
                port=SERIAL_CFG["port"],
                baudrate=SERIAL_CFG["baudrate"],
                timeout=SERIAL_CFG["timeout"],
            )
            log.info("Port série ouvert", extra={"port": SERIAL_CFG["port"]})
            return ser
        except serial.SerialException as exc:
            log.error(
                "Échec ouverture port série, nouvelle tentative",
                extra={"port": SERIAL_CFG["port"], "delay": delay, "error": str(exc)},
            )
            time.sleep(delay)
            delay = min(delay * 2, max_delay)


# ---------------------------------------------------------------------------
# Boucle principale
# ---------------------------------------------------------------------------

def run() -> None:
    log.info("Démarrage du service d'acquisition SRB")

    influx_client = InfluxDBClient(
        url=INFLUX_CFG["url"],
        token=INFLUX_CFG["token"],
        org=INFLUX_CFG["org"],
    )
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    ser = open_serial()

    try:
        while True:
            try:
                raw = ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    log.debug("Ligne non-JSON ignorée", extra={"raw": line[:120]})
                    continue

                if not validate(payload):
                    continue

                write_to_influx(write_api, payload)

            except serial.SerialException as exc:
                log.error(
                    "Perte de connexion série, reconnexion",
                    extra={"error": str(exc)},
                )
                try:
                    ser.close()
                except Exception:
                    pass
                ser = open_serial()

    except KeyboardInterrupt:
        log.info("Arrêt demandé par l'utilisateur")
    finally:
        ser.close()
        write_api.close()
        influx_client.close()
        log.info("Service arrêté proprement")


if __name__ == "__main__":
    run()

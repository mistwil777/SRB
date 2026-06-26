"""
Configure les cellules du dashboard AgroProject dans InfluxDB.
Usage : python -m src.common.dashboard_setup
"""
import json
import sys
from pathlib import Path

import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.common.config import cfg
from src.common.logger import get_logger

log = get_logger("common.dashboard_setup")

INFLUX_URL   = cfg["influxdb"]["url"]
TOKEN        = cfg["influxdb"]["token"]
ORG          = cfg["influxdb"]["org"]
DASHBOARD_ID = "10ed883944a18000"

HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json",
}

BASE_QUERY = """from(bucket: "srb_sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "environment")
  |> filter(fn: (r) => r.source == "synthetic")
  |> filter(fn: (r) => r._field == "{field}")"""

CELLS = [
    {
        "name": "Humidite sol (%)",
        "field": "soil_moisture",
        "x": 0, "y": 0, "w": 6, "h": 4,
        "colors": [{"id": "base", "type": "scale", "hex": "#8F8AF4", "name": "Do Androids Dream of Electric Sheep?", "value": 0}],
    },
    {
        "name": "Humidite air (%)",
        "field": "humidity_air",
        "x": 6, "y": 0, "w": 6, "h": 4,
        "colors": [],
    },
    {
        "name": "Luminosite (lux)",
        "field": "lux",
        "x": 0, "y": 4, "w": 12, "h": 4,
        "colors": [],
    },
    {
        "name": "Vue ensemble - T + Sol + HR",
        "field": None,   # requête multi-fields
        "x": 0, "y": 8, "w": 12, "h": 5,
        "colors": [],
    },
]

MULTI_QUERY = """from(bucket: "srb_sensors")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r._measurement == "environment")
  |> filter(fn: (r) => r.source == "synthetic")
  |> filter(fn: (r) => r._field == "temp_air" or r._field == "soil_moisture" or r._field == "humidity_air")"""


def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{INFLUX_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        log.error("Erreur API InfluxDB", extra={"status": e.code, "url": url})
        raise


def create_cell(cell: dict) -> str:
    query = MULTI_QUERY if cell["field"] is None else BASE_QUERY.format(field=cell["field"])

    payload = {
        "x": cell["x"], "y": cell["y"],
        "w": cell["w"], "h": cell["h"],
        "name": cell["name"],
        "queries": [{"text": query, "editMode": "advanced", "name": ""}],
        "axes": {
            "x": {"bounds": ["", ""], "label": "", "prefix": "", "suffix": "", "base": "10", "scale": "linear"},
            "y": {"bounds": ["", ""], "label": "", "prefix": "", "suffix": "", "base": "10", "scale": "linear"},
        },
        "type": "xy",
        "geom": "line",
        "colors": cell.get("colors", []),
        "legend": {},
        "tableOptions": {},
        "fieldOptions": [],
        "timeFormat": "",
        "decimalPlaces": {"isEnforced": False, "digits": 2},
    }

    result = _request("POST", f"/api/v2/dashboards/{DASHBOARD_ID}/cells", payload)
    return result.get("id", "?")


def run() -> None:
    log.info("Configuration du dashboard AgroProject")
    for cell in CELLS:
        cell_id = create_cell(cell)
        log.info("Cellule creee", extra={"cell": cell["name"], "id": cell_id})
        print(f"  + {cell['name']}")
    print("\nDashboard configure : http://localhost:8086")


if __name__ == "__main__":
    run()

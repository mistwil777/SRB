"""
Générateur de données synthétiques — Saison de culture SRB.

Simule ~120 jours de mesures capteurs toutes les 15 minutes avec :
- Cycles journaliers et saisonniers réalistes (pomme de terre, balcon urbain)
- Épisodes de stress programmables (sécheresse, canicule, sur-arrosage)
- Trous de données aléatoires (déconnexions Arduino)
- Bruit de mesure propre à chaque capteur

Usage :
    python -m src.acquisition.synthetic_generator
    python -m src.acquisition.synthetic_generator --days 60 --start 2026-04-15
"""

import argparse
import math
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from src.common.config import cfg
from src.common.logger import get_logger

log = get_logger("acquisition.synthetic_generator")

INFLUX_CFG = cfg["influxdb"]
INTERVAL_MIN = 15  # minutes entre deux mesures


# ---------------------------------------------------------------------------
# Modèle de stress
# ---------------------------------------------------------------------------

@dataclass
class StressEvent:
    """Épisode de stress sur la plante."""
    name: str
    start_day: int       # jour de la saison (0 = plantation)
    duration_days: int
    type: str            # "drought" | "heatwave" | "overwater"


@dataclass
class SeasonConfig:
    """Paramètres de la saison simulée."""
    start_date: datetime
    total_days: int = 120
    planting_day: int = 0

    # Température de base selon le mois (balcon urbain, orientation sud)
    base_temp_april: float = 13.0    # °C moyenne avril
    base_temp_august: float = 26.0   # °C moyenne août

    # Arrosage
    watering_interval_days: float = 3.0   # tous les 3 jours en moyenne
    watering_amount: float = 25.0          # remontée d'humidité sol en %
    soil_decay_rate: float = 0.008         # perte d'humidité par heure

    stress_events: list[StressEvent] = field(default_factory=lambda: [
        StressEvent("sécheresse précoce",  start_day=20, duration_days=5,  type="drought"),
        StressEvent("canicule juillet",    start_day=75, duration_days=7,  type="heatwave"),
        StressEvent("sur-arrosage",        start_day=50, duration_days=2,  type="overwater"),
    ])


# ---------------------------------------------------------------------------
# Fonctions de simulation
# ---------------------------------------------------------------------------

def _day_fraction(ts: datetime) -> float:
    """Fraction de la journée (0.0 = minuit, 0.5 = midi, 1.0 = minuit suivant)."""
    return (ts.hour * 3600 + ts.minute * 60 + ts.second) / 86400


def _season_fraction(day: int, total_days: int) -> float:
    """Fraction de la saison (0.0 = plantation, 1.0 = récolte)."""
    return max(0.0, min(1.0, day / total_days))


def _stress_factor(day: int, events: list[StressEvent], event_type: str) -> float:
    """Retourne l'intensité d'un stress actif (0.0 = aucun, 1.0 = max)."""
    for evt in events:
        if evt.type == event_type and evt.start_day <= day < evt.start_day + evt.duration_days:
            # Montée progressive puis descente
            progress = (day - evt.start_day) / evt.duration_days
            return math.sin(progress * math.pi)
    return 0.0


def simulate_temp_air(ts: datetime, day: int, cfg: SeasonConfig) -> float:
    """Température air en °C — cycle journalier + tendance saisonnière + canicule."""
    sf = _season_fraction(day, cfg.total_days)
    base = cfg.base_temp_april + (cfg.base_temp_august - cfg.base_temp_april) * sf

    # Cycle journalier : minimum à 5h, maximum à 14h
    df = _day_fraction(ts)
    daily = 6.0 * math.sin((df - 5 / 24) * 2 * math.pi - math.pi / 2)

    # Stress canicule
    heat_stress = _stress_factor(day, cfg.stress_events, "heatwave") * 8.0

    # Bruit capteur DHT22 (±0.5 °C)
    noise = random.gauss(0, 0.3)

    return round(base + daily + heat_stress + noise, 1)


def simulate_humidity_air(temp: float) -> float:
    """Humidité air en % — inversement corrélée à la température."""
    # Relation empirique simple : T° élevée → air sec
    base = 85.0 - (temp - 10.0) * 1.2
    noise = random.gauss(0, 2.0)
    return round(max(25.0, min(95.0, base + noise)), 1)


def simulate_lux(ts: datetime, day: int, cfg: SeasonConfig) -> float:
    """Éclairement en lux — cycle solaire + nuages + saison."""
    df = _day_fraction(ts)
    sf = _season_fraction(day, cfg.total_days)

    # Heures de lever/coucher du soleil (approximation saison printemps-été)
    sunrise = 0.25 - sf * 0.04   # 6h → 5h
    sunset  = 0.79 + sf * 0.04   # 19h → 20h

    if df < sunrise or df > sunset:
        return 0.0

    # Courbe solaire en cloche
    solar_progress = (df - sunrise) / (sunset - sunrise)
    peak_lux = 45_000 + sf * 20_000   # montée saisonnière du pic
    solar = peak_lux * math.sin(solar_progress * math.pi)

    # Passages nuageux aléatoires (30 % du temps, réduction 20-80 %)
    cloud_factor = 1.0
    if random.random() < 0.30:
        cloud_factor = random.uniform(0.2, 0.8)

    noise = random.gauss(0, solar * 0.03)
    return round(max(0.0, solar * cloud_factor + noise), 1)


def simulate_soil_moisture(
    day: int,
    hour_of_season: float,
    soil_state: dict,
    cfg: SeasonConfig,
) -> float:
    """
    Humidité sol en % — décroissance exponentielle entre arrosages.
    soil_state est un dict mutable pour persister l'état entre appels.
    """
    # Initialisation
    if "moisture" not in soil_state:
        soil_state["moisture"] = 65.0
        soil_state["next_watering"] = random.uniform(0, cfg.watering_interval_days * 24)

    # Arrosage ?
    if hour_of_season >= soil_state["next_watering"]:
        amount = cfg.watering_amount
        # Sur-arrosage
        if _stress_factor(day, cfg.stress_events, "overwater") > 0.3:
            amount *= 1.8
        soil_state["moisture"] = min(95.0, soil_state["moisture"] + amount)
        soil_state["next_watering"] = hour_of_season + random.gauss(
            cfg.watering_interval_days * 24,
            cfg.watering_interval_days * 8,
        )

    # Sécheresse : pas d'arrosage pendant l'épisode
    if _stress_factor(day, cfg.stress_events, "drought") > 0.5:
        soil_state["next_watering"] = hour_of_season + 48

    # Évapotranspiration
    soil_state["moisture"] = max(
        5.0,
        soil_state["moisture"] - cfg.soil_decay_rate * INTERVAL_MIN
    )

    noise = random.gauss(0, 1.0)
    return round(max(5.0, min(98.0, soil_state["moisture"] + noise)), 1)


# ---------------------------------------------------------------------------
# Génération de la saison complète
# ---------------------------------------------------------------------------

def generate_season(season: SeasonConfig) -> list[dict]:
    """Génère tous les points de mesure de la saison."""
    points = []
    soil_state: dict = {}

    total_minutes = season.total_days * 24 * 60
    current = season.start_date
    hour_of_season = 0.0

    # Trous de données : 2 à 4 gaps aléatoires de 1 à 12 heures
    n_gaps = random.randint(2, 4)
    gap_starts = sorted(random.uniform(0, total_minutes) for _ in range(n_gaps))
    gap_durations = [random.uniform(60, 720) for _ in range(n_gaps)]  # minutes
    gaps = [(s, s + d) for s, d in zip(gap_starts, gap_durations)]

    minute = 0
    while minute <= total_minutes:
        # Trou de données ?
        in_gap = any(s <= minute <= e for s, e in gaps)
        if not in_gap:
            day = minute // (24 * 60)
            temp = simulate_temp_air(current, day, season)
            point = {
                "ts": int(current.timestamp()),
                "soil_moisture": simulate_soil_moisture(day, hour_of_season, soil_state, season),
                "temp_air": temp,
                "humidity_air": simulate_humidity_air(temp),
                "lux": simulate_lux(current, day, season),
            }
            points.append(point)

        current += timedelta(minutes=INTERVAL_MIN)
        minute += INTERVAL_MIN
        hour_of_season += INTERVAL_MIN / 60

    return points


# ---------------------------------------------------------------------------
# Écriture dans InfluxDB
# ---------------------------------------------------------------------------

def write_to_influx(points: list[dict]) -> None:
    client = InfluxDBClient(
        url=INFLUX_CFG["url"],
        token=INFLUX_CFG["token"],
        org=INFLUX_CFG["org"],
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    batch: list[Point] = []
    for p in points:
        batch.append(
            Point("environment")
            .tag("station", "SRB-balcon")
            .tag("source", "synthetic")
            .field("soil_moisture", p["soil_moisture"])
            .field("temp_air", p["temp_air"])
            .field("humidity_air", p["humidity_air"])
            .field("lux", p["lux"])
            .time(p["ts"] * 10**9, WritePrecision.NS)
        )
        # Écriture par batch de 500
        if len(batch) >= 500:
            write_api.write(bucket=INFLUX_CFG["bucket"], org=INFLUX_CFG["org"], record=batch)
            batch = []

    if batch:
        write_api.write(bucket=INFLUX_CFG["bucket"], org=INFLUX_CFG["org"], record=batch)

    write_api.close()
    client.close()


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Générateur de données synthétiques SRB")
    parser.add_argument(
        "--start",
        default="2026-04-15",
        help="Date de plantation (YYYY-MM-DD, défaut: 2026-04-15)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=120,
        help="Durée de la saison en jours (défaut: 120)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simuler sans écrire dans InfluxDB",
    )
    return parser.parse_args()


def run(start: Optional[str] = None, days: int = 120, dry_run: bool = False) -> None:
    start_dt = datetime.strptime(start or "2026-04-15", "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    season = SeasonConfig(start_date=start_dt, total_days=days)

    log.info(
        "Démarrage génération saison synthétique",
        extra={"start": start_dt.date().isoformat(), "days": days, "dry_run": dry_run},
    )

    points = generate_season(season)
    total = len(points)
    log.info("Points générés", extra={"total": total, "interval_min": INTERVAL_MIN})

    # Résumé des stress simulés
    for evt in season.stress_events:
        log.info(
            "Stress simulé",
            extra={"stress": evt.name, "start_day": evt.start_day, "duration": evt.duration_days},
        )

    if dry_run:
        # Afficher un aperçu
        for p in points[:3]:
            print(p)
        print(f"... ({total} points au total, aucune écriture en base)")
        return

    log.info("Écriture dans InfluxDB...")
    write_to_influx(points)
    log.info("Injection terminée", extra={"points_ecrits": total})
    print(f"\nOK — {total} points injectes dans InfluxDB")
    print(f"  Bucket  : {INFLUX_CFG['bucket']}")
    print(f"  Periode : {start_dt.date()} -> {(start_dt + timedelta(days=days)).date()}")
    print(f"  Tag     : source=synthetic")
    print(f"\n  Interface : http://localhost:8086")


if __name__ == "__main__":
    args = parse_args()
    run(start=args.start, days=args.days, dry_run=args.dry_run)

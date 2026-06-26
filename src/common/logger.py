"""
Logging structuré JSON pour tous les modules SRB.
Usage : from src.common.logger import get_logger; log = get_logger(__name__)
"""
import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Clés réservées par LogRecord — ne pas écraser
        _RESERVED = {"ts", "level", "module", "msg", "name", "message", "exc"}
        if hasattr(record, "extra"):
            payload.update({k: v for k, v in record.extra.items() if k not in _RESERVED})
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    log_dir = Path(os.getenv("SRB_LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Handler fichier rotatif
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "srb.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(_JsonFormatter())
    file_handler.setLevel(logging.DEBUG)

    # Handler console (human-readable)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    )
    console_handler.setLevel(logging.INFO)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

from __future__ import annotations

import logging
import os


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging() -> None:
    """Configure process-wide console logging without duplicating handlers."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format=LOG_FORMAT, force=False)
    logging.getLogger("shippingassent").setLevel(level)


def get_logger(component: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(f"shippingassent.{component}")


__all__ = ["configure_logging", "get_logger"]

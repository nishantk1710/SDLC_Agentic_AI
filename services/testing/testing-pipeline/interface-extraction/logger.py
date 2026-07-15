"""Thin logging helper for the Interface Extraction stage.

Handler-free on purpose: the Testing Phase app (``services/testing/main.py``)
owns logging configuration via ``logging.basicConfig``. This just hands back a
named logger (optionally keyed by ``run_id``) so lines are easy to group,
without adding duplicate handlers.
"""

from __future__ import annotations

import logging


def get_logger(name: str = "interface_extraction", run_id: str | None = None) -> logging.Logger:
    return logging.getLogger(f"{name}:{run_id}" if run_id else name)

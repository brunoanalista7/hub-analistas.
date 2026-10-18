"""Onde o Hub guarda os dados (sempre fora da pasta do código)."""

import os
from pathlib import Path


def data_dir() -> Path:
    custom = os.environ.get("HUB_DADOS")
    base = Path(custom) if custom else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Hub"
    base.mkdir(parents=True, exist_ok=True)
    return base

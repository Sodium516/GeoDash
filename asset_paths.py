"""Prefer the extracted UHD artwork without changing logical world dimensions."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'assets/original'
try:UHD=json.loads((ASSETS/'uhd/manifest.json').read_text())
except (OSError,ValueError):UHD={}


def texture(name):
    high=ASSETS/'uhd'/name
    return high if name in UHD and high.is_file() else ASSETS/name


def resolution(name):return UHD.get(name,1) if texture(name).parent.name=='uhd' else 1

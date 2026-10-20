"""Installed official-level catalogue. Runtime uses only local extracted files."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / 'assets/levels/catalog.json'
NAMES = (
    ('Stereo Madness','StereoMadness'), ('Back On Track','BackOnTrack'),
    ('Polargeist','Polargeist'), ('Dry Out','DryOut'), ('Base After Base','BaseAfterBase'),
    ("Can't Let Go",'CantLetGo'), ('Jumper','Jumper'), ('Time Machine','TimeMachine'),
    ('Cycles','Cycles'), ('xStep','xStep'), ('Clutterfunk','Clutterfunk'),
    ('Theory of Everything','TheoryOfEverything'), ('Electroman Adventures','Electroman'),
    ('Clubstep','Clubstep'), ('Electrodynamix','Electrodynamix'), ('Hexagon Force','HexagonForce'),
    ('Blast Processing','BlastProcessing'), ('Theory of Everything 2','TheoryOfEverything2'),
    ('Geometrical Dominator','GeometricalDominator'), ('Deadlocked','Deadlocked'),
    ('Fingerdash','Fingerdash'), ('Dash','Dash'),
)
EXTRA = {3001:('The Challenge','DJRubRub'), 5001:('The Tower','tower01'),
         5002:('The Sewers','tower01'),5003:('The Cellar','tower01'),5004:('The Secret Hollow','tower01')}


def entries():
    return json.loads(CATALOG.read_text()) if CATALOG.exists() else []


def entry(level_id):
    return next((e for e in entries() if e['id']==int(level_id)), None)

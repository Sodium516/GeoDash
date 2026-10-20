"""Small, validated local preferences shared by menu and game."""
import json
from pathlib import Path

PATH=Path(__file__).resolve().parent/'assets/progress/library.json'
DEFAULTS=dict(selected=17,volume=.55,muted=False,primary=[255,220,75],secondary=[245,252,255],menu_music='')


def load():
    try:data=json.loads(PATH.read_text())
    except (OSError,ValueError):data={}
    result=dict(DEFAULTS)
    if isinstance(data,dict):result.update(data)
    try:result['volume']=max(0.,min(1.,float(result['volume'])))
    except (ValueError,TypeError):result['volume']=.55
    for key in ('primary','secondary'):
        if not isinstance(result[key],list) or len(result[key])!=3 or any(type(c)!=int or not 0<=c<=255 for c in result[key]):result[key]=DEFAULTS[key][:]
    if not isinstance(result['menu_music'],str):result['menu_music']=''
    result['muted']=bool(result['muted'])
    return result


def save(**changes):
    data=load();data.update(changes)
    PATH.parent.mkdir(parents=True,exist_ok=True)
    temp=PATH.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(PATH)
    return data

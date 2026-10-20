"""Extract only Blast Processing resources from this user's installed game.

Reads the installation; never modifies it. Run with .venv/bin/python.
"""
import base64
import json
import os
import plistlib
import re
import shutil
import zlib
from pathlib import Path

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame

ROOT = Path(__file__).resolve().parent
RESOURCES = (Path.home() / 'Library/Application Support/Steam/steamapps/common/'
             'Geometry Dash/Geometry Dash.app/Contents/Resources')


def numbers(value):
    return [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', value)]


def main(all_levels=False):
    pygame.display.init()
    pygame.display.set_mode((1, 1))
    target = ROOT / 'assets/original'
    target.mkdir(parents=True, exist_ok=True)
    sources = sorted((RESOURCES/'levels').glob('*.txt'), key=lambda p:int(p.stem)) if all_levels else [RESOURCES/'levels/17.txt']
    objects, catalogue = [], []
    from level_catalog import NAMES, EXTRA
    level_target = ROOT/'assets/levels'
    level_target.mkdir(parents=True,exist_ok=True)
    for source in sources:
        level_id=int(source.stem)
        data=source.read_bytes().strip()
        raw=zlib.decompress(base64.urlsafe_b64decode(data+b'='*(-len(data)%4)),31).decode()
        parts=raw.split(';');v=parts[0].split(',');settings=dict(zip(v[::2],v[1::2]))
        current=[dict(zip(v[::2],v[1::2])) for t in parts[1:] if t for v in [t.split(',')]]
        objects.extend(current)
        name,song=NAMES[level_id-1] if level_id<=len(NAMES) else EXTRA[level_id]
        shutil.copyfile(source,level_target/source.name)
        shutil.copyfile(RESOURCES/(song+'.mp3'),target/(song+'.mp3'))
        catalogue.append(dict(id=level_id,name=name,song=song+'.mp3',objects=len(current),
            background=max(1,int(settings.get('kA6') or 1)),ground=max(1,int(settings.get('kA7') or 1)),
            platformer=settings.get('kA22')=='1',end_x=max(float(o['2']) for o in current)+255))
    if all_levels:
        (level_target/'catalog.json').write_text(json.dumps(catalogue,indent=2)+'\n')
    ids = {int(o['1']) for o in objects}
    metadata = {o['id']: o for o in json.loads((ROOT / 'reference/objects.json').read_text())}
    frames, sheets = {}, {}
    for name in ('GJ_GameSheet', 'GJ_GameSheet02', 'GJ_GameSheet03', 'GJ_GameSheet04'):
        plist = plistlib.loads((RESOURCES / (name + '.plist')).read_bytes())
        sheets[name] = pygame.image.load(str(RESOURCES / (name + '.png'))).convert_alpha()
        for key, frame in plist['frames'].items():
            frames[key] = (name, frame)
    # Icon layers are included so the renderer can rotate/composite real icons.
    for name in ('player_01', 'ship_01', 'player_ball_01', 'bird_01', 'dart_01', 'robot_01', 'spider_01', 'swing_01', 'jetpack_01'):
        p = RESOURCES / 'icons' / (name + '.plist')
        if p.exists():
            plist = plistlib.loads(p.read_bytes())
            sheets[name] = pygame.image.load(str(p.with_suffix('.png'))).convert_alpha()
            for key, frame in plist['frames'].items():
                frames[key] = (name, frame)
    selected = set()
    manifest = {}
    for id in ids:
        if id not in metadata:
            continue  # Legacy triggers are invisible in play.
        info = dict(metadata[id])
        frame = info['frame']
        if frame in frames:
            info['size'] = numbers(frames[frame][1]['spriteSourceSize'])
            selected.add(frame)
            mask = frame.replace('_001.png', '_color_001.png')
            if mask in frames:
                selected.add(mask)
                info['mask'] = mask
            back = frame.replace('_front_', '_back_')
            if back != frame and back in frames:
                selected.add(back)
                info['back'] = back
        manifest[str(id)] = info
    for name in frames:
        if any(name.startswith(v) for v in ('player_01_', 'ship_01_', 'player_ball_01_', 'bird_01_', 'dart_01_', 'robot_01_', 'spider_01_', 'swing_01_', 'jetpack_01_')):
            selected.add(name)
    for key in selected:
        sheet_name, f = frames[key]
        x, y, w, h = map(round, numbers(f['textureRect']))
        if f['textureRotated']:
            w, h = h, w
        sprite = sheets[sheet_name].subsurface((x, y, w, h)).copy()
        if f['textureRotated']:
            sprite = pygame.transform.rotate(sprite, 90)
        sw, sh = map(round, numbers(f['spriteSourceSize']))
        ox, oy = numbers(f['spriteOffset'])
        if sw <= 0 or sh <= 0:
            continue  # Empty atlas placeholders (not drawable sprites).
        full = pygame.Surface((sw, sh), pygame.SRCALPHA)
        full.blit(sprite, (round((sw - sprite.get_width()) / 2 + ox),
                           round((sh - sprite.get_height()) / 2 - oy)))
        pygame.image.save(full, str(target / key))
    if all_levels:
        for pattern in ('game_bg_*_001.png','groundSquare_*_001.png'):
            for source in RESOURCES.glob(pattern):
                if '-hd' not in source.name and '-uhd' not in source.name:
                    shutil.copyfile(source,target/source.name)
    for filename in ('game_bg_05_001.png', 'groundSquare_05_001.png', 'BlastProcessing.mp3',
                     'bigFont.fnt', 'bigFont.png'):
        shutil.copyfile(RESOURCES / filename, target / filename)
    for mode in ('Robot','Spider'):
        source=RESOURCES/(mode+'_AnimDesc.plist')
        if source.exists():
            animation=plistlib.loads(source.read_bytes().lstrip())
            (target/(mode.lower()+'_animation.json')).write_text(json.dumps(animation,separators=(',',':')))
    (target / 'objects.json').write_text(json.dumps(manifest, separators=(',', ':')))
    print(f'Extracted {len(selected)} textures for {len(objects)} original objects.')
    pygame.quit()


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all",action="store_true",help="Extract every installed official level and its assets.")
    main(parser.parse_args().all)

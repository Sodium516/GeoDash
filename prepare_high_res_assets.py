"""Extract UHD textures and menu art from the local installation, read-only."""
import json
import os
from pathlib import Path
import plistlib
import shutil

os.environ.setdefault('SDL_VIDEODRIVER','dummy')
import pygame
from prepare_original_assets import RESOURCES,ROOT,numbers

MENU_FRAMES={'GJ_logo_001.png','GJ_playBtn_001.png','GJ_garageBtn_001.png',
             'GJ_creatorBtn_001.png','GJ_optionsBtn_001.png','GJ_achBtn_001.png',
             'GJ_statsBtn_001.png','GJ_infoBtn_001.png','GJ_backBtn_001.png',
             'GJ_arrow_01_001.png','GJ_arrow_03_001.png','GJ_musicOnBtn_001.png',
             'GJ_musicOffBtn_001.png','GJ_closeBtn_001.png'}
MENU_FRAMES.update(f'difficulty_{i:02}_btn_001.png' for i in range(7))


def main():
    pygame.display.init();pygame.display.set_mode((1,1))
    base=ROOT/'assets/original';target=base/'uhd';target.mkdir(exist_ok=True)
    selected={p.name for p in base.glob('*.png')}|MENU_FRAMES
    manifest={}
    atlases=[RESOURCES/(name+'-uhd.plist') for name in ('GJ_GameSheet','GJ_GameSheet02',
             'GJ_GameSheet03','GJ_GameSheet04','GJ_LaunchSheet')]
    atlases.extend((RESOURCES/'icons').glob('*_01-uhd.plist'))
    for path in atlases:
        if not path.exists():continue
        data=plistlib.loads(path.read_bytes())
        wanted=set(data['frames'])&selected
        if not wanted:continue
        sheet=pygame.image.load(str(path.with_suffix('.png'))).convert_alpha()
        for name in wanted:
            frame=data['frames'][name]
            x,y,w,h=map(round,numbers(frame['textureRect']))
            if frame['textureRotated']:w,h=h,w
            sw,sh=map(round,numbers(frame['spriteSourceSize']))
            if min(sw,sh,w,h)<=0:continue
            sprite=sheet.subsurface((x,y,w,h)).copy()
            if frame['textureRotated']:sprite=pygame.transform.rotate(sprite,90)
            ox,oy=numbers(frame['spriteOffset'])
            canvas=pygame.Surface((sw,sh),pygame.SRCALPHA)
            canvas.blit(sprite,(round((sw-sprite.get_width())/2+ox),round((sh-sprite.get_height())/2-oy)))
            pygame.image.save(canvas,str(target/name));manifest[name]=4
    for name in selected:
        path=RESOURCES/(Path(name).stem+'-uhd.png')
        if path.exists():shutil.copyfile(path,target/name);manifest[name]=4
    for stem in ('bigFont','goldFont'):
        for ext in ('.fnt','.png'):
            path=RESOURCES/(stem+'-uhd'+ext)
            if path.exists():shutil.copyfile(path,target/(stem+ext))
        manifest[stem+'.png']=4
    for stem in ('game_bg_01_001','groundSquare_01_001'):
        path=RESOURCES/(stem+'-uhd.png')
        if path.exists():shutil.copyfile(path,target/(stem+'.png'));manifest[stem+'.png']=4
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Extracted {len(manifest)} UHD textures; original logical sizes are preserved.')
    pygame.quit()


if __name__=='__main__':main()

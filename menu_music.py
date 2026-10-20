"""Loop the user's exact local menu track; gameplay owns its own soundtrack."""
import os
from pathlib import Path
import pygame
import user_settings

ROOT=Path(__file__).resolve().parent


def track_path(settings):
    configured=os.environ.get('GEODASH_MENU_MUSIC') or settings.get('menu_music','')
    if configured:
        path=Path(configured).expanduser()
        if path.is_file():return path
    for suffix in ('.ogg','.mp3','.wav','.flac'):
        path=ROOT/'assets/menu'/('vintage_vuitton'+suffix)
        if path.is_file():return path
    return None


class MenuMusic:
    def __init__(self,settings):
        self.settings=settings;self.path=track_path(settings);self.error='';self.ready=False
        if self.path:
            try:
                if not pygame.mixer.get_init():pygame.mixer.init(frequency=44100,buffer=512)
                pygame.mixer.music.load(str(self.path))
                pygame.mixer.music.set_volume(0 if settings['muted'] else settings['volume'])
                pygame.mixer.music.play(-1,fade_ms=500);self.ready=True
            except (pygame.error,OSError) as error:self.error=str(error)

    def volume(self):
        if self.ready:pygame.mixer.music.set_volume(0 if self.settings['muted'] else self.settings['volume'])

    def focus(self,focused):
        if self.ready:
            if focused:pygame.mixer.music.unpause()
            else:pygame.mixer.music.pause()

    def stop(self):
        if self.ready and pygame.mixer.get_init():pygame.mixer.music.stop()
        self.ready=False

"""Native-art home screen and official-level carousel, at a fixed 60 FPS."""
import json
from pathlib import Path
import time

import geometry_dash as app
import asset_paths
import menu_music
import user_settings
from level_catalog import entries

pygame = app.pygame
ROOT = Path(__file__).resolve().parent
SIZE = (1280, 720)
PALETTE = [(125,255,0),(0,255,110),(0,255,255),(0,150,255),(70,70,255),(175,60,255),
           (255,0,200),(255,60,90),(255,135,0),(255,220,75),(245,252,255),(45,45,55)]
DIFFICULTY = [1, 1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 5, 5, 6, 5, 5, 4, 6, 5, 6, 5, 5]


class Menu:
    def __init__(self, screen, levels, settings):
        from blast_processing import BitmapFont
        self.screen, self.levels, self.settings = screen, levels, settings
        self.selected = next((i for i, e in enumerate(levels) if e['id'] == settings.get('selected')), 0)
        self.view = 'home'
        self.notice = ''
        self.font = BitmapFont()
        self.small = pygame.font.Font(None, 26)
        self.images = {}
        self.texts = {}
        self.buttons = []
        self.bests = {}
        for level in levels:
            score = ROOT/'blast_processing_original_best.txt' if level['id'] == 17 else ROOT/f"assets/progress/{level['id']}.txt"
            try: self.bests[level['id']] = max(0, min(100, float(score.read_text())))
            except (OSError, ValueError): self.bests[level['id']] = 0
        try: self.report = {r['id']: r for r in json.loads((ROOT/'reference/compatibility_report.json').read_text())}
        except (OSError, ValueError): self.report = {}
        self.background = self.image('game_bg_01_001.png', (1280, 1280)).copy()
        self.background.fill((25, 100, 230, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self.ground = self.image('groundSquare_01_001.png', (512, 512)).copy()
        self.ground.fill((35, 110, 245, 255), special_flags=pygame.BLEND_RGBA_MULT)

    def image(self, name, size):
        key = name, size
        if key not in self.images:
            self.images[key] = pygame.transform.smoothscale(pygame.image.load(str(asset_paths.texture(name))).convert_alpha(), size)
        return self.images[key]

    def title(self, value, center, scale=1., color=(255, 255, 255)):
        key = value, scale, color
        if key not in self.texts:
            text = self.font.render(value, color, scale)
            shadow = self.font.render(value, (0, 24, 65), scale)
            self.texts[key] = text, shadow
        text, shadow = self.texts[key]
        rect = text.get_rect(center=center)
        self.screen.blit(shadow, rect.move(3, 4)); self.screen.blit(text, rect)

    def label(self, value, center, color=(218, 238, 255)):
        image = self.small.render(value, True, color)
        self.screen.blit(image, image.get_rect(center=center))

    def button(self, action, center, name=None, size=(84, 84), label=None):
        rect = pygame.Rect(0, 0, *size); rect.center = center
        self.buttons.append((rect, action))
        hovered = rect.collidepoint(pygame.mouse.get_pos())
        if name:
            image = self.image(name, size)
            if hovered:
                image = pygame.transform.smoothscale(image, (round(size[0]*1.06), round(size[1]*1.06)))
            self.screen.blit(image, image.get_rect(center=center))
        else:
            pygame.draw.rect(self.screen, (40, 170, 57) if hovered else (30, 134, 44), rect, border_radius=12)
            pygame.draw.rect(self.screen, (12, 45, 35), rect, 3, border_radius=12)
            pygame.draw.rect(self.screen, (166, 244, 117), rect.inflate(-8, -8), 2, border_radius=9)
        if label:
            if name: self.label(label, (center[0], rect.bottom+20))
            else: self.title(label, center, .65)

    def draw(self, elapsed):
        self.buttons = []
        self.screen.fill((0, 77, 185))
        self.screen.blit(self.background, (0, -360))
        # Only the ground scrolls: static artwork and cached text stay inexpensive.
        offset = int(elapsed*42) % 512
        for x in range(-512, 1280, 512): self.screen.blit(self.ground, (x-offset, 625))
        pygame.draw.line(self.screen, (151, 220, 255), (0, 624), (1280, 624), 3)
        if self.view == 'home':
            self.screen.blit(self.image('GJ_logo_001.png', (840, 156)), (220, 78))
            self.button('levels', (640, 365), 'GJ_playBtn_001.png', (178, 178), 'PLAY')
            self.button('library', (925, 365), 'GJ_creatorBtn_001.png', (124, 124), 'LEVEL LIBRARY')
            self.button('appearance', (355, 365), 'GJ_garageBtn_001.png', (124, 124), 'GARAGE')
            self.button('stats', (482, 555), 'GJ_statsBtn_001.png', (65, 65))
            self.button('settings', (587, 555), 'GJ_optionsBtn_001.png', (65, 65))
            self.button('mute', (692, 555), 'GJ_musicOffBtn_001.png' if self.settings['muted'] else 'GJ_musicOnBtn_001.png', (65, 65))
            self.button('about', (797, 555), 'GJ_infoBtn_001.png', (65, 65))
            self.button('original', (1080, 670), size=(300, 50), label='Original game')
            self.label('vintage vuitton - earfzilla', (640, 678))
            self.label('ENTER: play    M: music    O: original game', (270, 678))
        else:
            self.button('back', (54, 54), 'GJ_backBtn_001.png', (62, 62))
            if self.view == 'levels': self.draw_level()
            elif self.view == 'library': self.draw_library()
            elif self.view == 'settings': self.draw_settings()
            elif self.view == 'appearance': self.draw_appearance()
            elif self.view == 'stats':
                self.title('Your progress', (640, 120), 1.6)
                self.title(f"{sum(v >= 100 for v in self.bests.values())} levels completed", (640, 270), 1.1)
                self.title(f"{sum(self.bests.values())/len(self.bests):.1f}% average best", (640, 360), 1.1)
                self.label('Local recreation progress. Original-game saves are separate.', (640, 460))
            else:
                self.title('GeoDash', (640, 130), 1.8)
                for y, text in enumerate(('Original artwork from your installed Geometry Dash.',
                    'Python recreation: original-input compatibility is still in progress.',
                    'A passing reference route does not prove every click pattern matches.',
                    'Tower movement and some later-level mechanics remain unfinished.',
                    'Use Original game to play with the installed native engine.')):
                    self.label(text, (640, 250+y*48))
                self.button('original', (640, 550), size=(300, 58), label='Original game')
            self.label('ESC: back    M: music    O: original game', (640, 678))
        if self.notice:
            pygame.draw.rect(self.screen, (12, 33, 61), (120, 584, 1040, 36), border_radius=8)
            self.label(self.notice, (640, 602), (255, 222, 132))

    def draw_level(self):
        level = self.levels[self.selected]
        rect = pygame.Rect(220, 120, 840, 420)
        pygame.draw.rect(self.screen, (13, 62, 129), rect, border_radius=24)
        pygame.draw.rect(self.screen, (103, 193, 255), rect, 3, border_radius=24)
        difficulty = DIFFICULTY[level['id']-1] if level['id'] <= 22 else 5
        self.screen.blit(self.image(f'difficulty_{difficulty:02}_btn_001.png', (86, 86)), (260, 154))
        self.title(level['name'], (690, 203), min(1.5, 660/max(1, self.font.render(level['name']).get_width())))
        self.title('Normal mode', (640, 288), .85, (175, 255, 158))
        progress = self.bests[level['id']]
        pygame.draw.rect(self.screen, (4, 30, 60), (315, 327, 650, 28), border_radius=14)
        if progress:
            pygame.draw.rect(self.screen, (69, 224, 55), (319, 331, max(1, round(642*progress/100)), 20), border_radius=10)
        self.label(f'{progress:.0f}%', (640, 341), (255, 255, 255))
        self.button('play', (640, 435), 'GJ_playBtn_001.png', (114, 114))
        verified = self.report.get(level['id'], {}).get('passed', False)
        self.label('Original reference route passes' if verified else 'Original input matching in progress', (640, 516), (175, 255, 158) if verified else (255, 220, 143))
        self.button('previous', (105, 330), size=(100, 86), label='<')
        self.button('next', (1175, 330), size=(100, 86), label='>')
        self.title(f'{self.selected+1} / {len(self.levels)}', (640, 567), .7)
        self.label('LEFT / RIGHT: select    ENTER: play', (640, 605))

    def draw_library(self):
        self.title('Level library', (640, 78), 1.3)
        for i, level in enumerate(self.levels):
            col, row = i % 3, i // 3
            self.button(('select', i), (265+col*375, 150+row*49), size=(350, 42), label=level['name'])

    def tinted_icon(self, stem, center, size):
        for suffix, color in (('_2_001.png', self.settings['secondary']),
                              ('_001.png', self.settings['primary'])):
            name=stem+suffix
            if not asset_paths.texture(name).is_file():continue
            key=(name,size,tuple(color))
            if key not in self.images:
                source=pygame.image.load(str(asset_paths.texture(name))).convert_alpha()
                scale=min(size[0]/source.get_width(),size[1]/source.get_height())
                image=pygame.transform.smoothscale(source,(max(1,round(source.get_width()*scale)),max(1,round(source.get_height()*scale))))
                image.fill((*color,255),special_flags=pygame.BLEND_RGBA_MULT)
                self.images[key]=image
            self.screen.blit(self.images[key],self.images[key].get_rect(center=center))

    def draw_appearance(self):
        self.title('Icon colors', (640, 100), 1.5)
        for i, stem in enumerate(('player_01','ship_01','player_ball_01','bird_01','dart_01')):
            x=360+i*140
            pygame.draw.circle(self.screen,(13,62,129),(x,245),56)
            self.tinted_icon(stem,(x,245),(82,82))
        for row, key in enumerate(('primary','secondary')):
            self.title(key.title(),(640,355+row*130),.85)
            for i, color in enumerate(PALETTE):
                rect=pygame.Rect(0,0,58,58);rect.center=(222+i*76,415+row*130)
                self.buttons.append((rect,('color',key,i)))
                pygame.draw.rect(self.screen,color,rect,border_radius=8)
                selected=list(color)==self.settings[key]
                pygame.draw.rect(self.screen,(255,255,255) if selected else (12,35,63),rect,4 if selected else 2,border_radius=8)
                if selected:
                    pygame.draw.circle(self.screen,(10,30,55),rect.center,12)
                    pygame.draw.lines(self.screen,(255,255,255),False,[(rect.centerx-7,rect.centery),(rect.centerx-2,rect.centery+5),(rect.centerx+8,rect.centery-6)],3)
        self.label('Colors apply to your icons and wave trail in the recreation.',(640,600))

    def draw_settings(self):
        self.title('Settings', (640, 125), 1.6)
        self.title('Menu music', (640, 245), 1.1)
        self.button('mute', (640, 335), size=(280, 62), label='Muted' if self.settings['muted'] else 'Music on')
        self.button('quieter', (420, 440), size=(80, 65), label='-')
        self.title(f"{round(self.settings['volume']*100)}%", (640, 440), 1.2)
        self.button('louder', (860, 440), size=(80, 65), label='+')
        self.label('vintage vuitton - earfzilla', (640, 535))

    def action(self, action):
        if isinstance(action, tuple):
            if action[0]=='color':
                self.settings=user_settings.save(**{action[1]:list(PALETTE[action[2]])})
            else:self.selected=action[1]; self.view='levels'
        elif action == 'back': self.view='home'; self.notice=''
        elif action in ('home', 'levels', 'library', 'settings', 'appearance', 'stats', 'about'): self.view=action; self.notice=''
        elif action in ('previous', 'next'):
            self.selected=(self.selected+(-1 if action=='previous' else 1)) % len(self.levels)
        elif action == 'mute': self.settings=user_settings.save(muted=not self.settings['muted'])
        elif action in ('quieter', 'louder'):
            self.settings=user_settings.save(volume=round(max(0, min(1, self.settings['volume']+(-.1 if action=='quieter' else .1))), 2))
        elif action == 'original':
            import original_game
            try: self.notice=original_game.launch()
            except (OSError, TimeoutError) as error: self.notice=str(error)
        elif action == 'play':
            if self.levels[self.selected]['platformer']:
                self.notice='Tower controls and triggers are still being implemented.'
            else:
                self.settings=user_settings.save(selected=self.levels[self.selected]['id'])
                return self.levels[self.selected]['id']
        return None

    def event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self.view == 'home': return 'quit'
                return self.action('back')
            if event.key in (pygame.K_RETURN, pygame.K_SPACE): return self.action('play' if self.view=='levels' else 'levels')
            actions={pygame.K_LEFT:'previous', pygame.K_RIGHT:'next', pygame.K_m:'mute', pygame.K_o:'original'}
            if event.key in actions: return self.action(actions[event.key])
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in self.buttons:
                if rect.collidepoint(event.pos): return self.action(action)
        return None


def main():
    levels=entries()
    if not levels:
        from blast_processing import main as play
        play(); return
    settings=user_settings.load()
    view='home'; notice=''
    while True:
        pygame.display.init(); pygame.font.init()
        display=app.Display(SIZE)
        pygame.display.set_caption('GeoDash | Official Levels')
        menu=Menu(display.screen, levels, settings)
        menu.view=view; menu.notice=notice
        music=menu_music.MenuMusic(settings)
        if music.error: menu.notice='Menu audio unavailable: '+music.error
        started=time.perf_counter(); launch=None
        while launch is None:
            start=time.perf_counter()
            for event in pygame.event.get():
                if event.type==pygame.QUIT:
                    music.stop(); pygame.quit(); return
                if event.type==pygame.WINDOWFOCUSLOST: music.focus(False)
                elif event.type==pygame.WINDOWFOCUSGAINED: music.focus(True)
                result=menu.event(event)
                music.settings=menu.settings; music.volume()
                if result=='quit':
                    music.stop(); pygame.quit(); return
                if isinstance(result, int): launch=result; break
            menu.draw(time.perf_counter()-started)
            display.present(start)
        music.stop()
        settings=menu.settings; view='levels'; notice=''
        from blast_processing import main as play
        play(launch)


if __name__=='__main__': main()

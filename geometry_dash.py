"""Launch the original-data Blast Processing recreation.

Run: .venv/bin/python geometry_dash.py
Use --classic for the earlier shape-only approximation.
Space / Up / left mouse: jump, flap, flip gravity, or hold to fly.
R: restart. P: practice. Left / Right: practice section. Escape: quit.
M: mute/unmute Waterflame's BlastProcess soundtrack.
"""

import math
import os
import time
from collections import deque
from functools import lru_cache
from pathlib import Path

os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
try:
    import pygame
except ModuleNotFoundError:
    raise SystemExit('Run .venv/bin/python geometry_dash.py (install requirements.txt first).')

WIDTH, HEIGHT = 960, 540
TOP, FLOOR = 105, 455
PLAYER_X = 190
SPEED = 360.0
LEVEL_LENGTH = 36000.0
FPS = 60
PHYSICS_DT = 1 / 240
CYAN, WHITE, PINK = (65, 235, 245), (238, 247, 255), (255, 85, 134)
SCORE_FILE = Path(__file__).with_name('blast_processing_best.txt')
MUSIC_FILE = Path(__file__).with_name('blast_processing.mp3')
# Percentages and mode order follow Blast Processing. Geometry is a shape-only
# approximation, not an export of RobTop's original level data.
SECTIONS = (
    (0, 'cube'), (14, 'wave'), (28, 'ship'), (35, 'ball'),
    (42, 'wave'), (49, 'dual wave'), (53, 'wave'), (58, 'cube'),
    (65, 'ufo'), (73, 'ship'), (76, 'ball'), (80, 'ufo'),
    (83, 'ship'), (87, 'cube'),
)
COLORS = {'cube': (70, 195, 240), 'wave': CYAN, 'dual wave': (255, 177, 72),
          'ship': (255, 100, 200), 'ball': (255, 110, 95), 'ufo': (160, 135, 255)}
PALETTES = ((47, 12, 92), (35, 87, 15), (16, 43, 96), (81, 13, 86),
            (66, 16, 93), (69, 14, 83), (40, 16, 88), (105, 39, 9),
            (10, 74, 54), (44, 13, 100), (82, 12, 75), (59, 13, 102),
            (85, 12, 83), (53, 11, 88))
GRAVITY_PORTALS = ((2100, -1), (3100, 1),
                   (LEVEL_LENGTH * .677, -1), (LEVEL_LENGTH * .704, 1))


def section_at(x):
    result = 0
    for i, (percent, _) in enumerate(SECTIONS):
        if x >= percent * LEVEL_LENGTH / 100:
            result = i
    return result


class Music:
    """Stream the soundtrack without loading the whole song into memory."""
    def __init__(self, path=None):
        self.enabled = False
        self.muted = False
        self.playing = self.paused = False
        self.attempt = None
        try:
            path = Path(path) if path is not None else MUSIC_FILE
            if not path.is_file():
                raise OSError('blast_processing.mp3 is missing')
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(0.55)
            self.enabled = True
        except (pygame.error, OSError) as error:
            print(f'Music unavailable: {error}. The game will run without audio.')

    def toggle_mute(self):
        self.muted = not self.muted
        if self.enabled:
            pygame.mixer.music.set_volume(0 if self.muted else 0.55)

    @property
    def status(self):
        if not self.enabled:
            return 'MUSIC UNAVAILABLE'
        return 'WATERFLAME / M: ' + ('UNMUTE' if self.muted else 'MUTE')

    def sync(self, game, focused=True):
        if not self.enabled:
            return
        try:
            if not game.started or game.dead or game.won:
                if self.playing:
                    pygame.mixer.music.stop()
                self.playing = self.paused = False
                self.attempt = None
                return
            if self.attempt != game.attempt:
                # MP3 seek uses seconds. Practice sections start at their own
                # elapsed level time; retrying from the beginning starts at 0.
                pygame.mixer.music.play(loops=0, start=getattr(game, 'music_time', game.x / SPEED))
                self.attempt = game.attempt
                self.playing = True
                self.paused = False
            if not focused and not self.paused:
                pygame.mixer.music.pause()
                self.paused = True
            elif focused and self.paused:
                pygame.mixer.music.unpause()
                self.paused = False
        except pygame.error as error:
            pygame.mixer.music.stop()
            self.enabled = False
            self.playing = self.paused = False
            print(f'Music stopped: {error}. The game will continue without audio.')


class Hazard:
    """Static world geometry, with precise polygon collision and broad culling."""
    def __init__(self, points, kind='solid'):
        self.points = points
        self.kind = kind
        xs, ys = zip(*points)
        self.bounds = pygame.Rect(math.floor(min(xs)), math.floor(min(ys)),
                                  math.ceil(max(xs) - min(xs)), math.ceil(max(ys) - min(ys)))

    def hits(self, rect):
        if not self.bounds.colliderect(rect):
            return False
        # Separating axis theorem: rectangle vs convex obstacle polygon.
        corners = [(rect.left, rect.top), (rect.right, rect.top),
                   (rect.right, rect.bottom), (rect.left, rect.bottom)]
        axes = [(1, 0), (0, 1)]
        for a, b in zip(self.points, self.points[1:] + self.points[:1]):
            axes.append((a[1] - b[1], b[0] - a[0]))
        for ax, ay in axes:
            p = [x * ax + y * ay for x, y in self.points]
            q = [x * ax + y * ay for x, y in corners]
            if max(p) <= min(q) or max(q) <= min(p):
                return False
        return True


def rectangle(x, y, w, h):
    return Hazard([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


def saw(x, y, radius=25):
    # Convex collision hull; teeth are decorative and drawn outside this hull.
    return Hazard([(x + math.cos(i * math.tau / 16) * radius,
                    y + math.sin(i * math.tau / 16) * radius)
                   for i in range(16)], 'saw')


def build_level():
    """Fixed motifs: opening jumps, sloped wave tunnels, flight and gravity lanes."""
    hazards, rings = [], []
    for i, (percent, mode) in enumerate(SECTIONS):
        start = percent * LEVEL_LENGTH / 100
        end = SECTIONS[i + 1][0] * LEVEL_LENGTH / 100 if i + 1 < len(SECTIONS) else LEVEL_LENGTH
        if mode == 'cube':
            # Spikes, short raised platforms, and optional jump rings.
            for n, x in enumerate(range(int(start + 650), int(end - 380), 430)):
                count = 2 if n % 4 == 2 else 1
                for j in range(count):
                    left = x + j * 30
                    if n % 3 == 0:
                        hazards.append(saw(left + 18, FLOOR, 30))
                    else:
                        hazards.append(Hazard([(left, FLOOR), (left + 15, FLOOR - 36),
                                               (left + 30, FLOOR)], 'spike'))
                if n % 4 == 1:
                    hazards.append(rectangle(x + 40, FLOOR - 48, 90, 48))
                    rings.append((x + 85, FLOOR - 115, 'jump'))
        elif 'wave' in mode:
            # Connected 45-degree slopes, spacious enough for deliberate zigzags.
            dual = mode == 'dual wave'
            centers = [280, 280, 370, 280, 190, 280, 280, 190, 280, 370, 280]
            x, n = start + 500, 0
            while x < end - 400:
                width = min(180, end - 400 - x)
                c1 = 280 if dual else centers[n % len(centers)]
                c2 = 280 if dual else centers[(n + 1) % len(centers)]
                half = 160 if dual else 88
                hazards.append(Hazard([(x, TOP), (x + width, TOP),
                                       (x + width, c2 - half), (x, c1 - half)]))
                hazards.append(Hazard([(x, c1 + half), (x + width, c2 + half),
                                       (x + width, FLOOR), (x, FLOOR)]))
                x += width
                n += 1
            if dual:
                for x in range(int(start + 480), int(end - 180), 340):
                    # Leave a usable lane for each mirrored wave. The taller
                    # diamonds previously forced unusually rapid reversals.
                    hazards.append(Hazard([(x - 110, 280), (x, 228),
                                           (x + 110, 280), (x, 332)], 'diamond'))
        elif mode in ('ship', 'ufo'):
            for n, x in enumerate(range(int(start + 530), int(end - 350), 290)):
                center = (245, 300, 265, 315)[n % 4]
                half = 103 if mode == 'ship' else 112
                hazards.extend([rectangle(x, TOP, 52, center - half - TOP),
                                rectangle(x, center + half, 52, FLOOR - center - half)])
                if mode == 'ship' and n % 2 == 1:
                    hazards.append(saw(x + 150, TOP + 35 if n % 4 == 1 else FLOOR - 35, 22))
        else:  # Ball: alternate floor and ceiling spikes; tap to reverse gravity.
            for n, x in enumerate(range(int(start + 500), int(end - 300), 360)):
                if n % 2 == 0:
                    hazards.append(Hazard([(x, FLOOR), (x + 26, FLOOR - 48),
                                           (x + 52, FLOOR)], 'spike'))
                else:
                    hazards.append(Hazard([(x, TOP), (x + 26, TOP + 48),
                                           (x + 52, TOP)], 'spike'))
                rings.append((x - 100, 280, 'gravity'))
    # A gravity change needs room to cross the playfield before the next hazard.
    # In particular, the return-to-floor portal previously dropped the cube
    # directly onto saws before it could land and jump again.
    hazards = [h for h in hazards if not any(
        h.bounds.right > x - 100 and h.bounds.left < x + 420
        for x, _ in GRAVITY_PORTALS)]
    return sorted(hazards, key=lambda h: h.bounds.left), rings


class Game:
    def __init__(self):
        self.hazards, self.rings = build_level()
        self.gravity_portals = GRAVITY_PORTALS
        self.buckets = {}
        for hazard in self.hazards:
            for cell in range(hazard.bounds.left // 480, hazard.bounds.right // 480 + 1):
                self.buckets.setdefault(cell, []).append(hazard)
        try:
            self.best = max(0.0, min(100.0, float(SCORE_FILE.read_text())))
        except (OSError, ValueError):
            self.best = 0.0
        self.practice = False
        self.attempt = 0
        self.reset()

    def reset(self, section=0):
        self.attempt += 1
        self.x = SECTIONS[section][0] * LEVEL_LENGTH / 100
        self.section = section
        self.mode = SECTIONS[section][1]
        self.vy = 0.0
        self.gravity = 1
        self.y = FLOOR - 14 if self.mode in ('cube', 'ball') else (TOP + FLOOR) / 2
        self.started = False
        self.dead = self.won = False
        self.grounded = self.mode in ('cube', 'ball')
        self.trail = deque(maxlen=150)
        self.used_rings = set()
        self.pending_save = False

    @property
    def progress(self):
        return min(100, self.x / LEVEL_LENGTH * 100)

    def finish(self, won=False):
        self.won, self.dead = won, not won
        if not self.practice and self.progress > self.best:
            self.best = self.progress
            self.pending_save = True

    def save_best(self):
        # Disk writes happen after rendering, never inside the physics update.
        if self.pending_save:
            try:
                SCORE_FILE.write_text(f'{self.best:.2f}')
            except OSError:
                pass
            self.pending_save = False

    def change_mode(self, index):
        previous = self.mode
        self.section, self.mode = index, SECTIONS[index][1]
        self.vy = 0
        self.gravity = 1
        self.grounded = False
        self.trail.clear()
        if self.mode in ('cube', 'ball'):
            self.y = FLOOR - 14
            self.grounded = True
        elif 'wave' not in previous or self.mode == 'dual wave':
            self.y = (TOP + FLOOR) / 2

    def visible_hazards(self):
        left, right = self.x - PLAYER_X, self.x + WIDTH - PLAYER_X
        seen = set()
        for cell in range(int(left // 480), int(right // 480) + 1):
            for hazard in self.buckets.get(cell, ()):
                if id(hazard) not in seen and hazard.bounds.right >= left and hazard.bounds.left <= right:
                    seen.add(id(hazard))
                    yield hazard

    def update(self, dt, holding=False, pressed=False):
        if self.dead or self.won or not self.started:
            return
        old_x = self.x
        self.x += SPEED * dt
        section = section_at(self.x)
        if section != self.section:
            self.change_mode(section)
        for x, gravity in self.gravity_portals:
            if old_x < x <= self.x:
                self.gravity = gravity
                self.vy = 0
                self.grounded = False
        old_y = self.y
        mode = self.mode
        if 'wave' in mode:
            self.y += SPEED * dt * (-1 if holding else 1)
        elif mode == 'ship':
            self.vy = max(-390, min(390, self.vy + (-1050 if holding else 850) * dt))
            self.y += self.vy * dt
        else:
            if mode == 'cube':
                if pressed:
                    for index, (x, y, kind) in enumerate(self.rings):
                        if kind == 'jump' and index not in self.used_rings and abs(x - self.x) < 44 and abs(y - self.y) < 65:
                            self.vy = -670 * self.gravity
                            self.grounded = False
                            self.used_rings.add(index)
                            break
                if (holding or pressed) and self.grounded:
                    self.vy, self.grounded = -670 * self.gravity, False
            elif mode == 'ufo' and pressed:
                self.vy = -330 * self.gravity
            elif mode == 'ball' and pressed and self.grounded:
                self.gravity *= -1
                self.grounded = False
                self.vy = 100 * self.gravity
            elif mode == 'ball' and pressed:
                for index, (x, y, kind) in enumerate(self.rings):
                    if (kind == 'gravity' and index not in self.used_rings
                            and abs(x - self.x) < 44 and abs(y - self.y) < 65):
                        self.gravity *= -1
                        self.vy = 100 * self.gravity
                        self.used_rings.add(index)
                        break
            self.vy += (1900 if mode == 'cube' else 1150) * self.gravity * dt
            self.y += self.vy * dt

        radius = 8 if 'wave' in mode else 12
        if self.y - radius < TOP or self.y + radius > FLOOR:
            if mode in ('wave', 'dual wave', 'ufo'):
                self.finish()
                return
            self.y = max(TOP + radius, min(FLOOR - radius, self.y))
            self.vy = 0
            self.grounded = True
        elif mode in ('cube', 'ball'):
            self.grounded = False

        rect = pygame.Rect(round(self.x - radius), round(self.y - radius), radius * 2, radius * 2)
        twin = rect.copy()
        twin.centery = round(TOP + FLOOR - self.y)
        nearby = {}
        for cell in range(rect.left // 480, rect.right // 480 + 1):
            for hazard in self.buckets.get(cell, ()):
                nearby[id(hazard)] = hazard
        for hazard in nearby.values():
            if not hazard.hits(rect) and not (mode == 'dual wave' and hazard.hits(twin)):
                continue
            # Cubes can land on the top of rectangular blocks.
            if (mode == 'cube' and hazard.kind == 'solid'
                    and self.gravity == 1
                    and old_y + radius <= hazard.bounds.top + 1 and self.vy >= 0):
                self.y = hazard.bounds.top - radius
                self.vy = 0
                self.grounded = True
            elif (mode == 'cube' and hazard.kind == 'solid' and self.gravity == -1
                  and old_y - radius >= hazard.bounds.bottom - 1 and self.vy <= 0):
                self.y = hazard.bounds.bottom + radius
                self.vy = 0
                self.grounded = True
            else:
                self.finish()
                return
        self.trail.append((self.x, self.y))
        if self.x >= LEVEL_LENGTH:
            self.finish(won=True)


class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.fonts = [pygame.font.Font(None, size) for size in (23, 30, 54)]
        self.backgrounds = []
        for base in PALETTES:
            background = pygame.Surface((WIDTH, HEIGHT)).convert()
            background.fill((12, 16, 32))
            background.set_clip(pygame.Rect(0, TOP, WIDTH, FLOOR - TOP))
            for y in range(TOP, FLOOR):
                factor = 0.65 + (y - TOP) / (FLOOR - TOP) * 0.55
                pygame.draw.line(background, tuple(int(c * factor) for c in base), (0, y), (WIDTH, y))
            for row in range(3):
                for col in range(8):
                    cx, cy = col * 150 + (row % 2) * 75, TOP + row * 140
                    points = [(cx + math.cos(i * math.tau / 6) * 67,
                               cy + math.sin(i * math.tau / 6) * 67) for i in range(6)]
                    pygame.draw.polygon(background, tuple(min(255, int(c * 1.3)) for c in base), points, 3)
            background.set_clip(None)
            self.backgrounds.append(background)
        self.frames = deque(maxlen=120)

    @lru_cache(maxsize=256)
    def text_surface(self, text, size, color):
        return self.fonts[size].render(text, True, color)

    def text(self, text, x, y, size=0, color=WHITE, center=False):
        surface = self.text_surface(text, size, color)
        rect = surface.get_rect(center=(x, y)) if center else surface.get_rect(topleft=(x, y))
        self.screen.blit(surface, rect)

    def icon(self, mode, y, holding, color, inverted=False):
        screen, x = self.screen, PLAYER_X
        y = round(y)
        if 'wave' in mode:
            direction = -1 if holding else 1
            if inverted:
                direction *= -1
            points = [(x + 12, y + direction * 9), (x - 10, y), (x, y - direction * 9)]
            pygame.draw.polygon(screen, color, points)
            pygame.draw.polygon(screen, WHITE, points, 2)
        elif mode == 'ball':
            pygame.draw.circle(screen, color, (x, y), 14)
            pygame.draw.circle(screen, WHITE, (x, y), 14, 2)
            pygame.draw.circle(screen, (15, 25, 45), (x, y), 6)
        elif mode == 'ship':
            points = [(x - 17, y - 9), (x + 18, y), (x - 17, y + 10), (x - 10, y)]
            pygame.draw.polygon(screen, color, points)
            pygame.draw.polygon(screen, WHITE, points, 2)
            if holding:
                pygame.draw.polygon(screen, (255, 180, 70), [(x - 15, y - 5), (x - 30, y), (x - 15, y + 5)])
        elif mode == 'ufo':
            pygame.draw.ellipse(screen, color, (x - 11, y - 13, 22, 20))
            pygame.draw.ellipse(screen, WHITE, (x - 19, y - 2, 38, 12), 3)
        else:
            pygame.draw.rect(screen, color, (x - 14, y - 14, 28, 28))
            pygame.draw.rect(screen, WHITE, (x - 14, y - 14, 28, 28), 2)
            pygame.draw.rect(screen, (12, 20, 42), (x - 7, y - 6, 5, 5))
            pygame.draw.rect(screen, (12, 20, 42), (x + 3, y - 6, 5, 5))

    def draw(self, game, holding, fps):
        screen = self.screen
        screen.blit(self.backgrounds[game.section], (0, 0))
        color = COLORS[game.mode]
        camera = game.x - PLAYER_X
        for hazard in game.visible_hazards():
            points = [(round(x - camera), round(y)) for x, y in hazard.points]
            pygame.draw.polygon(screen, (16, 13, 33), points)
            pygame.draw.polygon(screen, PINK if hazard.kind == 'spike' else color, points, 2)
            if hazard.kind == 'saw':
                cx = round(hazard.bounds.centerx - camera)
                cy = hazard.bounds.centery
                radius = hazard.bounds.width / 2
                teeth = [(cx + math.cos(i * math.tau / 32) * (radius + (5 if i % 2 else 0)),
                          cy + math.sin(i * math.tau / 32) * (radius + (5 if i % 2 else 0)))
                         for i in range(32)]
                pygame.draw.polygon(screen, WHITE, teeth, 2)
                pygame.draw.circle(screen, PINK, (cx, cy), max(3, round(radius / 2)))
            if hazard.kind == 'diamond':
                pygame.draw.polygon(screen, (38, 113, 143), [points[0], points[2], points[3]])
                pygame.draw.line(screen, CYAN, points[0], points[2], 2)
            if hazard.kind == 'solid' and hazard.bounds.width < 150:
                # Offset edges provide the original's simple 3D block treatment.
                box = hazard.bounds.move(-round(camera), 0).inflate(-12, -12)
                if box.width > 0 and box.height > 0:
                    pygame.draw.rect(screen, (63, 66, 102), box, 1)
                    if game.mode == 'ufo' and box.height > 28:
                        eye_y = box.centery - 13
                        for eye_x in (box.centerx - 12, box.centerx + 5):
                            pygame.draw.rect(screen, CYAN, (eye_x, eye_y, 8, 8), 2)
                        pygame.draw.rect(screen, CYAN, (box.centerx - 12, eye_y + 18, 25, 7), 2)
        for x, y, kind in game.rings:
            if -30 < x - camera < WIDTH + 30:
                pygame.draw.circle(screen, CYAN if kind == 'gravity' else (255, 218, 75),
                                   (round(x - camera), y), 17, 3)
                pygame.draw.circle(screen, WHITE, (round(x - camera), y), 7, 2)
        for percent, mode in SECTIONS[1:]:
            x = round(percent * LEVEL_LENGTH / 100 - camera)
            if -60 < x < WIDTH + 60:
                pygame.draw.ellipse(screen, COLORS[mode], (x - 17, TOP + 20, 34, FLOOR - TOP - 40), 4)
                self.text(mode.upper(), x, TOP + 10, color=COLORS[mode], center=True)
        for world_x, gravity in game.gravity_portals:
            x = round(world_x - camera)
            if -40 < x < WIDTH + 40:
                portal_color = (255, 220, 65) if gravity == -1 else CYAN
                pygame.draw.ellipse(screen, portal_color, (x - 13, TOP + 45, 26, FLOOR - TOP - 90), 3)
                self.text('UP' if gravity == -1 else 'DOWN', x, TOP + 34,
                          color=portal_color, center=True)
        pygame.draw.line(screen, color, (0, TOP), (WIDTH, TOP), 2)
        pygame.draw.line(screen, color, (0, FLOOR), (WIDTH, FLOOR), 2)
        if 'wave' in game.mode and len(game.trail) > 1:
            points = [(round(x - camera), round(y)) for x, y in game.trail if x - camera >= -5]
            if len(points) > 1:
                pygame.draw.lines(screen, (26, 90, 110), False, points, 7)
                pygame.draw.lines(screen, color, False, points, 3)
                if game.mode == 'dual wave':
                    pygame.draw.lines(screen, (255, 180, 70), False,
                                      [(x, TOP + FLOOR - y) for x, y in points], 3)
        self.icon(game.mode, game.y, holding, color)
        if game.mode == 'dual wave':
            self.icon(game.mode, TOP + FLOOR - game.y, holding, (255, 180, 70), True)
        self.text('BLAST PROCESSING', 24, 16, 1, color)
        self.text('SHAPE RECREATION', 25, 49, color=(145, 159, 185))
        self.text(f'{game.progress:5.1f}%', 445, 20, 1)
        self.text(f'BEST {game.best:.1f}%', 620, 21)
        self.text(f'{fps:4.0f} / 60 FPS', 808, 21, color=CYAN)
        pygame.draw.rect(screen, (36, 48, 75), (24, 83, 912, 5))
        pygame.draw.rect(screen, color, (24, 83, round(912 * game.progress / 100), 5))
        self.text(f'{game.mode.upper()}  /  ATTEMPT {game.attempt}' + ('  /  PRACTICE' if game.practice else ''),
                  24, 470, color=color)
        self.text('SPACE / UP / MOUSE   action     R restart    P practice    ESC quit',
                  WIDTH // 2, 514, center=True)
        if not game.started or game.dead or game.won:
            panel = pygame.Rect(210, 170, 540, 185)
            pygame.draw.rect(screen, (14, 20, 40), panel, border_radius=12)
            pygame.draw.rect(screen, color, panel, 2, border_radius=12)
            title = 'LEVEL COMPLETE!' if game.won else 'CRASHED' if game.dead else 'READY?'
            self.text(title, 480, 211, 2, color, True)
            hint = {'cube': 'Hold to jump. Tap near yellow rings for a boost.',
                    'wave': 'Hold to rise. Release to dive. Avoid every surface.',
                    'dual wave': 'Two mirrored waves. Keep both clear of the walls.',
                    'ship': 'Hold for thrust. Release to descend.',
                    'ball': 'Tap while on a surface to reverse gravity.',
                    'ufo': 'Tap repeatedly to flap. Holding does not repeat.'}[game.mode]
            self.text(hint, 480, 264, center=True)
            self.text('R to retry' if game.dead or game.won else 'Press SPACE / UP / click to start',
                      480, 302, 1, center=True)
            if game.practice:
                self.text('LEFT / RIGHT: choose section', 480, 333, center=True)


_frame_sleep_guard = .005


def pace_frame(frame_start):
    """Maintain 60 FPS while adapting to the OS timer's sleep overshoot."""
    global _frame_sleep_guard
    deadline = frame_start + 1 / FPS
    remaining = deadline - time.perf_counter()
    if remaining > _frame_sleep_guard:
        requested = remaining - _frame_sleep_guard
        before_sleep = time.perf_counter()
        time.sleep(requested)
        overshoot = max(0, time.perf_counter()-before_sleep-requested)
        # Rise immediately on a late wake; relax slowly when timers improve.
        # The final trim is typically under 1 ms rather than a fixed 5 ms spin.
        _frame_sleep_guard = min(.006, max(.001, overshoot+.00075,
                                          _frame_sleep_guard*.97))
    while time.perf_counter() < deadline:
        pass


class Display:
    """Upload the software drawing surface through SDL's VSync renderer."""
    def __init__(self, size=None):
        size=size or (WIDTH,HEIGHT)
        self.synchronized = pygame.display.get_driver() not in ('dummy', 'offscreen')
        if self.synchronized:
            try:
                # SCALED selects SDL's renderer; vsync on a plain Surface display
                # is ignored. SDL also maps mouse coordinates to our 960x540 canvas.
                self.screen = pygame.display.set_mode(size,
                                                      pygame.SCALED, vsync=1)
            except pygame.error as error:
                print(f'VSync renderer unavailable: {error}. Using software display.')
                self.synchronized = False
        if not self.synchronized:
            self.screen = pygame.display.set_mode(size)

    def present(self, frame_start):
        if self.synchronized:
            # Arrive before the next refresh, leaving time for SDL's texture
            # upload. Waiting a full 16.67 ms before a blocking swap can miss it
            # and halve the frame rate. This also caps faster displays near 60.
            pace_frame(frame_start - .003)
            pygame.display.flip()
        else:
            pygame.display.flip()
            pace_frame(frame_start)


def main():
    pygame.display.init()
    pygame.font.init()
    display = Display()
    screen = display.screen
    pygame.display.set_caption('Blast Processing | Shape Recreation | 60 FPS')
    renderer, game = Renderer(screen), Game()
    music = Music()
    held = set()
    accumulator = 0.0
    pending_press = False
    running = True
    focused = True
    previous_frame = time.perf_counter() - 1 / FPS
    while running:
        # Read events immediately before physics; keep short taps even if down/up
        # arrive together. Never replay a long backlog after dragging the window.
        frame_start = time.perf_counter()
        frame_duration = frame_start - previous_frame
        previous_frame = frame_start
        renderer.frames.append(frame_duration)
        measured_fps = len(renderer.frames) / max(sum(renderer.frames), 0.001)
        elapsed = min(frame_duration, 1 / 30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.WINDOWFOCUSLOST:
                focused = False
                held.clear()
                pending_press = False
                accumulator = 0
            elif event.type == pygame.WINDOWFOCUSGAINED:
                focused = True
                elapsed = 0
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_SPACE, pygame.K_UP):
                    if event.key not in held:
                        pending_press = True
                    held.add(event.key)
                    game.started = True
                elif event.key == pygame.K_r:
                    game.reset(game.section if game.practice else 0)
                    accumulator = 0
                    pending_press = False
                elif event.key == pygame.K_m:
                    music.toggle_mute()
                elif event.key == pygame.K_p:
                    game.practice = not game.practice
                    game.reset(game.section if game.practice else 0)
                    accumulator = 0
                    pending_press = False
                elif game.practice and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    step = 1 if event.key == pygame.K_RIGHT else -1
                    game.reset((game.section + step) % len(SECTIONS))
                    accumulator = 0
                    pending_press = False
            elif event.type == pygame.KEYUP:
                held.discard(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                held.add('mouse')
                pending_press = True
                game.started = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                held.discard('mouse')
        music.sync(game, focused)
        if focused:
            accumulator += elapsed
            while accumulator >= PHYSICS_DT:
                game.update(PHYSICS_DT, bool(held), pending_press)
                pending_press = False
                accumulator -= PHYSICS_DT
        # Stop promptly on a collision or completion in this physics frame.
        if game.dead or game.won:
            music.sync(game, focused)
        renderer.draw(game, bool(held), measured_fps)
        renderer.text(music.status, 620, 54, color=CYAN)
        if not focused:
            renderer.text('PAUSED — click the window to resume', 480, 390, center=True)
        game.save_best()
        display.present(frame_start)
    pygame.quit()


# Sample reflection — personalize this to describe your own experience:
# The hardest part was making each game mode respond differently to the same input.
# Fixed physics steps helped keep collisions consistent when frames took longer.
# I am proud of the portals and mirrored dual wave because they make the course varied.
# Building a fixed layout also made it possible to practice and learn each section.
if __name__ == '__main__':
    import sys
    if '--classic' in sys.argv:
        main()
    else:
        import argparse
        parser=argparse.ArgumentParser(description='GeoDash original-level recreation')
        parser.add_argument('--level',type=int,help='Open a particular original level (1–22, 3001).')
        parser.add_argument('--original',action='store_true',help='Open the installed Geometry Dash engine.')
        args=parser.parse_args()
        if args.original:
            import original_game
            try:print(original_game.launch())
            except OSError as error:parser.exit(1,str(error)+'\n')
        elif args.level is not None:
            from blast_processing import main as play
            play(args.level)
        else:
            from level_browser import main as library
            library()

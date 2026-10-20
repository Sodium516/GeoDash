"""Audit unchanged original inputs; --classic verifies the earlier shape course.

An original-input failure reports an outstanding compatibility mismatch.
The separate classic controller generates a recreation-specific route.
"""
import argparse
import time
from dataclasses import dataclass

import geometry_dash as g


@dataclass(frozen=True)
class VerifiedRun:
    inputs: tuple
    changes: int
    min_dwell: int


def corridor(game, x):
    """Find the open vertical lane at a short look-ahead distance."""
    low, high = g.TOP + 22, g.FLOOR - 22
    for hazard in game.buckets.get(int(x // 480), ()):
        if hazard.kind != 'solid' or not hazard.bounds.left <= x <= hazard.bounds.right:
            continue
        ys = []
        for p, q in zip(hazard.points, hazard.points[1:] + hazard.points[:1]):
            if p[0] != q[0] and min(p[0], q[0]) <= x <= max(p[0], q[0]):
                ys.append(p[1] + (q[1] - p[1]) * (x - p[0]) / (q[0] - p[0]))
        if ys:
            if hazard.bounds.top <= g.TOP:
                low = max(low, max(ys) + 22)
            if hazard.bounds.bottom >= g.FLOOR:
                high = min(high, min(ys) - 22)
    return low, high


def choose_input(game, previous):
    mode = game.mode
    if 'wave' in mode:
        low, high = corridor(game, game.x + 50)
        target = 170 if mode == 'dual wave' else (low + high) / 2
        if game.y > target + 24:
            return True
        if game.y < target - 24:
            return False
        return previous
    if mode in ('ship', 'ufo'):
        low, high = corridor(game, game.x + 90)
        target = (low + high) / 2
        if mode == 'ship':
            error = game.vy - (target - game.y) * 3
            if error > 70:
                return True
            if error < -70:
                return False
            return previous
        return (game.y - target) * game.gravity > 12 and game.vy * game.gravity > -30
    if mode == 'ball':
        for hazard in game.visible_hazards():
            if hazard.kind == 'spike' and 0 < hazard.bounds.left - game.x < 160:
                same_surface = ((game.gravity == 1 and hazard.bounds.bottom == g.FLOOR)
                                or (game.gravity == -1 and hazard.bounds.top == g.TOP))
                if same_surface:
                    return game.grounded
        return False
    if game.gravity == -1:
        return False
    for hazard in game.visible_hazards():
        if (hazard.bounds.bottom >= g.FLOOR - 1
                and hazard.bounds.right - game.x > -15
                and hazard.bounds.left - game.x < 112):
            return game.grounded
    return False


def advance_frame(game, holding, previous):
    """Exactly the four 240 Hz physics steps used by a 60 Hz gameplay frame."""
    for tick in range(4):
        game.update(g.PHYSICS_DT, holding, holding and not previous and tick == 0)
        if game.dead:
            raise AssertionError(f'Route died at {game.progress:.2f}% ({game.mode})')
        if game.won:
            break


def generate_run(minimum_dwell=12):
    game = g.Game()
    game.started = True
    previous, changed = False, -minimum_dwell
    inputs, changes = [], []
    for frame in range(round(g.LEVEL_LENGTH / g.SPEED * g.FPS) + 2):
        holding = choose_input(game, previous)
        # Each hold AND each release lasts at least 200 ms by default. This rules out
        # frame-perfect oscillation as the only way to navigate a passage.
        if frame - changed < minimum_dwell:
            holding = previous
        if holding != previous:
            changed = frame
            changes.append(frame)
        inputs.append(holding)
        advance_frame(game, holding, previous)
        previous = holding
        if game.won:
            dwell = min(b - a for a, b in zip(changes, changes[1:]))
            return VerifiedRun(tuple(inputs), len(changes), dwell)
    raise AssertionError('The controller did not complete the course')


def replay(run):
    """Start over and replay recorded inputs without consulting the controller."""
    game = g.Game()
    game.started = True
    previous = False
    visited = {game.mode}
    for holding in run.inputs:
        advance_frame(game, holding, previous)
        previous = holding
        visited.add(game.mode)
    assert game.won and not game.dead and game.progress == 100
    assert visited == {mode for _, mode in g.SECTIONS}
    assert game.attempt == 1 and not game.practice
    return game


def watch(run):
    pygame = g.pygame
    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode((g.WIDTH, g.HEIGHT))
    pygame.display.set_caption('Verified 100% run | normal physics and collisions')
    renderer, game = g.Renderer(screen), g.Game()
    music = g.Music()
    game.started = True
    previous, frame = False, 0
    while True:
        start = time.perf_counter()
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                pygame.quit()
                return
            if event.type == pygame.KEYDOWN and event.key == pygame.K_m:
                music.toggle_mute()
        music.sync(game)
        holding = run.inputs[frame] if frame < len(run.inputs) else previous
        if frame < len(run.inputs):
            advance_frame(game, holding, previous)
            frame += 1
        if game.won:
            music.sync(game)
        previous = holding
        renderer.frames.append(time.perf_counter())
        fps = ((len(renderer.frames) - 1) / (renderer.frames[-1] - renderer.frames[0])
               if len(renderer.frames) > 1 else 60)
        renderer.draw(game, holding, fps)
        pygame.draw.rect(screen, (12, 16, 32), (20, 47, 900, 28))
        renderer.text('VERIFIED DEMO / NORMAL COLLISIONS', 25, 49, color=g.CYAN)
        renderer.text('HOLD' if holding else 'RELEASE', 808, 49, color=g.CYAN)
        pygame.display.flip()
        g.pace_frame(start)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--classic', action='store_true', help='Verify the earlier shape-only course.')
    parser.add_argument('--level', type=int, help='Audit a particular installed level.')
    args = parser.parse_args()
    if not args.classic:
        if args.watch:
            parser.error('--watch currently requires --classic; use audit_levels.py for original-input checks.')
        import audit_levels
        try:results=audit_levels.audit(args.level)
        except ValueError as error:parser.error(str(error))
        raise SystemExit(0 if results and all(r['passed'] for r in results) else 1)
    run = generate_run()
    replay(run)
    print(f'PASS: 0% to 100%, one attempt, all modes, no deaths or collision bypasses.\n'
          f'{len(run.inputs)} frames at 60 FPS; {run.changes} input changes; '
          f'shortest hold/release {run.min_dwell / g.FPS * 1000:.0f} ms.\n'
          'Recorded inputs also completed an independent replay. No high score was written.')
    if args.watch:
        watch(run)


if __name__ == '__main__':
    main()

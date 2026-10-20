"""Replay (or search for) a complete run of the original-data level.

The verifier sends hold/release inputs to the same simulation as normal play.
It never disables collisions, changes obstacles, skips modes, or moves the player.
"""
import argparse
import copy
import random
import time
from pathlib import Path

import blast_processing as b

ROUTE_FILE = b.ASSETS/'recreation_verified_run.bin'


def replay(inputs, level=None):
    level = level or b.Level()
    state = level.initial_state()
    previous = False
    modes = {state.mode}
    for frame, value in enumerate(inputs):
        if value not in (0, 1):
            raise AssertionError('Invalid recorded input')
        holding = bool(value)
        for tick in range(4):
            b.simulate(level,state,b.TICK,holding,holding and not previous and tick==0)
            if state.dead:
                raise AssertionError(f'Replay crashed at frame {frame}, {state.x/b.END_X*100:.2f}% ({state.mode})')
        previous=holding
        modes.add(state.mode)
    assert state.won and not state.dead, 'Replay did not reach the end'
    assert all(state.used & p.bit for p in level.portals), 'Replay bypassed a mode portal'
    assert modes == {'cube','wave','ship','ball','ufo'}
    return state


def search(level=None, progress=print):
    """Reachability search with deterministic pruning, on the real collision map."""
    level=level or b.Level()
    candidates=[(level.initial_state(),False,0,b'')]
    for frame in range(round(b.END_X/b.SPEED*60)+2):
        next_states={}
        x=(frame+1)*b.SPEED/60
        mask=0
        for obj in level.nearby(x,level.interactive_buckets,60):
            mask |= obj.bit
        required=0
        for portal in level.portals:
            if portal.x+70 < x:
                required |= portal.bit
        for state,previous,age,path in candidates:
            for holding in (False,True):
                if holding != previous and age < 2:
                    continue
                s=b.clone_state(state)
                for tick in range(4):
                    b.simulate(level,s,b.TICK,holding,holding and not previous and tick==0)
                    if s.dead:
                        break
                if s.dead or s.used & required != required:
                    continue
                age2=min(3,age+1) if holding==previous else 0
                key=(round(s.y/1.5),round(s.vy/.3),s.mode,s.gravity,
                     s.grounded,s.dual,holding,age2,s.used&mask,s.buffered,
                     None if s.twin is None else (round(s.twin.y/1.5),round(s.twin.vy/.3),
                                                   s.twin.gravity,s.twin.mode,s.twin.buffered))
                if key not in next_states:
                    next_states[key]=(s,holding,age2,path+bytes([holding]))
                if s.won:
                    result=path+bytes([holding])
                    replay(result,level)
                    return result
        if not next_states:
            raise AssertionError(f'No surviving route at {x/b.END_X*100:.2f}%')
        candidates=list(next_states.values())
        mode=candidates[0][0].mode
        budget=1200 if mode in ('ship','ufo') else 900 if mode=='wave' else 1800
        if len(candidates)>budget:
            random.Random(frame).shuffle(candidates)
            candidates=candidates[:budget]
        if frame%300==0:
            progress(f'Search: {x/b.END_X*100:.1f}% ({mode})',flush=True)
    raise AssertionError('Search did not finish')


def watch(inputs):
    pygame=b.pygame
    pygame.display.init();pygame.font.init()
    display=b.app.Display()
    screen=display.screen
    pygame.display.set_caption('Original Blast Processing | Verified replay')
    level=b.Level();game=b.Game(level);renderer=b.Renderer(screen,level)
    music=b.app.Music(b.ASSETS/'BlastProcessing.mp3')
    game.started=True
    previous=False
    frame=0
    paused=False
    focused=True
    last_frame=time.perf_counter()-1/60
    while True:
        start=time.perf_counter()
        frame_duration=start-last_frame
        last_frame=start
        renderer.frames.append(frame_duration)
        for event in pygame.event.get():
            if event.type==pygame.QUIT or (event.type==pygame.KEYDOWN and event.key==pygame.K_ESCAPE):
                pygame.quit()
                return
            if event.type==pygame.KEYDOWN and event.key==pygame.K_m:
                music.toggle_mute()
            elif event.type==pygame.KEYDOWN and event.key==pygame.K_TAB:
                paused=not paused
            elif (event.type==pygame.MOUSEBUTTONDOWN and event.button==1
                  and pygame.Rect(910,4,40,40).collidepoint(event.pos)):
                paused=not paused
            elif event.type==pygame.WINDOWFOCUSLOST:
                focused=False
            elif event.type==pygame.WINDOWFOCUSGAINED:
                focused=True
        active=focused and not paused
        music.sync(game,active)
        holding=bool(inputs[frame]) if frame<len(inputs) else previous
        if active and frame<len(inputs):
            for tick in range(4):
                game.update(b.TICK,holding,holding and not previous and tick==0)
                assert not game.dead, f'Replay died at {game.progress:.2f}%'
            frame+=1
            previous=holding
        if game.won:
            music.sync(game)
        fps=len(renderer.frames)/max(sum(renderer.frames),.001)
        renderer.draw(game,holding,frame_duration if active else 0,fps)
        renderer.text('REPLAY',120,8,color=(255,235,100))
        renderer.text('HOLD' if holding else 'RELEASE',420,516)
        if not active:
            renderer.draw_pause(focused)
        display.present(start)


def main(watch_run=False):
    inputs=ROUTE_FILE.read_bytes()
    result=replay(inputs)
    changes=sum(a!=c for a,c in zip(b'\0'+inputs,inputs))
    print(f'PASS: recreation-generated inputs clear original object layout 0–100%, all 13 mode/dual portals, '
          f'no deaths or collision bypasses. {len(inputs)} frames, '
          f'{changes} input changes. No high score written.')
    if watch_run:
        watch(inputs)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch',action='store_true')
    parser.add_argument('--search',action='store_true',help='Regenerate the recorded route; can take several minutes.')
    args=parser.parse_args()
    if args.search:
        ROUTE_FILE.write_bytes(search())
    main(args.watch)

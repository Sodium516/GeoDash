"""Read unmodified GDR2 recordings for physics compatibility checks.

Format reference: https://github.com/maxnut/GDReplayFormat/tree/gdr2
No position corrections or frame fixes are applied to the simulation.
"""
import math
import re
import struct
from dataclasses import dataclass
from pathlib import Path


class Reader:
    def __init__(self,data):
        self.data=data;self.offset=0
    def take(self,size):
        if size<0 or self.offset+size>len(self.data):raise ValueError('Truncated replay')
        value=self.data[self.offset:self.offset+size];self.offset+=size
        return value
    def integer(self):
        value=0
        for shift in range(0,70,7):
            byte=self.take(1)[0];value|=(byte&127)<<shift
            if byte<128:return value
        raise ValueError('Invalid replay integer')
    def text(self):
        length=self.integer()
        if length>65535:raise ValueError('Replay string is too long')
        return self.take(length).decode('utf-8')
    def number(self,fmt):return struct.unpack('>'+fmt,self.take(struct.calcsize(fmt)))[0]


@dataclass(frozen=True)
class Input:
    frame:int
    down:bool
    button:int=1
    player2:bool=False


@dataclass
class Replay:
    level_id:int
    name:str
    author:str
    rate:float
    duration:float
    inputs:list
    platformer:bool=False
    deaths:tuple=()
    source:str=''


def load(path):
    path=Path(path)
    if path.suffix=='.txt':
        inputs=[]
        for line in path.read_text().splitlines():
            match=re.fullmatch(r'input=(\d+),([01])',line)
            if not match:raise ValueError('Invalid input plan line')
            inputs.append(Input(int(match[1]),match[2]=='1'))
        match=re.fullmatch(r'solution_lv(\d+)_(?:dp|coins)',path.stem)
        if match is None:raise ValueError('Input plan needs a level identifier')
        return Replay(int(match[1]),path.stem,'gdsolver authors',240.,
                      max((i.frame for i in inputs),default=0)/240.,inputs,source=str(path))
    r=Reader(Path(path).read_bytes())
    if r.take(3)!=b'GDR' or r.integer()!=2:raise ValueError('Expected GDR version 2')
    tag=r.text();author=r.text();description=r.text()
    duration=r.number('f');game_version=r.integer();rate=r.number('d')
    seed=r.integer();coins=r.integer();ldm=r.integer();platformer=bool(r.integer())
    bot=r.text();bot_version=r.integer();level_id=r.integer();name=r.text()
    r.take(r.integer())
    deaths=[];frame=0
    for _ in range(r.integer()):
        frame+=r.integer();deaths.append(frame)
    count=r.integer();p1_count=r.integer()
    if p1_count>count or count>10000000:raise ValueError('Invalid input count')
    if not math.isfinite(rate) or not 1<=rate<=100000:raise ValueError('Invalid replay rate')
    inputs=[];frame=0
    for index in range(count):
        if index==p1_count:frame=0
        packed=r.integer();frame+=packed>>(3 if platformer else 1)
        inputs.append(Input(frame,bool(packed&1),(packed>>1)&3 if platformer else 1,index>=p1_count))
        if tag:r.take(r.integer())
    if r.offset!=len(r.data):raise ValueError('Unexpected trailing replay data')
    return Replay(level_id,name,author,rate,duration,sorted(inputs,key=lambda i:i.frame),platformer,tuple(deaths),str(path))


def run(replay,level,trace=False,game=None):
    import blast_processing as b
    state=level.initial_state() if game is None else game.state
    events={}
    for event in replay.inputs:events.setdefault(event.frame,[]).append(event)
    holding=False
    held_streams={False:False,True:False}
    two_player=level.settings.get('kA10')=='1'
    last_input=max(events,default=0)
    maximum=max(round(replay.duration*replay.rate),last_input)+round(5*replay.rate)
    history=[]
    for frame in range(maximum):
        pressed=False
        for event in events.get(frame,()):
            # Native handleButton queues both streams for the same player
            # unless two-player mode is enabled. A release on either stream
            # releases that shared button; they are not independent held keys.
            if event.button==1:
                held_streams[event.player2 if two_player else False]=event.down
                pressed|=event.down
        holding=any(held_streams.values())
        dt=1/replay.rate
        steps=max(1,math.ceil(dt/b.TICK))
        for tick in range(steps):
            if game is None:b.simulate(level,state,dt/steps,holding,pressed and tick==0)
            else:game.update(dt/steps,holding,pressed and tick==0)
            if state.dead or state.won:break
        if trace:history.append((frame,state.x,state.y,state.vy,state.mode,state.gravity,holding))
        if state.dead or state.won:
            return dict(passed=state.won and not state.dead,frame=frame,x=state.x,y=state.y,
                        mode=state.mode,progress=min(100,state.x/level.end_x*100),trace=history)
    return dict(passed=False,frame=maximum,x=state.x,y=state.y,mode=state.mode,
                progress=min(100,state.x/level.end_x*100),trace=history)

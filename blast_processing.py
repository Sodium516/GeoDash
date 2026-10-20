"""Original Blast Processing data/texture player, in Geometry Dash world units.

The original level and textures were imported from the local Steam installation.
The independently implemented simulation approximates GD's classic 240 Hz rules.
"""
import base64
import bisect
import copy
import json
import math
import re
import struct
import time
import zlib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import geometry_dash as app
import asset_paths
import user_settings

pygame = app.pygame
ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets/original'
SCALE = 1.6
SPEED = 5.7700018882751465 * .9 * 60
TICK = 1 / 240
JUMP = 11.180031776428223
GRAVITY = .9581990242004395
Y_TIME = 54.0
END_X = 30900.0
BEST_FILE = ROOT/'blast_processing_original_best.txt'
MODE_PORTALS = {12:'cube',13:'ship',47:'ball',111:'ufo',660:'wave',745:'robot',1331:'spider',1933:'swing'}
SPEED_PORTALS = {200:.7,201:.9,202:1.1,203:1.3,1334:1.6}
SPEED_RULES = {.7:(5.980002,10.620032,.940199), .9:(5.7700018882751465,JUMP,GRAVITY),
               1.1:(5.870002,11.420032,.957199),1.3:(6.000002,11.230032,.961199),
               1.6:(6.000002,11.230032,.961199)}
COLOR_TRIGGERS = {29: 1000, 30: 1001, 104: 1002, 105: 1004,
                  221: 1, 717: 2, 718: 3, 743: 4, 744: 1003}
ORB_IDS, PAD_IDS = {36,84,141,1022,1330,1333,1704,1751,3004}, {35,67,140,1332}
PORTAL_IDS = set(MODE_PORTALS) | set(SPEED_PORTALS) | {10,11,45,46,99,101,286,287,747,2902}
SOLID_EDGE = (245, 242, 255)
DANGER = (245, 242, 255)
WALL_FILL = (9, 5, 18)


def transform(points, x, y, angle=0, flip_x=False, flip_y=False):
    rad = math.radians(-angle)
    c, s = math.cos(rad), math.sin(rad)
    result = []
    for px, py in points:
        px *= -1 if flip_x else 1
        py *= -1 if flip_y else 1
        result.append((x + px * c - py * s, y + px * s + py * c))
    return tuple(result)


def box_points(w, h):
    return ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))


@dataclass(frozen=True)
class Object:
    uid: int
    id: int
    x: float
    y: float
    angle: float
    flip_x: bool
    flip_y: bool
    type: int
    frame: str
    width: float
    height: float
    channel: int
    points: tuple
    bounds: tuple
    raw: dict
    bit: int = 0
    collision_radius: float = 0.
    axes: tuple = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        axes = []
        for a, b in zip(self.points, self.points[1:] + self.points[:1]):
            ax, ay = a[1] - b[1], b[0] - a[0]
            projections = [px * ax + py * ay for px, py in self.points]
            axes.append((ax, ay, min(projections), max(projections)))
        object.__setattr__(self, 'axes', tuple(axes))

    def intersects(self, x, y, rx, ry):
        left, bottom, right, top = self.bounds
        if x + rx < left or x - rx > right or y + ry < bottom or y - ry > top:
            return False
        # SAT between convex geometry and the player's axis-aligned hitbox.
        for ax, ay, minimum, maximum in self.axes:
            center = x * ax + y * ay
            extent = abs(ax) * rx + abs(ay) * ry
            if center + extent < minimum or center - extent > maximum:
                return False
        return True

    def edge_height(self, x, top=True):
        ys = []
        for a, b in zip(self.points, self.points[1:] + self.points[:1]):
            if a[0] != b[0] and min(a[0], b[0]) - .01 <= x <= max(a[0], b[0]) + .01:
                ys.append(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))
        return (max(ys) if top else min(ys)) if ys else None

    def intersects_rotated_player(self,x,y,half,rotation):
        # Native turned hazards first test bounding rectangles, then both
        # oriented boxes. The player's own angle matters at narrow corners.
        left,bottom,right,top=self.bounds
        if x+half<left or x-half>right or y+half<bottom or y-half>top:return False
        player=transform(box_points(half*2,half*2),x,y,-rotation,False,False)
        axes=[(ax,ay) for ax,ay,_,_ in self.axes]
        axes.extend((a[1]-b[1],b[0]-a[0]) for a,b in zip(player,player[1:]+player[:1]))
        for ax,ay in axes:
            own=[px*ax+py*ay for px,py in self.points]
            other=[px*ax+py*ay for px,py in player]
            if max(own)<min(other) or max(other)<min(own):return False
        return True


class Level:
    def __init__(self, level_id=17):
        from level_catalog import entry
        self.id=int(level_id)
        self.spec=entry(self.id) or dict(id=17,name='Blast Processing',song='BlastProcessing.mp3',
                                       background=5,ground=5,end_x=END_X,platformer=False)
        self.name=self.spec['name']
        self.end_x=self.spec['end_x']
        source=ROOT/f'assets/levels/{self.id}.txt'
        if not source.exists():
            if self.id!=17:raise FileNotFoundError(f'Level {self.id} has not been extracted')
            source=ROOT/'assets/blast_processing_level.txt'
        encoded = source.read_bytes().strip()
        raw = zlib.decompress(base64.urlsafe_b64decode(encoded + b'=' * (-len(encoded) % 4)), 31).decode()
        parts = raw.split(';')
        settings = parts[0].split(',')
        self.settings = dict(zip(settings[::2], settings[1::2]))
        self.metadata = json.loads((ASSETS / 'objects.json').read_text())
        geometry=json.loads((ROOT/'reference/collision_geometry.json').read_text())
        self.objects, self.buckets = [], defaultdict(list)
        self.collision_buckets, self.interactive_buckets = defaultdict(list), defaultdict(list)
        self.colors, self.portals = defaultdict(list), []
        interactive_index = 0
        initial = {1000: (71, 0, 210), 1001: (53, 0, 138), 1002: (255, 250, 250),
                   1004: (241, 236, 240), 1: (0, 255, 0), 2: (0, 0, 0),
                   3: (255, 255, 255), 4: (255, 255, 255), 1003: (0, 0, 0)}
        for key, channel in [('kS29', 1000), ('kS30', 1001), ('kS31', 1002), ('kS32', 1004),
                             ('kS33', 1), ('kS34', 2), ('kS35', 3), ('kS36', 4), ('kS37', 1003)]:
            fields = self.settings.get(key, '').split('_')
            d = dict(zip(fields[::2], fields[1::2]))
            if d:
                initial[channel] = tuple(int(d.get(str(k), 255)) for k in (1, 2, 3))
        self.channel_opacity={}
        for encoded_color in self.settings.get('kS38','').split('|'):
            if not encoded_color:continue
            fields=encoded_color.split('_');data=dict(zip(fields[::2],fields[1::2]))
            channel=int(data.get('6') or 1004)
            initial[channel]=tuple(int(data.get(str(k)) or 255) for k in (1,2,3))
            self.channel_opacity[channel]=float(data.get('7') or 1)
        raw_objects = [dict(zip(v[::2], v[1::2])) for part in parts[1:] if part for v in [part.split(',')]]
        self.raw_count = len(raw_objects)
        self.raw_objects = raw_objects
        self.initial_speed = (.9,.7,1.1,1.3,1.6)[min(4,int(self.settings.get('kA4') or 0))]
        self.speed_events=[(-1000.,self.initial_speed)]
        self.speed_events.extend(sorted((float(o['2']),SPEED_PORTALS[int(o['1'])])
                                       for o in raw_objects if int(o['1']) in SPEED_PORTALS))
        for uid, data in enumerate(raw_objects):
            id = int(data['1'])
            x, y = float(data['2']), float(data['3'])
            if id in COLOR_TRIGGERS or id==899:
                channel=COLOR_TRIGGERS[id] if id!=899 else int(data.get('23') or 1004)
                self.colors[channel].append((x, float(data.get('10', 0)),
                    tuple(int(data.get(str(k), 255)) for k in (7, 8, 9))))
            info = self.metadata.get(str(id))
            if info is None or (info['type'] == 20 and id not in SPEED_PORTALS):
                continue
            type = info['type']
            # Legacy perspective-outline pieces inherit type 0 in the factory
            # dump but are decorative; real collision blocks are separate.
            if 506 <= id <= 559 or info['frame'].startswith('persp_'):
                type = 7
            w, h = info.get('size', (30, 30))
            object_scale=float(data.get('32') or 1)
            angle = float(data.get('6', 0))
            fx, fy = data.get('4') == '1', data.get('5') == '1'
            # Native legacy aliases share textures but have different default colors.
            channel = int(data.get('21') or data.get('19') or 1004)
            if '19' not in data and '21' not in data:
                if id in {91, 92, 93, 309, 345} or 515 <= id <= 523:
                    channel = 1
                elif id in {94, 161, 162, 163, 165, 166, 167, 321} or 524 <= id <= 532:
                    channel = 2
                elif id in {343} or 533 <= id <= 541:
                    channel = 3
                elif 551 <= id <= 559:
                    channel = 1003
                elif id in {132, 133, 460, 494}:
                    channel = 1
            physical_w, physical_h = w, h
            if type in (0,21) and not 506 <= id <= 559:
                physical_w, physical_h = min(30,w), min(30,h)
            if id == 468:
                physical_w, physical_h = 30, 1.5
            if type == 25:
                if id in (366, 367):
                    half = 15 if id == 366 else 30
                    physical_w = half * 2
                    physical_h = 30
                    points = ((-half, -15), (half, 15), (half, 10), (-half, -20))
                else:
                    points = ((-w/2, -h/2), (w/2, -h/2), (w/2, h/2))
            elif type == 2:
                if any(t in info['frame'].lower() for t in ('wheel', 'blade')):
                    # The collision circle excludes the large transparent/glow
                    # margin in the cogwheel's atlas frame.
                    radius = min(w, h) * .22
                    points = tuple((math.cos(i * math.tau / 12) * radius,
                                    math.sin(i * math.tau / 12) * radius) for i in range(12))
                elif 'pit_' in info['frame']:
                    physical_h = 8 if id in (61, 243, 244, 368) else 12
                    points = box_points(w * .92, physical_h)
                else:
                    points = ((-w * .38, -h * .4), (w * .38, -h * .4), (0, h * .4))
            else:
                points = box_points(physical_w, physical_h)
            reference=geometry['boxes'].get(str(id))
            if reference and type!=25:
                height,width,left,bottom=reference
                if width>0 and height>0:
                    points=((left,bottom),(left+width,bottom),
                            (left+width,bottom+height),(left,bottom+height))
            radius=geometry['radii'].get(str(id))
            if radius and type in (2,47):
                points=tuple((math.cos(i*math.tau/24)*radius,math.sin(i*math.tau/24)*radius)
                             for i in range(24))
            points = transform(tuple((px*object_scale,py*object_scale) for px,py in points), x, y, angle, fx, fy)
            w,h=w*object_scale,h*object_scale
            xs, ys = zip(*points)
            bounds = min(xs), min(ys), max(xs), max(ys)
            bit = 0
            if id in PORTAL_IDS | ORB_IDS | PAD_IDS | {142}:
                bit = 1 << interactive_index
                interactive_index += 1
            obj = Object(uid, id, x, y, angle, fx, fy, type, info['frame'], w, h,
                         channel, points, bounds, data, bit, (radius or 0)*object_scale)
            self.objects.append(obj)
            for cell in range(math.floor(bounds[0] / 120), math.floor(bounds[2] / 120) + 1):
                self.buckets[cell].append(obj)
                if type in (0, 2, 21, 25, 47):
                    self.collision_buckets[cell].append(obj)
                if bit:
                    self.interactive_buckets[cell].append(obj)
            if id in MODE_PORTALS or id in (286, 287):
                self.portals.append(obj)
        self.portals.sort(key=lambda o: o.x)
        self.color_events, self.color_x = {}, {}
        for channel in self.colors:
            initial.setdefault(channel,(255,255,255))
        for channel, color in initial.items():
            events = [(-1000., 0., color, color)]
            for x, duration, target in sorted(self.colors[channel]):
                last_x, length, source, dest = events[-1]
                t = min(1,max(0,(self.time_at_x(x)-self.time_at_x(last_x))/length)) if length else 1
                current = tuple(round(a + (b-a)*t) for a, b in zip(source, dest))
                events.append((x, duration, current, target))
            self.color_events[channel] = events
            self.color_x[channel] = [e[0] for e in events]

    def initial_state(self):
        state=State(speed=self.initial_speed,mini=self.settings.get('kA3')=='1')
        state.x=-native_horizontal_delta(state.speed,TICK)
        state.y=9 if state.mini else 15
        state.mode=('cube','ship','ball','ufo','wave','robot','spider','swing')[min(7,int(self.settings.get('kA2') or 0))]
        if state.mode not in ('cube','robot','spider'):
            state.y=120 if state.mode=='ball' else 150
            state.ceiling=240 if state.mode=='ball' else 300
            state.grounded=False
        return state

    def time_at_x(self,x):
        result=0.;previous=0.;speed=self.initial_speed
        for position,new_speed in self.speed_events[1:]:
            if position>=x:break
            result+=(position-previous)/(SPEED_RULES[speed][0]*speed*60)
            previous,speed=position,new_speed
        return result+(x-previous)/(SPEED_RULES[speed][0]*speed*60)

    def color(self, channel, x):
        events = self.color_events.get(channel, self.color_events[1004])
        positions = self.color_x.get(channel, self.color_x[1004])
        start, length, a, b = events[bisect.bisect_right(positions, x) - 1]
        t = min(1,max(0,(self.time_at_x(x)-self.time_at_x(start))/length)) if length else 1
        return tuple(round(v + (w-v)*t) for v, w in zip(a, b))

    def nearby(self, x, table, radius=20):
        if int((x-radius)//120) == int((x+radius)//120):
            return table.get(int(x//120), ())
        return {obj.uid: obj for cell in range(int((x-radius)//120), int((x+radius)//120)+1)
                for obj in table.get(cell, ())}.values()


@dataclass
class State:
    x: float = 0.
    y: float = 15.
    vy: float = 0.
    gravity: int = 1  # 1 is downward, -1 upward; world Y points up.
    mode: str = 'cube'
    grounded: bool = True
    dual: bool = False
    used: int = 0
    touched_rings: tuple = ()
    ground_linger: bool = False
    boost: bool = False
    on_slope: bool = False
    slope_m: float = 0.
    slope_ceiling: bool = False
    slope_since: float = -1.
    slope_target: float = 0.
    dead: bool = False
    won: bool = False
    rotation: float = 0.
    buffered: bool = False
    input_held: bool = False
    floor: float = 0.
    ceiling: float = 300.
    mini: bool = False
    speed: float = .9
    time: float = 0.
    mirror: bool = False
    robot_hold: float = 0.
    robot_jumping: bool = False
    dashing: bool = False
    dash_angle: float = 0.
    twin: object = field(default=None,repr=False,compare=False)
    snap_uid: int = -1
    snap_type: int = 0
    snap_x: float = 0.
    snap_y: float = 0.
    snap_offset: float = 0.


def native_position(value):
    """CCPoint stores each position update as an IEEE single-precision float."""
    return struct.unpack('f',struct.pack('f',value))[0]


def native_translate(position, displacement):
    """CCPoint arithmetic rounds the displacement before the position sum."""
    return native_position(position+native_position(displacement))


def native_horizontal_delta(speed,dt):
    return native_position(SPEED_RULES[speed][0]*native_position(speed)*native_position(60*dt))


def native_velocity(value):
    """Native setYVelocity rounds the fractional part to three decimals."""
    return math.copysign(math.floor(abs(value)*1000+.5)/1000,value)


def facing_down(obj):
    rotation=int(obj.angle)
    if rotation%90==0:
        return not obj.flip_y if abs(rotation)==180 else obj.flip_y
    inside=91<=rotation<=269 or -269<=rotation<=-91
    return not inside if obj.flip_y else inside


def pad_velocity(obj,state):
    """Native pad table; arithmetic is float32 before the ball-like postscale."""
    strength=1.
    if obj.id==140:
        strength=.35 if state.mode=='ship' else .4 if state.mode=='ufo' else .7 if state.mode in ('ball','spider') else .65
    elif obj.id==1332:
        strength=(.95 if state.mini else .63) if state.mode=='ship' else (.98 if state.mini else .6) if state.mode=='ufo' else 1.25
    elif obj.id==67:strength=.8
    value=native_position(native_position(strength)*16)
    value=native_position(value*(native_position(.8) if state.mini else 1))
    value=native_velocity(value)
    if state.mode in ('ball','spider','swing'):value*=native_position(.6)
    return value


def falling_bugged(level,state,gravity):
    if level.settings.get('kA32')=='1':
        return state.vy*state.gravity<2*gravity
    if state.gravity==-1:return state.vy>2*gravity
    return state.vy<(-2 if state.dual else 2)*gravity


def flight_limits(state):
    scale=native_position(.85) if state.mini else 1.
    return (native_position(native_position(-6.4)/scale),native_position(8/scale))


def slope_line(obj):
    diagonal=[(a,b) for a,b in zip(obj.points,obj.points[1:]+obj.points[:1])
              if abs(a[0]-b[0])>.001 and abs(a[1]-b[1])>.001]
    if len(diagonal)!=1:return None
    a,b=diagonal[0]
    m=(b[1]-a[1])/(b[0]-a[0])
    cx=sum(p[0] for p in obj.points)/len(obj.points)
    cy=sum(p[1] for p in obj.points)/len(obj.points)
    return m,cy>a[1]+m*(cx-a[0]),a[1]-m*a[0]


def slope_velocity(state):
    """Unmodified ramp velocity before the ride-age ramp."""
    f=native_position
    dx=native_horizontal_delta(state.speed,TICK)
    magnitude=f(abs(state.slope_m))
    rate=f(magnitude*f(4*dx))
    velocity=f(f(f(1.4)*rate)*min(f(1.1),f(f(.8)/f(math.atan(magnitude)))))
    if state.mode in ('ball','ship','ufo','wave','swing'):velocity=f(velocity*.75)
    return velocity*(-1 if state.slope_ceiling else 1)


def slope_exit_velocity(state):
    factor=min(1.,max(.4,(state.time-state.slope_since)*10))
    return native_velocity(slope_velocity(state)*factor)


def slope_jump_velocity(state, velocity, raw_slope_velocity):
    if raw_slope_velocity*state.gravity<=0:return velocity
    factor=min(1.,max(.4,(state.time-state.slope_since)*10))
    component=raw_slope_velocity if state.mode=='ball' else native_position(raw_slope_velocity*factor)
    bonus=native_position(component*.25)*state.gravity
    cap=abs(velocity)*native_position(1.4)
    return native_velocity(min(cap,abs(velocity)+bonus))*state.gravity


def slope_seat(obj,x,radius,line):
    m,ceiling,intercept=line
    surface=m*x+intercept
    normal_radius=radius*math.sqrt(1+m*m)
    target=(min(max(surface-normal_radius,obj.bounds[1]-radius),obj.bounds[3])
            if ceiling else max(min(surface+normal_radius,obj.bounds[3]+radius),obj.bounds[1]))
    return native_position(target)


def hazard_contact(level,obj,state,half):
    if not obj.collision_radius:
        if obj.angle%90:
            return obj.intersects_rotated_player(state.x,state.y,half,state.rotation)
        return obj.intersects(state.x,state.y,half,half)
    dx,dy=abs(state.x-obj.x),abs(state.y-obj.y)
    radius=obj.collision_radius
    if level.settings.get('kA39')=='1':
        return dx*dx+dy*dy<(radius+half)**2
    # Legacy GD checks the corners and centre containment. It does not use
    # nearest-point circle/rectangle overlap along the middle of an edge.
    if dx<half and dy<half:return True
    return (dx-half)**2+(dy-half)**2<radius*radius


def snap_stair(state,obj):
    if state.mode!='cube':return
    threshold=1 if state.speed in (.7,.9) else 2
    little=(90 if state.mini else 120) if state.speed==.9 else 90 if state.speed==.7 else (90 if state.mini else 150) if state.speed==1.1 else 90 if state.speed==1.3 else (120 if state.mini else 180)
    big=60 if state.speed==.7 else 90 if state.speed==.9 else 120 if state.speed==1.1 else 135
    down=120 if state.speed==.7 else 150 if state.speed==.9 else 195 if state.speed==1.1 else 225
    if state.snap_uid>=0 and state.snap_uid!=obj.uid and state.snap_type==0:
        dx,dy=obj.x-state.snap_x,(obj.y-state.snap_y)*state.gravity
        if any(abs(dx-x)<=threshold and abs(dy-y)<=threshold
               for x,y in ((little,30),(down,-30),(big,60))):
            correction=obj.x+state.snap_offset-state.x
            state.x=native_position(state.x+max(-threshold,min(threshold,correction)))
    state.snap_uid=obj.uid;state.snap_type=obj.type;state.snap_x=obj.x;state.snap_y=obj.y
    state.snap_offset=native_position(state.x-obj.x)


def spider_flip(level,state,radius):
    """Move to the closest facing surface in the opposite gravity direction."""
    direction=state.gravity
    candidates=[state.ceiling-radius if direction==1 else state.floor+radius]
    for obj in level.nearby(state.x,level.collision_buckets,15):
        if obj.type not in (0,25) or obj.id in (366,367):continue
        if not obj.bounds[0]-radius<state.x<obj.bounds[2]+radius:continue
        edge=obj.edge_height(max(obj.bounds[0]+.001,min(state.x,obj.bounds[2]-.001)),direction==-1)
        if edge is None:continue
        y=edge-radius if direction==1 else edge+radius
        if (y-state.y)*direction>0:candidates.append(y)
    state.y=min(candidates,key=lambda y:abs(y-state.y))
    state.gravity*=-1;state.vy=0.;state.grounded=True


def player_radius(state):
    if state.mode=='wave':return 3 if state.mini else 5
    if state.mode=='spider':return 8.1 if state.mini else 13.5
    return 9 if state.mini else 15


def wave_surface_contact(obj,state):
    """Wave solids use a tiny kill box; ramps use an offset surface sample."""
    if obj.type!=25:
        return obj.intersects(state.x,state.y,1.5,1.5)
    diagonals=[(a,b) for a,b in zip(obj.points,obj.points[1:]+obj.points[:1])
               if abs(a[0]-b[0])>.001 and abs(a[1]-b[1])>.001]
    if len(diagonals)!=1:
        return obj.intersects(state.x,state.y,1.5,1.5)
    a,b=diagonals[0]
    slope=(b[1]-a[1])/(b[0]-a[0])
    center_y=sum(p[1] for p in obj.points)/len(obj.points)
    center_x=sum(p[0] for p in obj.points)/len(obj.points)
    ceiling=center_y>a[1]+slope*(center_x-a[0])
    scale=.7 if state.mini else 1.
    sample=state.x+(3.072 if (slope<0 if ceiling else slope>0) else -4.068)*scale
    clamped=max(obj.bounds[0],min(obj.bounds[2],sample))
    surface=a[1]+slope*(clamped-a[0])
    flat=obj.bounds[3] if ceiling else obj.bounds[1]
    if sample!=clamped and abs(surface-flat)<.001:return False
    offset=4*scale
    return (state.y>surface-offset and state.y-offset<flat) if ceiling else (state.y<surface+offset and state.y+offset>flat)


def flight_rotation(state, dx, dy, dt):
    """Classic flying-mode angle easing, expressed in world rotation signs."""
    if state.on_slope or state.dashing:return state.rotation
    f=native_position
    dx,dy=f(dx),f(dy)
    if dx*dx+dy*dy<60*dt*f(1.2):return state.rotation
    target=math.atan2(dy,dx)
    coefficient=.15
    if state.mode=='ufo':
        target=-.4*target
        target=min(target,.1) if state.gravity==1 else max(target,-.1)
        coefficient=.07
    elif state.mode=='wave':coefficient=.4 if state.mini else .25
    target=math.degrees(target)
    delta=(target-state.rotation+180)%360-180
    blend=min(1.,max(0.,60*dt*coefficient))
    return f(state.rotation+delta*blend)


def orb_velocity(kind,state):
    """Native classic orb table: float32 strength, setter, then mode postscale."""
    f=native_position
    if kind==1330:
        magnitude=16.5 if state.mode=='spider' else 11.2 if state.mode=='ufo' else 14 if state.mode in ('ship','wave','swing') else 15
        return -state.gravity*magnitude
    ratio=1.
    if kind==141:
        ratio=.37 if state.mode=='ship' else .42 if state.mode=='ufo' else .77 if state.mode=='ball' else .72
    elif kind==1333:
        ratio=((1.4 if state.mini else 1.) if state.mode=='ship' else
               (1.36 if state.mini else 1.02) if state.mode=='ufo' else
               1.34 if state.mode in ('ball','spider') else 1.28 if state.mode=='robot' else 1.38)
    elif kind==84:ratio=.8
    elif kind==1022:ratio=.7 if state.mode=='ship' else 1.
    elif state.mode=='robot':ratio=.9
    value=f(f(SPEED_RULES[state.speed][1])*f(ratio))
    value=native_velocity(f(value*(f(.8) if state.mini else 1)))
    if state.mode in ('ball','spider'):value*=f(.7)
    elif state.mode=='swing':value*=f(.6)
    if kind==84:value*=.5
    return value*state.gravity*(-1 if kind==1022 else 1)


def ground_action(level,s,ramp_velocity=None):
    _,jump,_=SPEED_RULES[s.speed]
    if ramp_velocity is None and s.on_slope and s.slope_m*s.gravity>0:
        ramp_velocity=slope_velocity(s)
    s.buffered=False
    s.ground_linger=False
    s.on_slope=False
    s.vy=native_velocity(s.gravity*jump*(.5 if s.mode=='robot' else 1)*(.8 if s.mini else 1))
    if ramp_velocity is not None:s.vy=slope_jump_velocity(s,s.vy,ramp_velocity)
    if s.mode=='spider':spider_flip(level,s,player_radius(s))
    elif s.mode=='ball':
        s.gravity*=-1
        s.vy=(s.vy*.5)*native_position(.6)
    elif s.mode=='robot':
        s.robot_hold=0.
        s.robot_jumping=True
    s.grounded=False


def touch_objects(level,s,activation_only=False):
    """Pads/portals activate before solids; ring input keeps its later phase."""
    multiplier,jump,gravity=SPEED_RULES[s.speed]
    size=.8 if s.mini else 1.
    radius=player_radius(s)
    previous_rings=s.touched_rings
    touching=[]
    pad_fired=False
    for obj in level.nearby(s.x, level.interactive_buckets, 80):
        if s.used & obj.bit:
            continue
        # Use the actual rotated activation rectangle and the full player box.
        # Portals, rings, and shallow pads have different native dimensions.
        if activation_only and obj.id in ORB_IDS:continue
        if obj.id in ORB_IDS:
            # Native rings use their object rectangle and retain the preceding
            # collision pass's contacts for a newly pressed button. A held
            # buffered press instead fires on this pass's first contact.
            near=obj.intersects(s.x,s.y,radius,radius)
            if near:touching.append(obj.uid)
            if s.buffered and not s.input_held and obj.uid in previous_rings:
                near=True
        else:near = obj.intersects(s.x,s.y,radius,radius)
        if not near:
            continue
        if obj.id in ORB_IDS:
            if not s.buffered:
                continue
            s.buffered = False
            s.robot_jumping=False
            if obj.id in (1704,1751):
                s.dashing=True;s.dash_angle=math.radians(-obj.angle)
                if obj.id==1751:s.gravity*=-1
            elif obj.id==3004:
                spider_flip(level,s,radius)
            elif obj.id==1330:
                s.vy=orb_velocity(obj.id,s)
            else:
                s.vy=orb_velocity(obj.id,s)
                if obj.id in (84,1022):s.gravity*=-1
            s.grounded = False
            s.boost=s.boost or obj.id in (1330,1333)
        elif obj.id in PAD_IDS:
            if obj.id==67:
                if (s.gravity==-1)!=facing_down(obj):continue
                old_gravity=s.gravity
                s.gravity*=-1
                s.vy=old_gravity*pad_velocity(obj,s)*.5
            else:
                s.vy=s.gravity*pad_velocity(obj,s)
            s.boost=obj.id==1332
            s.on_slope=False
            pad_fired=True
            s.robot_jumping=False
            s.grounded=False
        elif obj.id in MODE_PORTALS:
            previous_mode=s.mode
            new_mode=MODE_PORTALS[obj.id]
            # Ground/camera placement is separate from toggling the icon. In
            # particular a second ship portal can raise the flight corridor.
            if new_mode!='cube' and (new_mode!='wave' or previous_mode!=new_mode):
                height=240 if new_mode=='ball' else 300
                center=max(height/2,math.floor((obj.y+90)/30)*30-90)
                s.floor,s.ceiling=center-height/2,center+height/2
            elif new_mode=='cube':s.floor=0.
            if new_mode!=previous_mode:
                flying=('ship','ufo','wave','swing')
                if previous_mode in flying:s.vy*=.5
                if new_mode in flying:s.vy*=.5
                s.mode=new_mode
                s.robot_jumping=False
                s.grounded=False
                radius=player_radius(s)
        elif obj.id in SPEED_PORTALS:
            s.speed=SPEED_PORTALS[obj.id]
            multiplier,jump,gravity=SPEED_RULES[s.speed]
        elif obj.id in (99,101):
            s.mini=obj.id==101
            size=.8 if s.mini else 1.
            radius=player_radius(s)
        elif obj.id in (45,46):
            s.mirror=obj.id==45
        elif obj.id in (10, 11):
            target=1 if obj.id==10 else -1
            if s.gravity!=target:
                s.gravity=target
                s.vy*=.5
                s.grounded=False
        elif obj.id==747:
            s.y=native_position(obj.y+float(obj.raw.get('54') or 100))
            s.grounded=False
        elif obj.id in (286, 287):
            s.dual = obj.id == 286
        s.used |= obj.bit
        s.ground_linger=False
    if not activation_only:s.touched_rings=tuple(touching)
    return pad_fired



def _simulate_player(level,s,dt,holding,pressed):
    """Native phase order: held physics, contacts, then new button actions."""
    if s.dead or s.won:return
    edge=pressed or (holding and not s.input_held)
    held_before=s.input_held
    was_on_slope=s.on_slope
    previous_slope_m=s.slope_m
    previous_slope_ceiling=s.slope_ceiling
    previous_grounded=s.grounded
    if not was_on_slope and not previous_grounded:s.slope_since=-1.
    previous_slope_target=s.slope_target
    s.on_slope=False
    # Legacy inverted gravity retains the on-ground latch while walking off
    # a platform, until the previous velocity exceeds the native 2g test.
    # kA32 enables the newer symmetric gravity behavior.
    linger=(level.settings.get('kA32')!='1' and s.gravity==-1
            and s.mode in ('cube','ball','spider') and not s.dual
            and (s.grounded or s.ground_linger) and s.vy<=2*SPEED_RULES[s.speed][2])
    was_grounded=s.grounded or s.ground_linger
    old_x,old_y=s.x,s.y
    s.time+=dt
    multiplier,jump,gravity=SPEED_RULES[s.speed]
    speed=multiplier*native_position(s.speed)*60
    dx=native_horizontal_delta(s.speed,dt)
    s.x=native_translate(s.x,dx)
    step=native_position(native_position(60*dt)*native_position(.9))
    radius=player_radius(s)
    launch=False
    fall_limit,rise_limit=flight_limits(s)
    if s.mode in ('ship','ufo','swing') and fall_limit<s.vy*s.gravity<rise_limit:
        s.boost=False
    if s.dashing and held_before:
        s.vy=speed/Y_TIME*math.sin(s.dash_angle)
    elif s.mode=='wave':
        s.vy=multiplier*native_position(s.speed)*(1 if held_before else -1)*s.gravity
    elif s.mode=='ship':
        falling=falling_bugged(level,s,gravity)
        if held_before and not s.boost:
            coefficient=.5 if falling else .4
        elif s.boost and s.vy*s.gravity<0:
            coefficient=.5 if held_before and falling else .4
        elif not held_before and not falling:
            coefficient=-.48
        else:coefficient=-.4 if held_before and falling else -.32
        s.vy+=GRAVITY*coefficient*step*s.gravity/(.85 if s.mini else 1)
        if not s.boost:s.vy=max(fall_limit,min(rise_limit,s.vy*s.gravity))*s.gravity
    elif s.mode=='ufo':
        if s.buffered and held_before:
            s.vy=native_velocity(max(s.vy*s.gravity,6.8 if s.mini else 7)*s.gravity)
            s.buffered=False
        falling=falling_bugged(level,s,gravity)
        s.vy-=GRAVITY*(.4 if falling else .6)*step*s.gravity/(.85 if s.mini else 1)
        if not s.boost:s.vy=max(fall_limit,min(rise_limit,s.vy*s.gravity))*s.gravity
    elif s.mode=='swing':
        if s.buffered and held_before:
            s.gravity*=-1
            s.vy=native_velocity(s.vy*.8)
            s.buffered=False
        s.vy-=GRAVITY*(.6 if s.mini else .4)*step*s.gravity
        if not s.boost:s.vy=max(-8,min(8,s.vy))
    else:
        if (s.grounded or (was_grounded and linger)) and held_before and (s.mode=='cube' or s.buffered):
            ramp_velocity=slope_velocity(s) if was_on_slope and s.slope_m*s.gravity>0 else None
            ground_action(level,s,ramp_velocity)
            launch=True
        if not launch:
            sustain=s.mode=='robot' and s.robot_jumping and held_before and s.robot_hold<.278 and s.vy*s.gravity>0
            if sustain:s.robot_hold+=dt
            else:s.vy-=(GRAVITY*.6 if s.mode in ('ball','spider') else gravity*(.9 if s.mode=='robot' else 1))*step*s.gravity
        s.vy=max(-15,s.vy*s.gravity)*s.gravity
    s.vy=native_velocity(s.vy)
    if s.mode=='wave' and not s.dashing:
        s.y=native_translate(s.y,dx*(2 if s.mini else 1)*(1 if held_before else -1)*s.gravity)
    else:s.y=native_translate(s.y,s.vy*step)
    s.grounded = False
    s.ground_linger=linger and not launch
    clamp_radius=(6 if s.mini else 10) if s.mode=='wave' else radius
    if s.y < s.floor+clamp_radius:
        if s.mode == 'cube' and s.gravity == -1:
            s.dead = True
        s.y, s.vy, s.grounded = s.floor+clamp_radius, 0, s.gravity == 1
    if s.mode != 'cube' and s.y > s.ceiling - clamp_radius:
        s.y, s.vy, s.grounded = s.ceiling-clamp_radius, 0, s.gravity == -1
    if s.mode == 'cube' and s.y > 900:
        s.dead = True
    # Native collision passes resolve surfaces before testing hazards. A
    # landing can seat the icon clear of a nearby spike in the same tick.
    if touch_objects(level,s,activation_only=True):was_on_slope=False
    radius=player_radius(s)
    nearby=tuple(level.nearby(s.x,level.collision_buckets))
    surfaces=sorted((o for o in nearby if o.type not in (2,47) and o.id not in (366,367)),
                    key=lambda o:(math.floor(o.x/100),math.floor(o.y/100),o.uid),reverse=True)
    for obj in surfaces:
        if not obj.intersects(s.x,s.y,radius,radius):continue
        if s.mode == 'wave':
            if obj.type==21:continue
            if wave_surface_contact(obj,s):
                s.dead = True
                return
            continue
        if obj.type==25:
            line=slope_line(obj)
            if line is not None and (s.gravity==-1)==line[1]:
                m,ceiling,intercept=line
                # While a positive launch is stored, native slope collision
                # refuses a downhill successor (or a shallower rise). The
                # current ramp must release first; a neighboring triangle's
                # clamped corner cannot steal the accumulated ride.
                if (was_on_slope and previous_slope_ceiling==ceiling
                        and previous_slope_m*s.gravity>0
                        and (m*s.gravity<0 or abs(previous_slope_m)>abs(m)+.0001)):
                    continue
                target=slope_seat(obj,s.x,radius,line)
                # A repeated clamped target returns before setting onSlope.
                # postCollision then releases the rider with the ramp impulse.
                if was_on_slope and target==previous_slope_target:continue
                penetrated=s.y>target if ceiling else s.y<target
                approach=(old_y<=target+10 if ceiling else old_y>=target-10)
                if penetrated and (was_on_slope or approach):
                    s.y=target;s.vy=0;s.grounded=True;s.on_slope=True
                    s.slope_m=m;s.slope_ceiling=ceiling;s.slope_target=target
                    if not was_on_slope and s.slope_since<0:s.slope_since=s.time
                elif penetrated and obj.intersects(s.x,s.y,2.7 if s.mini else 4.5,2.7 if s.mini else 4.5):
                    s.dead=True
                    return
                continue
        # A cube lands as soon as its leading edge overlaps a platform. Requiring
        # its center to be above the platform wrongly rejects narrow pillars.
        sample_x = max(obj.bounds[0]+.001, min(s.x, obj.bounds[2]-.001))
        top = obj.edge_height(sample_x, True)
        bottom = obj.edge_height(sample_x, False)
        landed = False
        if (s.gravity==1 or s.mode in ('ball','ship','ufo','swing')) and s.vy <= 0 and top is not None and old_y - radius >= top - (6 if s.mode in ('ship','ufo','wave') else 10):
            s.y, s.vy = top + radius, 0
            s.grounded = s.gravity == 1
            landed = True
            snap_stair(s,obj)
        elif (s.gravity==-1 or s.mode in ('ball','ship','ufo','swing')) and s.vy >= 0 and bottom is not None and old_y + radius <= bottom + (6 if s.mode in ('ship','ufo','wave') else 10):
            s.y, s.vy = bottom - radius, 0
            s.grounded = s.gravity == -1
            landed = True
            snap_stair(s,obj)
        if landed and obj.type==25 and s.grounded:
            line=slope_line(obj)
            if line is not None:
                s.on_slope=True
                s.slope_m,s.slope_ceiling=line[:2]
                s.slope_target=s.y
                if not was_on_slope and s.slope_since<0:s.slope_since=s.time
        # collidedWithObjectInternal also admits an upright rising body whose
        # foot is already inside the top-face snap tolerance. It can clear a
        # ledge after a pad without the inner side box killing it first.
        if (not landed and s.mode in ('cube','robot') and s.gravity==1
                and s.vy>0 and top is not None and s.y-radius>=top-10):
            continue
        if obj.type==21:continue  # Brick platforms provide footing without a lethal side face.
        if not landed and obj.intersects(s.x, s.y, 2.7 if s.mini else 4.5, 2.7 if s.mini else 4.5):
            s.dead = True
            return

    for obj in nearby:
        if (obj.type in (2,47) or obj.id in (366,367)) and hazard_contact(level,obj,s,radius):
            s.dead=True
            return

    if was_on_slope and not s.on_slope and not s.grounded and not launch:
        uphill=s.slope_m<0 if s.slope_ceiling else s.slope_m>0
        velocity=slope_exit_velocity(s) if uphill else native_velocity(s.slope_m*speed/60)
        if not uphill or (velocity-s.vy)*(-1 if s.slope_ceiling else 1)>0:
            s.vy=velocity
            s.boost=True
            s.ground_linger=False

    # New presses are read after this tick's movement and collision pass.
    # A held buffered action can therefore launch on a later grounded tick;
    # an edge launch sets velocity immediately without moving the icon twice.
    if edge:s.buffered=True
    elif not holding:s.buffered=False
    if not holding:
        s.dashing=False
        if s.mode=='robot':s.robot_hold=.278;s.robot_jumping=False
    touch_objects(level,s)
    if s.buffered and (holding or pressed):
        if edge and (s.grounded or s.ground_linger) and s.mode in ('cube','ball','robot','spider'):
            ground_action(level,s)
        elif s.mode in ('ufo','swing'):
            pass  # Native pushButton queues these actions for updateJump.
    s.input_held=holding
    if not holding:s.buffered=False
    if s.mode=='cube':
        if not s.grounded:s.rotation-=(540 if s.mini else 415.384615)*dt*s.gravity
        else:s.rotation+=(round(s.rotation/90)*90-s.rotation)*-math.expm1(-30*dt)
    elif s.mode=='ball':s.rotation-=360*dt*s.gravity
    elif s.mode in ('ship','ufo','wave','swing'):
        s.rotation=flight_rotation(s,s.x-old_x,s.y-old_y,dt)
    else:s.rotation=math.degrees(math.atan2(s.vy*Y_TIME,speed))
    if s.x>=level.end_x:s.won=True


def clone_state(state):
    result=copy.copy(state)
    if state.twin is not None:
        result.twin=copy.copy(state.twin)
    return result


def simulate(level,state,dt,holding,pressed):
    """Advance each dual icon independently, with the same input stream."""
    _simulate_player(level,state,dt,holding,pressed)
    if state.dead:return
    if not state.dual:
        state.twin=None
        return
    if state.twin is None:
        twin=copy.copy(state)
        twin.twin=None;twin.dual=True
        twin.y=state.floor+state.ceiling-state.y
        twin.vy=-state.vy;twin.gravity=-state.gravity;twin.rotation=-state.rotation
        state.twin=twin
    else:
        _simulate_player(level,state.twin,dt,holding,pressed)
        if state.twin.dead:state.dead=True



class Game:
    def __init__(self, level=None):
        self.level = level or Level()
        self.practice = False
        self.best_file=BEST_FILE if self.level.id==17 else ROOT/f'assets/progress/{self.level.id}.txt'
        self.attempt = 0
        try:
            self.best = max(0., min(100., float(self.best_file.read_text())))
        except (OSError, ValueError):
            self.best = 0.
        self.reset()

    def reset(self, section=0):
        self.attempt += 1
        self.section = section
        self.state = self.level.initial_state()
        if section:
            portal = self.level.portals[section-1]
            self.state.x, self.state.y = portal.x + 27, portal.y
            for p in self.level.portals[:section]:
                if p.id in MODE_PORTALS:
                    self.state.mode = MODE_PORTALS[p.id]
                elif p.id in (286, 287):
                    self.state.dual = p.id == 286
                self.state.used |= p.bit
            self.state.grounded = False
            for obj in sorted((o for o in self.level.objects if o.x<self.state.x and o.id in PORTAL_IDS),key=lambda o:o.x):
                if obj.id in SPEED_PORTALS:self.state.speed=SPEED_PORTALS[obj.id]
                elif obj.id in (99,101):self.state.mini=obj.id==101
                elif obj.id in (10,11):self.state.gravity=1 if obj.id==10 else -1
                elif obj.id in MODE_PORTALS:
                    mode=MODE_PORTALS[obj.id]
                    if mode!='cube':
                        height=240 if mode=='ball' else 300
                        center=max(height/2,math.floor((obj.y+90)/30)*30-90)
                        self.state.floor,self.state.ceiling=center-height/2,center+height/2
                    else:self.state.floor=0.
                self.state.used|=obj.bit
            self.state.time=self.level.time_at_x(self.state.x)
        self.started = False
        self.previous_state = clone_state(self.state)
        self.trail = deque(maxlen=160)
        self.trail2 = deque(maxlen=160)
        self.pending_save = False

    @property
    def x(self): return self.state.x
    @property
    def y(self): return self.state.y
    @property
    def mode(self): return self.state.mode
    @property
    def dead(self): return self.state.dead
    @property
    def won(self): return self.state.won
    @property
    def progress(self): return max(0,min(100, self.x / self.level.end_x * 100))
    @property
    def music_time(self): return self.state.time

    def update(self, dt, holding=False, pressed=False):
        if not self.started or self.dead or self.won:
            return
        self.previous_state = clone_state(self.state)
        simulate(self.level, self.state, dt, holding, pressed)
        self.trail.append((self.x, self.y))
        if self.state.twin is not None:self.trail2.append((self.state.twin.x,self.state.twin.y))
        else:self.trail2.clear()
        if not self.practice:
            if self.progress > self.best:
                self.best = self.progress
                if self.dead or self.won:
                    self.pending_save = True
        self.section = sum(p.x <= self.x for p in self.level.portals)

    def save_best(self):
        if self.pending_save:
            try:
                self.best_file.parent.mkdir(parents=True,exist_ok=True)
                temporary=self.best_file.with_suffix('.tmp')
                temporary.write_text(f'{self.best:.2f}')
                temporary.replace(self.best_file)
            except OSError:
                pass
            self.pending_save = False


class BitmapFont:
    """Use the installed game's Pusab glyph atlas for level text."""
    def __init__(self):
        font_image=asset_paths.texture('bigFont.png')
        self.source_scale=asset_paths.resolution('bigFont.png')
        self.sheet = pygame.image.load(str(font_image)).convert_alpha()
        self.glyphs = {}
        for line in (font_image.parent/'bigFont.fnt').read_text().splitlines():
            if line.startswith('char '):
                item = {k:int(v) for k,v in re.findall(r'(\w+)=(-?\d+)', line)}
                self.glyphs[item['id']] = item
        # Keep cached text with this font, rather than retaining old UHD atlases
        # in a class-wide cache after returning from levels.
        self.render=lru_cache(maxsize=96)(self.make_text)

    def make_text(self, text, color=(255,255,255), scale=1.):
        width = sum(self.glyphs.get(ord(c), {}).get('xadvance', 15*self.source_scale) for c in text)
        surface = pygame.Surface((max(1,width+8*self.source_scale), 48*self.source_scale),pygame.SRCALPHA)
        x=0
        for char in text:
            d=self.glyphs.get(ord(char))
            if not d:
                x+=15*self.source_scale
                continue
            if d['width'] and d['height']:
                glyph=self.sheet.subsurface((d['x'],d['y'],d['width'],d['height']))
                surface.blit(glyph,(x+d['xoffset'],d['yoffset']))
            x+=d['xadvance']
        surface.fill((*color,255),special_flags=pygame.BLEND_RGBA_MULT)
        return pygame.transform.smoothscale(surface,(max(1,round(surface.get_width()*scale/self.source_scale)),
                                                       max(1,round(surface.get_height()*scale/self.source_scale))))


@dataclass(frozen=True)
class DrawItem:
    obj: Object
    layer: int
    mask: str
    rotating: bool
    solid: bool
    lethal: bool
    extent: float
    polygon: tuple


class Renderer:
    """Readable foreground, quiet decoration, and bounded rendering caches."""
    def __init__(self, screen, level):
        self.screen, self.level = screen, level
        appearance=user_settings.load()
        self.primary=tuple(appearance['primary'])
        self.secondary=tuple(appearance['secondary'])
        frames={obj.frame for obj in level.objects}
        for obj in level.objects:
            info=level.metadata.get(str(obj.id),{})
            frames.update(info.get(k,'') for k in ('mask','back'))
        self.background_frame=f"game_bg_{level.spec['background']:02}_001.png"
        self.ground_frame=f"groundSquare_{level.spec['ground']:02}_001.png"
        frames.update((self.background_frame,self.ground_frame,'bigFont.png'))
        frames.update(p.name for p in ASSETS.glob('*.png') if p.name.startswith(
            ('player_01_', 'ship_01_', 'player_ball_01_', 'bird_01_', 'dart_01_',
             'robot_01_', 'spider_01_', 'swing_01_', 'jetpack_01_')))
        self.images={name:pygame.image.load(str(asset_paths.texture(name))).convert_alpha()
                     for name in frames if name and asset_paths.texture(name).is_file()}
        self.font = pygame.font.Font(None, 25)
        self.small = pygame.font.Font(None, 20)
        self.bitmap_font = BitmapFont()
        self.camera_y = -93.75
        self.last_attempt = None
        self.frames = deque(maxlen=120)
        # Scale once. A translucent, neutral texture preserves the original
        # hexagons without rebuilding a large RGB-tinted image every frame.
        self.backdrop = pygame.transform.smoothscale(
            self.images[self.background_frame], (820, 820)).convert()
        self.backdrop.set_alpha(65)
        self.scrim = pygame.Surface((app.WIDTH, app.HEIGHT)).convert()
        self.scrim.fill((3, 7, 16))
        self.scrim.set_alpha(175)
        self.footer = pygame.Surface((app.WIDTH, 28), pygame.SRCALPHA)
        self.footer.fill((7, 13, 25, 235))
        self.items = {}
        for obj in level.objects:
            lethal = obj.type in (2,47) or obj.id in (366, 367)
            solid = obj.type in (0, 21, 25) and not lethal
            rotating = any(word in obj.frame.lower()
                           for word in ('cogwheel', 'rotatingball', 'blade'))
            self.items[obj.uid] = DrawItem(
                obj, 0 if obj.type == 7 else 1 if solid else 2,
                level.metadata.get(str(obj.id), {}).get('mask', ''),
                rotating, solid, lethal, math.hypot(obj.width, obj.height) * SCALE / 2,
                tuple((x * SCALE, -y * SCALE) for x, y in obj.points))
        self.animations={}
        for mode in ('robot','spider'):
            path=ASSETS/(mode+'_animation.json')
            if path.exists():self.animations[mode]=json.loads(path.read_text())['animationContainer']
        self.pose=lru_cache(maxsize=96)(self.make_pose)
        self.boundaries = self.build_boundaries()
        # Instance-local caches don't retain old Renderer instances after exit.
        self.sprite = lru_cache(maxsize=1024)(self.make_sprite)
        self.visible_items = lru_cache(maxsize=24)(self.collect_visible)
        self.label = lru_cache(maxsize=128)(self.make_label)

    def build_boundaries(self):
        """Find exposed collision edges once, so interior tile seams stay quiet."""
        unique, buckets = set(), defaultdict(list)
        for obj in self.level.objects:
            if not self.items[obj.uid].solid:
                continue
            for a, b in zip(obj.points, obj.points[1:] + obj.points[:1]):
                length = math.hypot(b[0]-a[0], b[1]-a[1])
                if length < .01:
                    continue
                key = tuple(sorted(((round(a[0], 3), round(a[1], 3)),
                                    (round(b[0], 3), round(b[1], 3)))))
                if key in unique:
                    continue
                unique.add(key)
                mx, my = (a[0]+b[0])/2, (a[1]+b[1])/2
                nx, ny = -(b[1]-a[1])/length*.35, (b[0]-a[0])/length*.35
                inside = []
                neighbors = tuple(self.level.nearby(mx, self.level.collision_buckets, 1))
                for sign in (-1, 1):
                    inside.append(any(self.items[o.uid].solid and
                        o.intersects(mx+nx*sign, my+ny*sign, .01, .01) for o in neighbors))
                if inside[0] == inside[1]:
                    continue
                edge = (a[0]*SCALE, -a[1]*SCALE, b[0]*SCALE, -b[1]*SCALE)
                for cell in range(math.floor(min(a[0], b[0])/120),
                                  math.floor(max(a[0], b[0])/120)+1):
                    buckets[cell].append(edge)
        return buckets

    def collect_visible(self, first, last):
        objects, edges = {}, set()
        for cell in range(first, last+1):
            for obj in self.level.buckets.get(cell, ()):
                objects[obj.uid] = self.items[obj.uid]
            edges.update(self.boundaries.get(cell, ()))
        return (tuple(sorted(objects.values(), key=lambda item: (item.layer,int(item.obj.raw.get('24') or 5),int(item.obj.raw.get('25') or 0),item.obj.uid))),
                tuple(edges))

    def make_sprite(self, frame, color, angle, fx, fy, opacity=255, scale=1.):
        base = self.images.get(frame)
        if base is None:
            return None
        image = base.copy()
        image.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
        if fx or fy:
            image = pygame.transform.flip(image, fx, fy)
        if angle % 360:
            image = pygame.transform.rotate(image, -angle)
        image = pygame.transform.smoothscale(image,
            (max(1, round(image.get_width()*SCALE*scale/asset_paths.resolution(frame))), max(1, round(image.get_height()*SCALE*scale/asset_paths.resolution(frame)))))
        if opacity != 255:
            image.set_alpha(opacity)
        return image

    def make_label(self, text, color, big=False):
        if big:
            image = self.bitmap_font.render(text, color, 1.15)
            shadow = self.bitmap_font.render(text, (0, 0, 0), 1.15)
        else:
            image = self.font.render(text, True, color)
            shadow = self.font.render(text, True, (0, 0, 0))
        return image, shadow

    def text(self, text, x, y, color=(255,255,255), big=False, center=False):
        image, shadow = self.label(text, color, big)
        rect = image.get_rect(center=(x,y)) if center else image.get_rect(topleft=(x,y))
        self.screen.blit(shadow, rect.move(2,2))
        self.screen.blit(image, rect)

    @staticmethod
    def render_state(game, alpha):
        current, previous = game.state, game.previous_state
        if (alpha >= 1 or not game.started or game.dead or game.won or
                (previous.mode, previous.gravity, previous.dual) !=
                (current.mode, current.gravity, current.dual)):
            return current
        state = clone_state(current)
        alpha = max(0, alpha)
        for name in ('x', 'y', 'rotation'):
            a, b = getattr(previous, name), getattr(current, name)
            setattr(state, name, a+(b-a)*alpha)
        if state.twin is not None and previous.twin is not None:
            for name in ('x','y','rotation'):
                a,b=getattr(previous.twin,name),getattr(current.twin,name)
                setattr(state.twin,name,a+(b-a)*alpha)
        return state

    def draw(self, game, holding, dt=1/60, fps=60, alpha=1):
        screen, level = self.screen, self.level
        s = self.render_state(game, alpha)
        target = (s.floor+s.ceiling)/2-168.75 if s.mode != 'cube' else max(-93.75, s.y-250)
        if game.attempt != self.last_attempt:
            self.camera_y = target
            self.last_attempt = game.attempt
        else:
            self.camera_y += (target-self.camera_y) * -math.expm1(-min(max(dt, 0), .1)*10)
        camera_x = s.x-105
        offset_x = -camera_x*SCALE
        offset_y = app.HEIGHT+self.camera_y*SCALE
        def project(x, y):
            return round(x*SCALE+offset_x), round(-y*SCALE+offset_y)

        # Resolve each channel once instead of doing a timeline search per object.
        colors = {channel: level.color(channel, s.x) for channel in level.color_events}
        bg = colors[1000]
        screen.fill(tuple(round(c*.48) for c in bg))
        drift = round(-s.x*SCALE*.10) % 820
        screen.blit(self.backdrop, (drift-820, -140))
        screen.blit(self.backdrop, (drift, -140))
        if drift+820 < app.WIDTH:
            screen.blit(self.backdrop, (drift+820, -140))

        first = int((camera_x-90)//120)
        last = int((camera_x+app.WIDTH/SCALE+90)//120)
        items, edges = self.visible_items(first, last)
        angle_offset = round(s.x/SPEED*90) % 360
        portal_fronts = []
        for item in items:
            obj = item.obj
            if obj.id == 142 and s.used & obj.bit:
                continue
            px, py = project(obj.x, obj.y)
            if (px+item.extent < 0 or px-item.extent > app.WIDTH or
                    py+item.extent < 0 or py-item.extent > app.HEIGHT):
                continue
            if item.solid:
                polygon = [(round(x+offset_x), round(y+offset_y)) for x,y in item.polygon]
                pygame.draw.polygon(screen, WALL_FILL, polygon)
            if obj.id == 146 or obj.frame.startswith('invis_'):
                continue
            if obj.type == 25 and not item.lethal:
                continue  # Its collision silhouette is drawn in the foreground pass.
            # Keep the level's authored channels and native texture contrast.
            # Only non-colliding artwork is subdued; hazards retain white detail.
            color = colors.get(obj.channel, colors[1004])
            opacity = round((165 if obj.type == 7 else 255)*level.channel_opacity.get(obj.channel,1))
            angle = obj.angle+(45 if obj.id in (366,367) else 0)
            if item.rotating:
                angle = (angle+angle_offset) % 360
            object_scale=float(obj.raw.get('32') or 1)
            back_frame = level.metadata.get(str(obj.id), {}).get('back')
            if back_frame:
                # Native portals wrap around the player: rear half below the
                # icon, front half above it. Both use the atlas artwork.
                image = self.sprite(back_frame, color, angle, obj.flip_x, obj.flip_y, opacity, object_scale)
                if image:
                    screen.blit(image, image.get_rect(center=(px,py)))
                portal_fronts.append((obj.frame, color, angle, obj.flip_x, obj.flip_y, opacity, object_scale, (px,py)))
            else:
                image = self.sprite(obj.frame, color, angle, obj.flip_x, obj.flip_y, opacity, object_scale)
                if image:
                    screen.blit(image, image.get_rect(center=(px,py)))
            if item.mask:
                detail = colors.get(int(obj.raw.get('22') or 1003), (0, 0, 0))
                image = self.sprite(item.mask, detail, angle, obj.flip_x, obj.flip_y, opacity, object_scale)
                if image:
                    screen.blit(image, image.get_rect(center=(px,py)))

        # A consistent bright rim denotes real collision geometry. Background
        # artwork never receives this rim, even if its native texture has spikes.
        for x1,y1,x2,y2 in edges:
            a = (round(x1+offset_x), round(y1+offset_y))
            b = (round(x2+offset_x), round(y2+offset_y))
            if max(a[0], b[0]) < 0 or min(a[0], b[0]) > app.WIDTH:
                continue
            pygame.draw.line(screen, (7,3,16), a, b, 3)
            pygame.draw.line(screen, colors[1004], a, b, 1)

        floor_y = project(s.x,s.floor)[1]
        if floor_y < app.HEIGHT:
            ground_color = colors[1001]
            pygame.draw.rect(screen, ground_color,
                (0,max(0,floor_y),app.WIDTH,app.HEIGHT-max(0,floor_y)))
            tile = self.sprite(self.ground_frame, ground_color, 0, False, False)
            if tile:
                width, height = tile.get_size()
                drift = round(-s.x*SCALE) % width
                for y in range(floor_y, app.HEIGHT, height):
                    for x in range(drift-width, app.WIDTH, width):
                        screen.blit(tile, (x,y))
            pygame.draw.line(screen, colors[1002], (0,floor_y), (app.WIDTH,floor_y), 2)
        if s.mode != 'cube':
            ceiling = project(s.x,s.ceiling)[1]
            if ceiling > 0:
                pygame.draw.rect(screen, (7,13,25), (0,0,app.WIDTH,ceiling))
                pygame.draw.line(screen, SOLID_EDGE, (0,ceiling), (app.WIDTH,ceiling), 2)
        if s.mode == 'wave' and len(game.trail) > 1:
            trail = list(game.trail)
            trail[-1] = (s.x,s.y)
            points = [project(x,y) for x,y in trail]
            pygame.draw.lines(screen, (255,207,91), False, points, 5)
            pygame.draw.lines(screen, self.primary, False, points, 2)
            if s.twin is not None and len(game.trail2)>1:
                pygame.draw.lines(screen,(255,207,91),False,
                                  [project(x,y) for x,y in game.trail2],4)
        self.icon(s, project(s.x,s.y), holding)
        if s.twin is not None:
            self.icon(s.twin,project(s.twin.x,s.twin.y),holding)
        for frame, color, angle, fx, fy, opacity, object_scale, position in portal_fronts:
            image = self.sprite(frame, color, angle, fx, fy, opacity, object_scale)
            if image:
                screen.blit(image, image.get_rect(center=position))
        self.draw_hud(game, fps)
        if not game.started or s.dead or s.won:
            self.draw_menu(game)

    def draw_hud(self, game, fps):
        screen = self.screen
        bar = pygame.Rect(310,12,340,6)
        pygame.draw.rect(screen, (6,12,23), bar.inflate(8,8), border_radius=6)
        pygame.draw.rect(screen, (95,135,164), bar.inflate(4,4), 1, border_radius=5)
        pygame.draw.rect(screen, (255,225,105),
            (bar.x,bar.y,round(bar.width*game.progress/100),bar.height), border_radius=3)
        self.text(f'{game.progress:.0f}%', 670, 3)
        self.text(f'{fps:.0f} FPS', 12, 8, color=(160,181,202))
        pygame.draw.circle(screen, (176,204,222), (930,24), 15, 2)
        for x in (926,934):
            pygame.draw.line(screen, (220,238,248), (x,17), (x,31), 3)
        screen.blit(self.footer,(0,app.HEIGHT-28))
        pygame.draw.circle(screen,SOLID_EDGE,(22,app.HEIGHT-14),4)
        self.text('Solid',34,app.HEIGHT-24,color=SOLID_EDGE)
        pygame.draw.polygon(screen,DANGER,((104,app.HEIGHT-10),(114,app.HEIGHT-10),(109,app.HEIGHT-19)))
        self.text('Spikes = danger',121,app.HEIGHT-24,color=DANGER)
        self.text('Dim = background',285,app.HEIGHT-24,color=(154,144,174))
        hint = {'cube':'HOLD TO JUMP', 'ship':'HOLD TO FLY', 'wave':'HOLD / RELEASE',
                'ball':'HOLD TO BUFFER', 'ufo':'TAP TO FLAP', 'robot':'HOLD TO JUMP',
                'spider':'HOLD TO BUFFER','swing':'TAP TO FLIP'}[game.mode]
        self.text(f'{game.mode.upper()} / {hint}',590,app.HEIGHT-24,color=(234,235,221))
        if game.practice:
            self.text('PRACTICE',420,app.HEIGHT-24,color=(125,232,172))

    def draw_menu(self, game):
        self.screen.blit(self.scrim,(0,0))
        panel = pygame.Rect(100,142,760,272)
        pygame.draw.rect(self.screen,(13,23,40),panel,border_radius=18)
        pygame.draw.rect(self.screen,(61,94,122),panel,1,border_radius=18)
        title = ('LEVEL COMPLETE!' if game.won else 'TRY AGAIN' if game.dead
                 else game.level.name.upper())
        self.text(title,480,195,(237,243,226),True,True)
        self.text('SPACE / CLICK / R: retry' if game.started else 'SPACE / UP / CLICK: start',
                  480,253,color=(255,223,139),center=True)
        self.text(f'Attempt {game.attempt}   /   Best {game.best:.1f}%',
                  480,290,color=(152,179,199),center=True)
        self.text('P: practice   /   LEFT & RIGHT: section   /   M: mute',
                  480,334,color=(176,195,211),center=True)
        self.text('TAB: pause   /   ESC: level menu',
                  480,370,color=(125,149,170),center=True)

    def draw_pause(self, focused=True):
        self.screen.blit(self.scrim,(0,0))
        self.text('PAUSED',480,230,big=True,center=True)
        message = ('TAB or click the pause button to resume' if focused
                   else 'Click the window to resume')
        self.text(message,480,290,center=True)

    def make_pose(self,mode,frame,upside_down,mini):
        parts=self.animations[mode][frame]
        surface=pygame.Surface((160,160),pygame.SRCALPHA)
        for part in sorted(parts.values(),key=lambda p:int(p.get('zValue',0))):
            x,y=[float(v) for v in re.findall(r'-?[\d.]+',part['position'])]
            sx,sy=[float(v) for v in re.findall(r'-?[\d.]+',part.get('scale','{1, 1}'))]
            flips=[int(v) for v in re.findall(r'\d+',part.get('flipped','{0, 0}'))]
            frame_name=part['texture']
            back=int(part.get('tag',3))<3
            for name,color in ((frame_name.replace('_001.png','_2_001.png'),self.secondary),
                               (frame_name,tuple(round(c*.65) for c in self.primary) if back else self.primary)):
                image=self.sprite(name,color,float(part.get('rotation',0)),bool(flips[0]),bool(flips[1]),255,(sx+sy)/2)
                if image:surface.blit(image,image.get_rect(center=(round(80+x*SCALE),round(80-y*SCALE))))
        if upside_down:surface=pygame.transform.flip(surface,False,True)
        if mini:surface=pygame.transform.smoothscale(surface,(96,96))
        return surface

    def icon(self,state,position,holding):
        if state.mode in self.animations:
            mode=state.mode
            action='run' if state.grounded else 'jump_loop' if state.vy*state.gravity>0 else 'fall_loop'
            frames=sorted(k for k in self.animations[mode] if k.startswith(mode.title()+'_'+action+'_'))
            if not frames:frames=sorted(self.animations[mode])
            frame=frames[int(state.time*30)%len(frames)]
            image=self.pose(mode,frame,state.gravity==-1,state.mini)
            self.screen.blit(image,image.get_rect(center=position))
            return
        stem = {'cube':'player_01','ball':'player_ball_01','ship':'ship_01',
                'ufo':'bird_01','wave':'dart_01','robot':'player_01',
                'spider':'player_01','swing':'swing_01'}[state.mode]
        for frame,color in ((stem+'_2_001.png',self.secondary),
                            (stem+'_001.png',self.primary),
                            (stem+'_extra_001.png',(255,255,255))):
            image = self.sprite(frame,color,round(-state.rotation)%360,False,state.gravity==-1,255,.6 if state.mini else 1)
            if image:
                self.screen.blit(image,image.get_rect(center=position))
        if state.mode in ('ship', 'ufo'):
            rider = self.sprite('player_01_001.png', self.primary,
                                round(-state.rotation)%360, False, state.gravity == -1)
            if rider:
                rider = pygame.transform.smoothscale(rider,
                    (max(1,round(rider.get_width()*.55)), max(1,round(rider.get_height()*.55))))
                radians = math.radians(state.rotation)
                offset = -5 if state.gravity == 1 else 5
                center = (round(position[0]-math.sin(radians)*offset),
                          round(position[1]+math.cos(radians)*offset))
                self.screen.blit(rider, rider.get_rect(center=center))

def main(level_id=17):
    pygame.display.init()
    pygame.font.init()
    display = app.Display()
    screen = display.screen
    loading=pygame.font.Font(None,34).render('Loading original level...',True,(242,232,203))
    screen.fill((17,12,35))
    screen.blit(loading,loading.get_rect(center=(480,270)))
    display.present(time.perf_counter()-1/60)
    level = Level(level_id)
    pygame.display.set_caption(f'{level.name} | GeoDash | 60 FPS')
    game = Game(level)
    renderer = Renderer(screen, level)
    music = app.Music(ASSETS/level.spec['song'])
    held = set()
    pending = False
    focused, running, paused = True, True, False
    accumulator = 0.
    previous = time.perf_counter()-1/60

    def clear_input():
        nonlocal pending, accumulator
        held.clear()
        pending, accumulator = False, 0.
        game.state.buffered = game.state.input_held = False
        if game.state.twin is not None:
            game.state.twin.buffered = game.state.twin.input_held = False
        game.previous_state = clone_state(game.state)

    def toggle_pause():
        nonlocal paused
        if game.started and not game.dead and not game.won:
            paused = not paused
            clear_input()

    while running:
        start = time.perf_counter()
        frame_duration = start-previous
        elapsed = min(frame_duration, 1/30)
        previous = start
        renderer.frames.append(frame_duration)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.WINDOWFOCUSLOST:
                focused = False
                clear_input()
            elif event.type == pygame.WINDOWFOCUSGAINED:
                focused, elapsed = True, 0
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_TAB:
                    toggle_pause()
                elif event.key in (pygame.K_SPACE, pygame.K_UP) and not paused:
                    if game.dead or game.won:
                        game.save_best()
                        game.reset(game.section if game.practice else 0)
                        clear_input()
                    pending = pending or event.key not in held
                    held.add(event.key)
                    game.started = True
                elif event.key == pygame.K_m:
                    music.toggle_mute()
                elif event.key == pygame.K_r:
                    game.reset(game.section if game.practice else 0)
                    paused = False
                    clear_input()
                elif event.key == pygame.K_p:
                    game.practice = not game.practice
                    game.reset(game.section if game.practice else 0)
                    paused = False
                    clear_input()
                elif game.practice and event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    direction = 1 if event.key == pygame.K_RIGHT else -1
                    game.reset((game.section+direction) % (len(level.portals)+1))
                    paused = False
                    clear_input()
            elif event.type == pygame.KEYUP:
                held.discard(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if pygame.Rect(910,4,40,40).collidepoint(event.pos):
                    toggle_pause()
                elif not paused:
                    if game.dead or game.won:
                        game.save_best()
                        game.reset(game.section if game.practice else 0)
                        clear_input()
                    held.add('mouse')
                    pending = True
                    game.started = True
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                held.discard('mouse')
        active = focused and not paused
        music.sync(game, active)
        if active:
            accumulator += elapsed
            while accumulator >= TICK:
                game.update(TICK, bool(held), pending)
                pending = False
                accumulator -= TICK
        if game.dead or game.won:
            music.sync(game, active)
        fps = len(renderer.frames)/max(sum(renderer.frames), .001)
        renderer.draw(game, bool(held), elapsed if active else 0, fps,
                      alpha=accumulator/TICK if active else 1)
        if not active:
            renderer.draw_pause(focused)
        game.save_best()
        display.present(start)
    pygame.quit()


if __name__=='__main__':
    main()

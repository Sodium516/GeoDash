"""Checks for the original-data player; the classic-course tests remain separate."""
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import copy
import itertools
import random
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

import blast_processing as b


class OriginalLevelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level = b.Level()

    def empty_level(self):
        level = copy.copy(self.level)
        level.collision_buckets = defaultdict(list)
        level.interactive_buckets = defaultdict(list)
        return level

    def relocated(self,obj,x,y,**changes):
        from dataclasses import replace
        dx,dy=x-obj.x,y-obj.y
        return replace(obj,x=x,y=y,
                       points=tuple((px+dx,py+dy) for px,py in obj.points),
                       bounds=tuple(v+(dx if i%2==0 else dy) for i,v in enumerate(obj.bounds)),
                       **changes)

    def test_original_object_count_and_portal_positions(self):
        self.assertEqual(self.level.raw_count, 11552)
        self.assertEqual([o.x for o in self.level.portals if o.id == 660], [4437, 13335])
        self.assertEqual([o.x for o in self.level.portals if o.id in (286,287)], [15369,16621])
        self.assertEqual(len(self.level.portals), 13)

    def test_cube_jump_height_and_forward_speed_in_original_units(self):
        level = self.empty_level()
        state = b.State()
        apex = state.y
        for tick in range(240):
            b.simulate(level,state,b.TICK,tick==0,tick==0)
            apex=max(apex,state.y)
        self.assertAlmostEqual(state.x,311.5801019668579,delta=.001)
        self.assertTrue(63 < apex-15 < 65, apex-15)
        self.assertEqual(state.y,15)
        self.assertTrue(state.grounded)

    def test_wave_diagonal_and_mirrored_dual(self):
        state = b.State(y=150,mode='wave',grounded=False,dual=True)
        level=self.empty_level()
        b.simulate(level,state,b.TICK,True,True)
        # The new input is queued after movement; next tick uses the hold.
        y=state.y;x=state.x
        b.simulate(level,state,b.TICK,True,False)
        self.assertAlmostEqual(state.y-y,state.x-x,delta=.00001)
        self.assertTrue(state.dual)
        self.assertIsNotNone(state.twin)
        self.assertAlmostEqual(state.y+state.twin.y,300,delta=.0001)

    def test_ball_flip_and_ufo_one_impulse_per_press(self):
        state = b.State(mode='ball')
        level=self.empty_level()
        b.simulate(level,state,b.TICK,True,True)
        self.assertEqual(state.gravity,-1)
        self.assertGreater(state.vy,0)
        b.simulate(level,state,b.TICK,True,False)
        self.assertEqual(state.gravity,-1)
        state=b.State(y=150,mode='ufo',grounded=False)
        b.simulate(level,state,b.TICK,True,True)
        # Native pushButton queues a flap; updateJump on the next tick
        # applies 7 then gravity, giving the measured normal-size 6.871.
        self.assertLess(state.vy,0)
        self.assertTrue(state.buffered)
        b.simulate(level,state,b.TICK,True,False)
        self.assertEqual(state.vy,6.871)
        self.assertFalse(state.buffered)
        vy=state.vy
        b.simulate(level,state,b.TICK,True,False)
        self.assertLess(state.vy,vy)

    def test_swing_queues_flip_and_hold_does_not_repeat(self):
        level=self.empty_level()
        state=b.State(y=150,mode='swing',grounded=False)
        b.simulate(level,state,b.TICK,True,True)
        self.assertEqual(state.gravity,1)
        self.assertEqual(state.vy,-.086)
        self.assertTrue(state.buffered)
        b.simulate(level,state,b.TICK,True,False)
        self.assertEqual(state.gravity,-1)
        self.assertEqual(state.vy,.017)
        self.assertFalse(state.buffered)
        for _ in range(5):b.simulate(level,state,b.TICK,True,False)
        self.assertEqual(state.gravity,-1)
        b.simulate(level,state,b.TICK,False,False)
        b.simulate(level,state,b.TICK,True,True)
        self.assertEqual(state.gravity,-1)
        b.simulate(level,state,b.TICK,True,False)
        self.assertEqual(state.gravity,1)

    def test_queued_swing_flips_match_native_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_swing_samples.json').read_text())
        for row in report['cases']:
            with self.subTest(row=row):
                state=b.State(y=150,mode='swing',grounded=False,input_held=True,
                              buffered=True,mini=row['mini'],gravity=-1 if row['upside'] else 1,
                              vy=row['vy'])
                b.simulate(self.empty_level(),state,b.TICK,True,False)
                self.assertEqual(state.vy,row['native_vy'])
                self.assertEqual(state.gravity==-1,row['native_upside'])
                self.assertFalse(state.buffered)

    def test_ground_impulses_match_native_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_ground_samples.json').read_text())
        for row in report['cases']:
            with self.subTest(row=row):
                state=b.State(mode=row['mode'],mini=row['mini'],gravity=-1 if row['upside'] else 1)
                b.ground_action(self.empty_level(),state)
                self.assertAlmostEqual(state.vy,row['native_vy'],places=12)

    def test_ramp_jump_impulses_match_native_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_slope_jump_samples.json').read_text())
        for row in report['cases']:
            with self.subTest(row=row):
                state=b.State(mode=row['mode'],mini=row['mini'],gravity=-1 if row['upside'] else 1,
                              time=row['age'],slope_since=0)
                raw=row['slope']*state.gravity
                b.ground_action(self.empty_level(),state,ramp_velocity=raw)
                self.assertAlmostEqual(state.vy,row['native_vy'],places=11)

    def test_brick_platforms_are_indexed_and_original_electroman_route_advances(self):
        import original_replays
        level=b.Level(13)
        bricks=[o for o in level.objects if o.type==21]
        self.assertEqual(len(bricks),32)
        self.assertTrue(all(any(o in bucket for bucket in level.collision_buckets.values()) for o in bricks))
        for suffix,minimum in (('dp',19),('coins',58)):
            result=original_replays.run(original_replays.load(b.ROOT/f'reference/original_replays/solution_lv13_{suffix}.txt'),level)
            self.assertGreater(result['progress'],minimum)

    def test_brick_platform_lands_cube_and_does_not_kill_pass_through(self):
        brick=next(o for o in b.Level(13).objects if o.type==21)
        brick=self.relocated(brick,0,150)
        level=self.empty_level();level.collision_buckets[0]=[brick]
        landing=b.State(y=178,vy=-1,grounded=False)
        b.simulate(level,landing,b.TICK,False,False)
        self.assertTrue(landing.grounded)
        self.assertEqual(landing.y,180)
        for mode in ('cube','wave'):
            state=b.State(y=150,vy=10,grounded=False,mode=mode)
            b.simulate(level,state,b.TICK,False,False)
            self.assertFalse(state.dead)

    def test_stair_snap_checks_previous_platform_type(self):
        from dataclasses import replace
        block=next(o for o in self.level.objects if o.id==165 and o.x==20025 and o.y==45)
        target=self.relocated(block,90,60)
        state=b.State(x=100,snap_uid=1,snap_type=21,snap_x=0,snap_y=0,snap_offset=3)
        b.snap_stair(state,target)
        self.assertEqual(state.x,100)
        state=b.State(x=100,snap_uid=1,snap_type=0,snap_x=0,snap_y=0,snap_offset=3)
        b.snap_stair(state,replace(target,type=21))
        self.assertEqual(state.x,99)
        self.assertEqual(state.snap_type,21)

    def test_unused_bitmap_font_is_not_retained_by_text_cache(self):
        import gc,weakref
        b.pygame.display.init();b.pygame.display.set_mode((960,540))
        font=b.BitmapFont()
        image=font.render('Cache lifecycle')
        self.assertIs(image,font.render('Cache lifecycle'))
        reference=weakref.ref(font)
        del font
        gc.collect()
        self.assertIsNone(reference())

    def test_airborne_robot_without_jump_latch_matches_native_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_robot_samples.json').read_text())
        for row in report['cases']:
            with self.subTest(row=row):
                level=self.empty_level()
                state=b.State(y=150,mode='robot',grounded=False,mini=row['mini'],
                              gravity=-1 if row['upside'] else 1,vy=row['vy'],input_held=row['held'])
                b.simulate(level,state,b.TICK,row['held'],False)
                self.assertEqual(state.vy,row['native_vy'])

    def test_robot_pad_cancels_ground_jump_sustain(self):
        level=self.empty_level()
        state=b.State(y=150,mode='robot',grounded=False,input_held=True)
        b.ground_action(level,state)
        vy=state.vy
        b.simulate(level,state,b.TICK,True,False)
        self.assertEqual(state.vy,vy)
        pad=self.relocated(next(o for o in self.level.objects if o.id==35),state.x,state.y,bit=1)
        level.interactive_buckets[0]=[pad]
        b.simulate(level,state,b.TICK,True,False)
        self.assertEqual(state.vy,16)
        self.assertFalse(state.robot_jumping)
        b.simulate(level,state,b.TICK,True,False)
        self.assertLess(state.vy,16)

    def test_robot_ground_jump_bonus_matches_native_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_robot_jump_samples.json').read_text())
        for row in report['cases']:
            with self.subTest(row=row):
                state=b.State(mode='robot',mini=row['mini'],gravity=-1 if row['upside'] else 1,
                              time=row['age'],slope_since=0)
                b.ground_action(self.empty_level(),state,ramp_velocity=row['slope']*state.gravity)
                self.assertAlmostEqual(state.vy,row['native_vy'],places=11)
                self.assertTrue(state.robot_jumping)

    def test_flying_rotation_matches_native_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_rotation_samples.json').read_text())
        for row in report['cases']:
            with self.subTest(row=row):
                state=b.State(mode=row['mode'],mini=row['mini'],gravity=-1 if row['upside'] else 1,
                              rotation=-row['rotation'])
                rotation=b.flight_rotation(state,b.native_position(1.3),row['dy'],b.TICK)
                error=abs((rotation+row['native_rotation']+180)%360-180)
                self.assertLess(error,.00002)

    def test_orb_impulses_match_native_mode_size_gravity_samples(self):
        import json
        from dataclasses import replace
        report=json.loads((b.ROOT/'reference/native_orb_samples.json').read_text())
        kinds={11:36,12:141,13:84,29:1022,32:1330,35:1333}
        base=next(o for o in self.level.objects if o.id==36)
        for row in report['cases']:
            with self.subTest(row=row):
                level=self.empty_level()
                orb=self.relocated(replace(base,id=kinds[row['kind']]),0,150,bit=1)
                level.interactive_buckets[0]=[orb]
                state=b.State(y=150,mode=row['mode'],mini=row['mini'],gravity=-1 if row['upside'] else 1,
                              buffered=True,input_held=True,boost=row['boost'])
                b.touch_objects(level,state)
                self.assertAlmostEqual(state.vy,row['native_vy'],places=11)
                self.assertEqual(state.gravity==-1,row['native_upside'])
                self.assertEqual(state.boost,row['native_boost'])
                self.assertFalse(state.buffered)

    def test_yellow_orb_preserves_existing_ship_boost_into_next_tick(self):
        level=self.empty_level()
        orb=self.relocated(next(o for o in self.level.objects if o.id==36),0,150,bit=1)
        level.interactive_buckets[0]=[orb]
        state=b.State(y=150,mode='ship',grounded=False,buffered=True,boost=True)
        b.touch_objects(level,state)
        self.assertTrue(state.boost)
        self.assertEqual(state.vy,11.18)
        b.simulate(level,state,b.TICK,False,False)
        self.assertGreater(state.vy,8)
        self.assertTrue(state.boost)

    def test_pad_wrappers_match_native_impulses_boost_and_slope_flags(self):
        import json
        from dataclasses import replace
        report=json.loads((b.ROOT/'reference/native_pad_samples.json').read_text())
        kinds={8:35,9:140,34:1332}
        base=next(o for o in self.level.objects if o.id==35)
        for row in report['cases']:
            with self.subTest(row=row):
                level=self.empty_level()
                pad=self.relocated(replace(base,id=kinds[row['kind']]),0,150,bit=1)
                level.interactive_buckets[0]=[pad]
                state=b.State(y=150,mode=row['mode'],mini=row['mini'],gravity=-1 if row['upside'] else 1,
                              boost=row['boost'],on_slope=True)
                self.assertTrue(b.touch_objects(level,state))
                self.assertAlmostEqual(state.vy,row['native_vy'],places=11)
                self.assertEqual(state.boost,row['native_boost'])
                self.assertEqual(state.on_slope,row['native_on_slope'])
                self.assertFalse(row['native_was_on_slope'])

    def test_pad_launch_is_not_overwritten_by_downhill_slope_release(self):
        level=self.empty_level()
        pad=self.relocated(next(o for o in self.level.objects if o.id==35),0,150,bit=1)
        level.interactive_buckets[0]=[pad]
        state=b.State(y=150,on_slope=True,slope_m=-1,slope_since=0,time=.2)
        b.simulate(level,state,b.TICK,False,False)
        self.assertEqual(state.vy,16)
        self.assertFalse(state.on_slope)
        self.assertFalse(state.dead)

    def test_wave_velocity_and_position_match_native_all_speed_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_wave_samples.json').read_text())
        for row in report['cases']:
            with self.subTest(row=row):
                self.assertEqual(list(b.SPEED_RULES[row['speed']]),row['native_speed_settings'])
                state=b.State(x=row['x'],y=150,mode='wave',grounded=False,speed=row['speed'],mini=row['mini'],
                              gravity=-1 if row['upside'] else 1,input_held=row['held'])
                b.simulate(self.empty_level(),state,b.TICK,row['held'],False)
                self.assertAlmostEqual(state.vy,row['native_vy'],places=12)
                self.assertEqual([state.x,state.y],row['native_position'])

    def test_wave_exit_carries_native_stored_velocity(self):
        level=self.empty_level()
        portal=self.relocated(next(o for o in self.level.objects if o.id==12),0,150,bit=1)
        level.interactive_buckets[0]=[portal]
        state=b.State(y=150,mode='wave',grounded=False,input_held=True)
        b.simulate(level,state,b.TICK,True,False)
        self.assertEqual(state.mode,'cube')
        self.assertAlmostEqual(state.vy,2.5965,places=12)

    def test_native_position_integration_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_position_samples.json').read_text())
        step=b.native_position(b.native_position(.25)*b.native_position(.9))
        for row in report['cases']:
            with self.subTest(row=row):
                x=b.native_translate(b.native_position(row['x']),b.SPEED*b.TICK)
                y=b.native_translate(b.native_position(row['y']),row['vy']*step)
                self.assertEqual([x,y],row['native_position'])

    def test_queued_ufo_flaps_match_native_velocity_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_flap_samples.json').read_text())
        for row in report['cases']:
            with self.subTest(row=row):
                state=b.State(y=150,mode='ufo',grounded=False,input_held=True,
                              buffered=True,mini=row['mini'],gravity=-1 if row['upside'] else 1,
                              vy=row['vy'])
                b.simulate(self.empty_level(),state,b.TICK,True,False)
                self.assertEqual(state.vy,row['native_vy'])
                self.assertFalse(state.buffered)

    def test_ball_buffers_until_landing_and_consumes_the_press(self):
        level=self.empty_level()
        state=b.State(y=100,mode='ball',grounded=False)
        b.simulate(level,state,b.TICK,True,True)
        self.assertTrue(state.buffered)
        for _ in range(240):
            if state.grounded:break
            b.simulate(level,state,b.TICK,True,False)
        self.assertTrue(state.grounded)
        self.assertEqual(state.gravity,1)
        b.simulate(level,state,b.TICK,True,False)
        self.assertEqual(state.gravity,-1)
        self.assertFalse(state.buffered)
        for _ in range(480):b.simulate(level,state,b.TICK,True,False)
        self.assertTrue(state.grounded)
        self.assertEqual(state.gravity,-1)  # Holding is not automatic repeat flipping.

    def test_releasing_cancels_a_buffered_ball_flip(self):
        level=self.empty_level()
        state=b.State(y=50,mode='ball',grounded=False)
        b.simulate(level,state,b.TICK,True,True)
        b.simulate(level,state,b.TICK,False,False)
        for _ in range(240):b.simulate(level,state,b.TICK,False,False)
        self.assertEqual(state.gravity,1)
        self.assertTrue(state.grounded)
        self.assertFalse(state.buffered)

    def test_orb_consumes_one_held_press_and_requires_rearming(self):
        from dataclasses import replace
        level=self.empty_level()
        state=b.State(y=150,mode='ball',grounded=False)
        b.simulate(level,state,b.TICK,True,True)  # Press before entering orb range.
        orb=next(o for o in self.level.objects if o.id==36)
        first=self.relocated(orb,state.x,state.y,bit=1)
        second=self.relocated(orb,state.x,state.y,uid=orb.uid+100000,bit=2)
        level.interactive_buckets[0]=[first,second]
        b.simulate(level,state,b.TICK,True,False)
        self.assertTrue(state.used & 1)
        self.assertFalse(state.used & 2)
        self.assertFalse(state.buffered)
        b.simulate(level,state,b.TICK,True,False)
        self.assertFalse(state.used & 2)
        b.simulate(level,state,b.TICK,False,False)
        b.simulate(level,state,b.TICK,True,True)
        self.assertTrue(state.used & 2)

    def test_released_press_does_not_trigger_a_later_orb(self):
        from dataclasses import replace
        level=self.empty_level()
        state=b.State(y=150,mode='ball',grounded=False)
        b.simulate(level,state,b.TICK,True,True)
        b.simulate(level,state,b.TICK,False,False)
        orb=next(o for o in self.level.objects if o.id==36)
        level.interactive_buckets[0]=[self.relocated(orb,state.x,state.y,bit=1)]
        b.simulate(level,state,b.TICK,False,False)
        self.assertFalse(state.used & 1)

    def test_ring_rectangular_corner_and_previous_contact_press(self):
        level=self.empty_level()
        orb=self.relocated(next(o for o in self.level.objects if o.id==36),0,100,bit=1)
        level.interactive_buckets[0]=[orb]
        # Both axes overlap the native 36x36 ring. The former fitted circle
        # rejected this corner, despite the native rectangular contact.
        state=b.State(x=32,y=132,grounded=False,buffered=True,input_held=True)
        b.touch_objects(level,state)
        self.assertTrue(state.used & 1)
        # A new press can use the preceding collision pass's ring list after
        # moving just outside the rectangle, as native pushButton does.
        state=b.State(x=32,y=132,grounded=False)
        b.touch_objects(level,state)
        self.assertEqual(state.touched_rings,(orb.uid,))
        state.x=35
        state.buffered=True
        b.touch_objects(level,state)
        self.assertTrue(state.used & 1)
        self.assertEqual(state.touched_rings,())

    def test_legacy_inverted_ground_latch_and_compatibility_setting(self):
        for fixed in (False,True):
            level=self.empty_level()
            level.settings=dict(level.settings,kA32='1' if fixed else '0')
            state=b.State(y=225,gravity=-1,grounded=True)
            for _ in range(8):b.simulate(level,state,b.TICK,False,False)
            b.simulate(level,state,b.TICK,True,True)
            self.assertEqual(state.vy<0,not fixed)
        # The old latch must expire; it is tied to the native velocity test,
        # rather than an arbitrary grace timer or infinite airborne jump.
        level.settings=dict(level.settings,kA32='0')
        state=b.State(y=225,gravity=-1,grounded=True)
        for _ in range(15):b.simulate(level,state,b.TICK,False,False)
        b.simulate(level,state,b.TICK,True,True)
        self.assertGreater(state.vy,0)

    def test_wave_plain_ramp_uses_offset_surface_sample(self):
        ramp=next(o for o in self.level.objects if o.id==309 and o.x==5625 and o.y==15)
        state=b.State(x=5611.3735,y=10,mode='wave')
        self.assertFalse(b.wave_surface_contact(ramp,state))
        state.y=8
        self.assertTrue(b.wave_surface_contact(ramp,state))

    def test_narrow_pillar_landing_uses_leading_edge(self):
        level=self.empty_level()
        pillar=next(o for o in self.level.objects if o.id==470 and o.x==1695 and o.y==75)
        level.collision_buckets={14:[pillar]}
        state=b.State(x=1667,y=106,vy=-2,grounded=False)
        for _ in range(8):
            b.simulate(level,state,b.TICK,False,False)
        self.assertFalse(state.dead)
        self.assertEqual(state.y,105)
        self.assertTrue(state.grounded)

    def test_perspective_art_is_not_a_wall(self):
        perspective=[o for o in self.level.objects if 506 <= o.id <=559]
        self.assertTrue(perspective)
        self.assertTrue(all(o.type==7 for o in perspective))

    def test_original_color_timeline(self):
        self.assertEqual(self.level.color(1000,0),(71,0,210))
        self.assertNotEqual(self.level.color(1000,5000),self.level.color(1000,0))
        for x in (0,400,5000,15500,21000,30000):
            self.assertTrue(all(0 <= c <=255 for c in self.level.color(1000,x)))

    def test_unmodified_original_recordings_clear_validated_levels(self):
        import original_replays
        import hashlib,json
        folder=b.ROOT/'reference/original_replays'
        manifest=json.loads((folder/'manifest.json').read_text())
        for name,level_id in [('Stereo Madness.gdr2',1),('solution_lv2_dp.txt',2),
                              ('solution_lv3_dp.txt',3),('Dry Out.gdr2',4),
                              ('solution_lv5_dp.txt',5),('solution_lv6_dp.txt',6),
                              ('solution_lv7_dp.txt',7),('solution_lv8_dp.txt',8),
                              ('solution_lv9_dp.txt',9),('xStep.gdr2',10),
                              ('solution_lv11_dp.txt',11),('solution_lv14_coins.txt',14)]:
            path=folder/name
            source=next(e for e in manifest if e['file']==path.name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),source['sha256'])
            result=original_replays.run(original_replays.load(path),b.Level(level_id))
            self.assertTrue(result['passed'],result)

    def test_original_blast_processing_inputs_clear_both_wave_sections(self):
        import original_replays
        recording=original_replays.load(b.ROOT/'reference/original_replays/solution_lv17_dp.txt')
        result=original_replays.run(recording,self.level)
        # This is deliberately a section regression, not a full-level pass.
        self.assertGreaterEqual(result['progress'],80,result)

    def test_native_ramp_seat_uses_perpendicular_radius_and_extrapolated_line(self):
        ramp=self.relocated(next(o for o in self.level.objects if o.id==309),0,0)
        line=b.slope_line(ramp)
        self.assertAlmostEqual(b.slope_seat(ramp,0,15,line),15*2**.5,places=5)
        self.assertAlmostEqual(b.slope_seat(ramp,-25,15,line),-25+15*2**.5,places=5)
        self.assertEqual(b.slope_seat(ramp,30,15,line),30)

    def test_native_ramp_exit_velocity_depends_on_mode_and_ride_age(self):
        state=b.State(on_slope=True,slope_m=1,slope_since=0,time=.15)
        self.assertEqual(b.slope_exit_velocity(state),7.405)
        state.mode='ball'
        self.assertEqual(b.slope_exit_velocity(state),5.554)
        state.slope_ceiling=True
        state.time=1/240
        self.assertEqual(b.slope_exit_velocity(state),-2.222)

    def test_repeated_ramp_corner_releases_before_whole_body_leaves(self):
        ramp=self.relocated(next(o for o in self.level.objects if o.id==309),0,0)
        level=self.empty_level();level.collision_buckets[0]=[ramp]
        state=b.State(x=10,y=30,on_slope=True,slope_m=1,slope_since=0,
                      slope_target=30,time=.15,grounded=True)
        b.simulate(level,state,b.TICK,False,False)
        self.assertFalse(state.on_slope)
        self.assertFalse(state.grounded)
        self.assertLess(state.y,30)
        self.assertEqual(state.vy,7.405)

    def test_downhill_neighbor_does_not_replace_a_live_uphill_ride(self):
        up=self.relocated(next(o for o in self.level.objects if o.id==309),0,0)
        down=self.relocated(next(o for o in self.level.objects if o.id==321 and o.x==25305 and o.y==135),30,0)
        level=self.empty_level();level.collision_buckets[0]=[up,down]
        state=b.State(x=0,y=15*2**.5,mode='ufo',on_slope=True,slope_m=1,
                      slope_target=b.native_position(15*2**.5),slope_since=0,time=.15,grounded=True)
        b.simulate(level,state,b.TICK,False,False)
        self.assertTrue(state.on_slope)
        self.assertEqual(state.slope_m,1)
        self.assertLess(state.y,25)

    def test_exact_platform_edge_remains_a_valid_jump_contact(self):
        block=next(o for o in self.level.objects if o.id==165 and o.x==20025 and o.y==45)
        self.assertTrue(block.intersects(20055,75,15,15))
        self.assertFalse(block.intersects(20055.01,75,15,15))

    def test_rotated_hazard_checks_players_turned_box(self):
        spike=next(o for o in self.level.objects if o.id==720 and o.x==13680.3)
        state=b.State(x=13674.59765625,y=160.81356811523438,mode='wave',rotation=45)
        self.assertTrue(spike.intersects(state.x,state.y,5,5))
        self.assertFalse(b.hazard_contact(self.level,spike,state,5))

    def test_native_pad_strengths_and_gravity_pad_facing(self):
        from dataclasses import replace
        pad=next(o for o in self.level.objects if o.id==35)
        for mode,mini,kind,expected in [('ship',False,140,5.6),('ufo',True,140,5.12),
                                      ('spider',False,140,6.72),('swing',False,35,9.6),
                                      ('ship',True,1332,12.16)]:
            self.assertAlmostEqual(b.pad_velocity(replace(pad,id=kind),b.State(mode=mode,mini=mini)),expected,delta=.000001)
        level=self.empty_level()
        pad=self.relocated(replace(pad,id=67),0,150,bit=1)
        level.interactive_buckets[0]=[pad]
        state=b.State(y=150,gravity=-1)
        b.touch_objects(level,state)
        self.assertEqual(state.gravity,-1)
        self.assertFalse(state.used & 1)
        state.gravity=1
        b.touch_objects(level,state)
        self.assertEqual(state.gravity,-1)
        self.assertTrue(state.used & 1)

    def test_pad_impulse_precedes_platform_landing(self):
        level=self.empty_level()
        block=self.relocated(next(o for o in self.level.objects if o.id==165 and o.x==20025 and o.y==45),0,30)
        pad=self.relocated(next(o for o in self.level.objects if o.id==35),0,45,bit=1)
        level.collision_buckets[0]=[block]
        level.interactive_buckets[0]=[pad]
        state=b.State(y=59,vy=-1,grounded=False)
        expected_y=b.native_translate(59,-1.216*b.native_position(.225))
        b.simulate(level,state,b.TICK,False,False)
        self.assertFalse(state.dead)
        self.assertEqual(state.vy,16)
        self.assertEqual(state.y,expected_y)
        self.assertFalse(state.grounded)
        self.assertEqual(state.snap_uid,-1)

    def test_red_pad_exemption_preserves_flight_impulse(self):
        level=self.empty_level()
        state=b.State(mode='ship',y=150,vy=10,boost=True,grounded=False)
        b.simulate(level,state,b.TICK,False,False)
        self.assertGreater(state.vy,8)
        self.assertTrue(state.boost)
        state.vy=7
        b.simulate(level,state,b.TICK,False,False)
        self.assertFalse(state.boost)

    def test_freeflight_velocities_match_installed_native_binary_samples(self):
        import json
        report=json.loads((b.ROOT/'reference/native_velocity_samples.json').read_text())
        cases=[row for row in report['cases'] if 'native_vy' in row]
        self.assertGreaterEqual(len(cases),1840)
        self.assertEqual(report['dt'],.225)
        level=self.empty_level()
        for row in cases:
            with self.subTest(**row):
                level.settings=dict(level.settings,kA32='1' if row['fixed'] else '0')
                state=b.State(mode=row['mode'],y=150,vy=row['vy'],mini=row['mini'],
                              gravity=-1 if row['upside'] else 1,grounded=False,
                              input_held=row['held'],boost=row['boost'],dual=row['dual'])
                b.simulate(level,state,b.TICK,row['held'],False)
                self.assertAlmostEqual(state.vy,row['native_vy'],delta=.000001)

    def test_single_player_replay_release_is_shared_across_streams(self):
        import original_replays as r
        level=self.empty_level()
        inputs=[r.Input(0,True,player2=True),r.Input(3,False,player2=False)]
        replay=r.Replay(17,'mixed streams','test',240,.02,inputs)
        trace=r.run(replay,level,trace=True)['trace']
        self.assertTrue(trace[2][-1])
        self.assertFalse(trace[3][-1])
        self.assertEqual(replay.inputs,inputs)

    def test_cached_collision_axes_match_the_original_sat_calculation(self):
        def original(obj,x,y,rx,ry):
            left,bottom,right,top=obj.bounds
            if x+rx<=left or x-rx>=right or y+ry<=bottom or y-ry>=top:
                return False
            for a,c in zip(obj.points,obj.points[1:]+obj.points[:1]):
                ax,ay=a[1]-c[1],c[0]-a[0]
                center=x*ax+y*ay
                extent=abs(ax)*rx+abs(ay)*ry
                projections=[px*ax+py*ay for px,py in obj.points]
                if center+extent<=min(projections) or center-extent>=max(projections):
                    return False
            return True
        rng=random.Random(42)
        objects=rng.sample([o for o in self.level.objects if o.type in (0,2,25)],100)
        for obj in objects:
            for _ in range(12):
                x,y=obj.x+rng.uniform(-40,40),obj.y+rng.uniform(-40,40)
                rx,ry=rng.choice((5,7,15)),rng.choice((5,7,15))
                self.assertEqual(obj.intersects(x,y,rx,ry),original(obj,x,y,rx,ry))

    def test_interpolation_is_visual_only_and_skips_mode_transitions(self):
        game=b.Game(self.empty_level())
        game.started=True
        game.update(b.TICK,True,True)
        authoritative=copy.copy(game.state)
        previous=copy.copy(game.previous_state)
        view=b.Renderer.render_state(game,.5)
        self.assertAlmostEqual(view.x,(previous.x+authoritative.x)/2)
        self.assertAlmostEqual(view.y,(previous.y+authoritative.y)/2)
        self.assertEqual(game.state,authoritative)
        self.assertEqual(game.previous_state,previous)
        game.state.mode='wave'
        self.assertIs(b.Renderer.render_state(game,.5),game.state)

    def test_camera_easing_is_independent_of_render_rate(self):
        b.pygame.display.init();b.pygame.font.init()
        self.addCleanup(b.pygame.quit)
        screen=b.pygame.display.set_mode((960,540))
        game=b.Game(self.level)
        a,b_renderer=b.Renderer(screen,self.level),b.Renderer(screen,self.level)
        a.draw(game,False);b_renderer.draw(game,False)
        game.state.mode='ship'
        game.state.y=150
        game.started=True
        for _ in range(30):a.draw(game,False,1/30)
        for _ in range(60):b_renderer.draw(game,False,1/60)
        self.assertAlmostEqual(a.camera_y,b_renderer.camera_y,places=8)

    def test_main_pause_focus_restart_and_pause_button_do_not_trigger_jumps(self):
        pygame=b.pygame
        original_draw=b.Renderer.draw
        snapshots={}
        events={
            1:pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE),
            4:pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=(930,24)),
            6:pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE),
            8:pygame.event.Event(pygame.KEYDOWN,key=pygame.K_TAB),
            11:pygame.event.Event(pygame.WINDOWFOCUSLOST),
            14:pygame.event.Event(pygame.WINDOWFOCUSGAINED),
            17:pygame.event.Event(pygame.KEYDOWN,key=pygame.K_r),
            19:pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=(930,24)),
            20:pygame.event.Event(pygame.KEYDOWN,key=pygame.K_SPACE),
            23:pygame.event.Event(pygame.QUIT),
        }
        def capture(renderer,game,*args,**kwargs):
            original_draw(renderer,game,*args,**kwargs)
            frame=len(snapshots)+1
            snapshots[frame]=(game.x,game.started)
            if frame in events:pygame.event.post(events[frame])
        clock=itertools.count(0,1/60)
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(b,'BEST_FILE',Path(folder)/'best.txt'), \
                patch.object(b.Renderer,'draw',capture), \
                patch.object(b.app,'pace_frame',lambda start:None), \
                patch.object(b.time,'perf_counter',side_effect=lambda:next(clock)):
            b.main()
        self.assertGreater(snapshots[4][0],0)
        self.assertEqual(snapshots[5][0],snapshots[8][0])
        self.assertGreater(snapshots[9][0],snapshots[8][0])
        self.assertEqual(snapshots[12][0],snapshots[15][0])
        self.assertGreater(snapshots[16][0],snapshots[15][0])
        self.assertEqual(snapshots[18],(self.level.initial_state().x,False))
        self.assertEqual(snapshots[20],(self.level.initial_state().x,False))
        self.assertGreater(snapshots[21][0],0)

    def test_game_class_replays_the_same_inputs_as_the_verifier(self):
        import original_replays
        level=b.Level(4)
        recording=original_replays.load(b.ROOT/'reference/original_replays/Dry Out.gdr2')
        expected=original_replays.run(recording,level)
        game=b.Game(level);game.started=True
        result=original_replays.run(recording,level,game=game)
        self.assertEqual(result,expected)
        self.assertTrue(game.won)
        self.assertFalse(game.dead or game.practice)
        self.assertEqual(game.attempt,1)
        self.assertEqual(game.progress,100)

    def test_ball_flip_uses_native_half_velocity(self):
        state=b.State(mode='ball')
        b.simulate(self.empty_level(),state,b.TICK,True,True)
        self.assertAlmostEqual(state.vy,3.354,places=5)
        self.assertEqual(state.gravity,-1)
        self.assertEqual(state.y,15)

    def test_ball_portal_uses_240_unit_corridor(self):
        level=self.empty_level()
        portal=next(o for o in self.level.objects if o.id==47)
        level.interactive_buckets[int(portal.x//120)]=[portal]
        state=b.State(x=portal.x,y=portal.y,mode='ship',grounded=False)
        b.simulate(level,state,b.TICK,False,False)
        self.assertEqual(state.mode,'ball')
        self.assertEqual(state.ceiling-state.floor,240)

    def test_ball_pad_has_ball_strength_and_cube_pad_is_not_capped_at_15(self):
        from dataclasses import replace
        pad=next(o for o in self.level.objects if o.id==35)
        for mode,impulse in [('ball',9.6),('cube',16.)]:
            level=self.empty_level()
            points=b.transform(b.box_points(25,4),0,2)
            native_pad=replace(pad,x=0,y=2,points=points,bounds=(-12.5,0,12.5,4),bit=1)
            level.interactive_buckets[0]=[native_pad]
            state=b.State(mode=mode)
            b.simulate(level,state,b.TICK,False,False)
            self.assertAlmostEqual(state.vy,impulse,delta=.000001)
            if mode=='cube':
                b.simulate(level,state,b.TICK,False,False)
                self.assertGreater(state.vy,15)

    def test_all_original_sections_render_with_real_textures(self):
        b.pygame.display.init();b.pygame.font.init()
        self.addCleanup(b.pygame.quit)
        screen=b.pygame.display.set_mode((960,540))
        renderer=b.Renderer(screen,self.level)
        with tempfile.TemporaryDirectory() as folder, patch.object(b,'BEST_FILE',Path(folder)/'best.txt'):
            game=b.Game(self.level)
            renderer.draw(game,False)
            for i in range(1,len(self.level.portals)+1):
                game.reset(i)
                game.started=True
                renderer.draw(game,True)
            self.assertTrue(renderer.bitmap_font.glyphs)


class NativeCompositingTests(unittest.TestCase):
    def test_portal_art_wraps_around_player(self):
        pygame=b.pygame
        pygame.display.init();pygame.font.init()
        level=b.Level()
        portal=next(obj for obj in level.objects if obj.id==660)
        game=b.Game(level);game.started=True;game.state.x=portal.x
        game.state.mode='wave';game.state.y=150
        renderer=b.Renderer(pygame.display.set_mode((960,540)),level)
        calls=[]
        with patch.object(renderer,'sprite',side_effect=lambda frame,*args:calls.append(frame)), \
                patch.object(renderer,'icon',side_effect=lambda *args:calls.append('PLAYER')):
            renderer.draw(game,False)
        back=level.metadata['660']['back']
        self.assertLess(calls.index(back),calls.index('PLAYER'))
        self.assertLess(calls.index('PLAYER'),calls.index(portal.frame))


class DisplayTests(unittest.TestCase):
    def test_native_display_requests_scaled_vsync(self):
        with patch.object(b.pygame.display, 'get_driver', return_value='cocoa'), \
                patch.object(b.pygame.display, 'set_mode') as mode:
            display = b.app.Display()
        mode.assert_called_once_with((960, 540), b.pygame.SCALED, vsync=1)
        calls = []
        with patch.object(b.app, 'pace_frame', side_effect=lambda t:calls.append(('pace', t))), \
                patch.object(b.pygame.display, 'flip', side_effect=lambda:calls.append(('flip',))):
            display.present(10)
        self.assertEqual(calls, [('pace', 9.997), ('flip',)])

    def test_unavailable_renderer_uses_software_fallback(self):
        with patch.object(b.pygame.display, 'get_driver', return_value='cocoa'), \
                patch.object(b.pygame.display, 'set_mode',
                             side_effect=[b.pygame.error('No renderer'), object()]) as mode, \
                patch('builtins.print'):
            display = b.app.Display()
        self.assertFalse(display.synchronized)
        self.assertEqual(mode.call_args.args, ((960, 540),))
        calls = []
        with patch.object(b.app, 'pace_frame', side_effect=lambda t:calls.append(('pace', t))), \
                patch.object(b.pygame.display, 'flip', side_effect=lambda:calls.append(('flip',))):
            display.present(10)
        self.assertEqual(calls, [('flip',), ('pace', 10)])


if __name__=='__main__':
    unittest.main()

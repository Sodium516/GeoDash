"""Headless regression checks: .venv/bin/python -m unittest -v"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import geometry_dash as g
import pygame


class GameTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.score_patch = patch.object(g, 'SCORE_FILE', Path(self.temp.name) / 'best.txt')
        self.score_patch.start()
        self.addCleanup(self.score_patch.stop)
        self.game = g.Game()

    def start(self, mode):
        index = next(i for i, (_, name) in enumerate(g.SECTIONS) if name == mode)
        self.game.reset(index)
        self.game.started = True
        return self.game

    def test_waiting_and_short_tap_jump(self):
        a = self.game
        a.update(.1, True, True)
        self.assertEqual(a.x, 0)
        a.started = True
        a.update(g.PHYSICS_DT, False, True)
        self.assertLess(a.vy, 0)  # A down/up pair within one frame still jumps.
        vy = a.vy
        a.update(g.PHYSICS_DT, True, True)
        self.assertGreater(a.vy, vy)  # No extra midair jump without a ring.

    def test_wave_has_equal_diagonal_speed_and_reverses(self):
        a = self.start('wave')
        x, y = a.x, a.y
        a.update(g.PHYSICS_DT, True)
        self.assertAlmostEqual(a.x - x, y - a.y)
        a.update(g.PHYSICS_DT, False)
        self.assertAlmostEqual(a.y, y)

    def test_ship_thrust_and_ufo_taps(self):
        a = self.start('ship')
        a.update(g.PHYSICS_DT, True)
        self.assertLess(a.vy, 0)
        a = self.start('ufo')
        a.update(g.PHYSICS_DT, True, True)
        vy = a.vy
        a.update(g.PHYSICS_DT, True, False)
        self.assertGreater(a.vy, vy)
        a.update(g.PHYSICS_DT, False, True)
        self.assertLess(a.vy, vy + 1)

    def test_ball_flips_once_and_cannot_flip_midair(self):
        a = self.start('ball')
        a.update(g.PHYSICS_DT, True, True)
        self.assertEqual(a.gravity, -1)
        a.update(g.PHYSICS_DT, True, True)
        self.assertEqual(a.gravity, -1)

    def test_all_portals_transition_without_instant_death(self):
        for index in range(1, len(g.SECTIONS)):
            with self.subTest(index=index):
                a = self.game
                a.reset(index - 1)
                a.started = True
                a.x = g.SECTIONS[index][0] * g.LEVEL_LENGTH / 100 - .5
                a.update(g.PHYSICS_DT)
                self.assertEqual(a.mode, g.SECTIONS[index][1])
                self.assertFalse(a.dead)

    def test_gravity_portal_and_inverted_jump(self):
        a = self.game
        a.started = True
        a.x = 2099
        a.update(g.PHYSICS_DT)
        self.assertEqual(a.gravity, -1)
        a.y = g.TOP + 12
        a.vy = 0
        a.grounded = True
        a.update(g.PHYSICS_DT, True, True)
        self.assertGreater(a.vy, 0)
        self.assertGreater(a.y, g.TOP + 12)

    def test_cube_can_land_on_platform(self):
        a = self.game
        a.started = True
        a.x = 100
        a.y = 300 - 12 - .5
        a.vy = 240
        a.grounded = False
        a.buckets = {0: [g.rectangle(80, 300, 100, 155)]}
        a.update(g.PHYSICS_DT)
        self.assertFalse(a.dead)
        self.assertTrue(a.grounded)
        self.assertEqual(a.y, 288)

    def test_layout_is_repeatable(self):
        first, rings = g.build_level()
        second, other_rings = g.build_level()
        self.assertEqual([h.points for h in first], [h.points for h in second])
        self.assertEqual(rings, other_rings)

    def test_return_gravity_portal_has_a_safe_landing(self):
        a = self.game
        a.started = True
        a.x, a.y, a.gravity = 3000, g.TOP + 12, -1
        while a.x < 3540 and not a.dead:
            a.update(g.PHYSICS_DT)
        self.assertFalse(a.dead)
        self.assertTrue(a.grounded)
        self.assertEqual(a.y, g.FLOOR - 12)

    def test_entire_level_can_be_beaten_and_replayed_with_ordinary_inputs(self):
        import verify_level
        for dwell in (10, 12):
            with self.subTest(minimum_dwell=dwell):
                run = verify_level.generate_run(dwell)
                self.assertGreaterEqual(run.min_dwell, dwell)
                result = verify_level.replay(run)
                self.assertEqual(result.progress, 100)
                self.assertTrue(result.won)
                self.assertEqual(result.attempt, 1)
                self.assertFalse(g.SCORE_FILE.exists())

    def test_triangle_collision_ignores_empty_bounding_box_corner(self):
        spike = g.Hazard([(0, 100), (50, 0), (100, 100)], 'spike')
        self.assertFalse(spike.hits(pygame.Rect(0, 0, 8, 8)))
        self.assertTrue(spike.hits(pygame.Rect(45, 45, 10, 10)))

    def test_dual_twin_collides_independently(self):
        a = self.start('dual wave')
        a.y = 220
        a.buckets = {int(a.x // 480): [g.rectangle(a.x, 325, 50, 35)]}
        a.update(g.PHYSICS_DT, True)
        self.assertTrue(a.dead)

    def test_boundary_death_freezes_progress_and_restart_clears_state(self):
        a = self.start('wave')
        a.y = g.TOP + 8
        a.update(g.PHYSICS_DT, True)
        self.assertTrue(a.dead)
        x = a.x
        a.update(1, True, True)
        self.assertEqual(a.x, x)
        a.reset()
        self.assertFalse(a.dead or a.won or a.started)
        self.assertEqual(a.x, 0)
        self.assertEqual(len(a.trail), 0)

    def test_completion_persists_best_but_practice_does_not(self):
        a = self.game
        a.started = True
        a.x = g.LEVEL_LENGTH - 1
        a.update(g.PHYSICS_DT)
        self.assertTrue(a.won)
        a.save_best()
        self.assertEqual(g.Game().best, 100)
        a.best = 0
        a.practice = True
        a.reset(2)
        a.finish()
        self.assertFalse(a.pending_save)
        self.assertEqual(a.best, 0)

    def test_render_every_mode_and_overlay(self):
        pygame.display.init()
        pygame.font.init()
        self.addCleanup(pygame.quit)
        renderer = g.Renderer(pygame.display.set_mode((g.WIDTH, g.HEIGHT)))
        for index in range(len(g.SECTIONS)):
            a = self.game
            a.reset(index)
            renderer.draw(a, False, 60)
            a.started = True
            for _ in range(8):
                a.update(g.PHYSICS_DT, True)
            renderer.draw(a, True, 60)
            a.finish()
            renderer.draw(a, False, 60)


class MusicTests(unittest.TestCase):
    def setUp(self):
        self.music = g.Music()
        self.assertTrue(self.music.enabled, 'Bundled soundtrack must load and decode')
        self.addCleanup(pygame.mixer.quit)
        self.game = g.Game()

    def test_start_pause_resume_mute_and_stop(self):
        a, music = self.game, self.music
        music.sync(a)
        self.assertFalse(music.playing)
        a.started = True
        music.sync(a)
        self.assertTrue(pygame.mixer.music.get_busy())
        music.sync(a, False)
        self.assertTrue(music.paused)
        music.sync(a, True)
        self.assertFalse(music.paused)
        music.toggle_mute()
        self.assertEqual(pygame.mixer.music.get_volume(), 0)
        self.assertTrue(music.playing)
        music.toggle_mute()
        self.assertGreater(pygame.mixer.music.get_volume(), 0)
        a.dead = True
        music.sync(a)
        self.assertFalse(pygame.mixer.music.get_busy())

    def test_retry_and_practice_seek_without_restarting_every_frame(self):
        a, music = self.game, self.music
        with patch.object(pygame.mixer.music, 'play') as play:
            a.started = True
            music.sync(a)
            play.assert_called_once_with(loops=0, start=0)
            music.sync(a)
            self.assertEqual(play.call_count, 1)
            a.reset(8)
            music.sync(a)
            a.started = True
            music.sync(a)
            play.assert_called_with(loops=0, start=65)
            self.assertEqual(play.call_count, 2)
            a.reset()
            a.started = True
            music.sync(a)
            play.assert_called_with(loops=0, start=0)

    def test_missing_music_keeps_game_playable(self):
        with patch.object(g, 'MUSIC_FILE', Path('/nonexistent/blast_processing.mp3')):
            with patch('builtins.print'):
                music = g.Music()
        self.assertFalse(music.enabled)
        music.sync(self.game)
        music.toggle_mute()
        self.game.started = True
        self.game.update(g.PHYSICS_DT)
        self.assertGreater(self.game.x, 0)


if __name__ == '__main__':
    unittest.main()

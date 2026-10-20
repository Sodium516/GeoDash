"""Exercise menu navigation and launch boundaries without opening the native app."""
import os
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import pygame
import level_browser as browser
import user_settings
from level_catalog import entries


class MenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init(); pygame.font.init()
        cls.menu=browser.Menu(pygame.display.set_mode(browser.SIZE), entries(), dict(user_settings.DEFAULTS))

    def setUp(self):
        self.menu.view='home'; self.menu.selected=16; self.menu.notice=''
        self.menu.settings=dict(user_settings.DEFAULTS)

    def key(self, key):
        return self.menu.event(pygame.event.Event(pygame.KEYDOWN, key=key))

    def test_home_carousel_launch_and_back(self):
        self.assertIsNone(self.key(pygame.K_RETURN))
        self.assertEqual(self.menu.view,'levels')
        self.key(pygame.K_RIGHT)
        with patch.object(user_settings,'save',return_value=self.menu.settings) as save:
            self.assertEqual(self.key(pygame.K_RETURN),18)
            save.assert_called_once_with(selected=18)
        self.key(pygame.K_ESCAPE)
        self.assertEqual(self.menu.view,'home')
        self.assertEqual(self.key(pygame.K_ESCAPE),'quit')

    def test_library_mouse_selection_and_platformer_guard(self):
        self.menu.action('library'); self.menu.draw(0)
        rect, action=next((r,a) for r,a in self.menu.buttons if a==('select',26))
        self.menu.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=rect.center))
        self.assertEqual(self.menu.view,'levels')
        self.assertEqual(self.menu.levels[self.menu.selected]['id'],5004)
        self.assertIsNone(self.key(pygame.K_RETURN))
        self.assertIn('still being implemented',self.menu.notice)

    def test_garage_colors_persist_without_erasing_other_settings(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(user_settings,'PATH',Path(directory)/'settings.json'):
            user_settings.save(selected=18,volume=.3)
            self.menu.settings=user_settings.load()
            self.menu.action('appearance');self.menu.draw(0)
            rect,_=next((r,a) for r,a in self.menu.buttons if a==('color','primary',7))
            self.menu.event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1,pos=rect.center))
            self.menu.action(('color','secondary',2))
            saved=user_settings.load()
            self.assertEqual(saved['primary'],list(browser.PALETTE[7]))
            self.assertEqual(saved['secondary'],list(browser.PALETTE[2]))
            self.assertEqual(saved['selected'],18)
            self.assertEqual(saved['volume'],.3)
            self.menu.draw(0)

    def test_original_failure_stays_in_menu(self):
        with patch('original_game.launch',side_effect=OSError('Cannot open game')):
            self.key(pygame.K_o)
        self.assertEqual(self.menu.notice,'Cannot open game')
        self.assertEqual(self.menu.view,'home')

    def test_music_controls_persist_and_clamp(self):
        def save(**changes):
            return dict(self.menu.settings,**changes)
        with patch.object(user_settings,'save',side_effect=save):
            self.key(pygame.K_m)
            self.assertTrue(self.menu.settings['muted'])
            for _ in range(20):self.menu.action('quieter')
            self.assertEqual(self.menu.settings['volume'],0)
            for _ in range(20):self.menu.action('louder')
            self.assertEqual(self.menu.settings['volume'],1)


if __name__=='__main__':unittest.main()

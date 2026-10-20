"""The native launch option must use Launch Services and report failures."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import original_game


class OriginalLauncherTests(unittest.TestCase):
    def test_launches_installed_app_with_argument_boundaries(self):
        app=Path('/tmp/Steam Library/Geometry Dash.app')
        with patch.object(original_game,'installation',return_value=app), \
             patch.object(original_game.sys,'platform','darwin'), \
             patch.object(original_game.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
            self.assertIn('own menu',original_game.launch())
        run.assert_called_once_with(['open','-a',str(app)],capture_output=True,text=True,timeout=15)

    def test_missing_installation_and_failed_open_are_readable(self):
        with patch.object(original_game,'installation',return_value=None):
            with self.assertRaisesRegex(OSError,'not installed'):original_game.launch()
        with patch.object(original_game,'installation',return_value=Path('/tmp/Game.app')), \
             patch.object(original_game.sys,'platform','darwin'), \
             patch.object(original_game.subprocess,'run',return_value=subprocess.CompletedProcess([],1,stderr='Launch failed')):
            with self.assertRaisesRegex(OSError,'Launch failed'):original_game.launch()

    def test_timeout_is_reported_without_crashing_library(self):
        with patch.object(original_game,'installation',return_value=Path('/tmp/Game.app')), \
             patch.object(original_game.sys,'platform','darwin'), \
             patch.object(original_game.subprocess,'run',side_effect=subprocess.TimeoutExpired('open',15)):
            with self.assertRaisesRegex(OSError,'too long'):original_game.launch()


if __name__=='__main__':unittest.main()

"""Open the user's installed game. Never changes its application or save files."""
from pathlib import Path
import subprocess
import sys


def installation():
    candidates=[Path.home()/'Library/Application Support/Steam/steamapps/common/Geometry Dash/Geometry Dash.app',
                Path('/Applications/Geometry Dash.app')]
    return next((p for p in candidates if p.is_dir()),None)


def launch():
    app=installation()
    if app is None:raise OSError('Geometry Dash is not installed in the usual Steam location.')
    if sys.platform!='darwin':raise OSError('The installed-game launcher currently supports macOS.')
    try:
        result=subprocess.run(['open','-a',str(app)],capture_output=True,text=True,timeout=15)
    except subprocess.TimeoutExpired as error:
        raise OSError('macOS took too long to open Geometry Dash. Try opening it from Steam.') from error
    if result.returncode:
        raise OSError(result.stderr.strip() or 'macOS could not open Geometry Dash.')
    return 'Original game opened. Choose your level in its own menu.'


if __name__ == '__main__':
    try:
        print(launch())
    except OSError as error:
        raise SystemExit(str(error))

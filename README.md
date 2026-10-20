# GeoDash

Open the home screen:

```sh
.venv/bin/python geometry_dash.py
```

The 1280×720 menu uses original UHD artwork, with a level carousel, full library,
local progress, icon-color garage, and music settings. Garage colors persist and
apply to gameplay icons, animated robot/spider parts, and the wave trail.
Enter opens the carousel; Left / Right selects
a level; Enter plays it. Escape goes back. The user-provided “vintage vuitton” by
earfzilla loops in the menu; M toggles mute, and Settings adjusts its volume.
Menu music pauses when unfocused and hands off to the level soundtrack on play.

Click **Open original game**, or press **O**, to open your installed Geometry Dash.
Choose a level in the original game's own menu. This option uses the original
engine, physics, assets, and input behavior. It does not change application or save
files. You can also launch it directly:

```sh
.venv/bin/python geometry_dash.py --original
```

The Python recreation imports all 22 main levels, The Challenge, and four Tower
levels from the local Steam installation. The library opens the main levels and
Challenge; Tower gameplay is still being implemented. Original textures, songs,
backgrounds, and fonts are extracted locally. No internet is required to play.

**The Python recreation is unfinished.** Matching original object positions does
not establish matching physics or click timing. The library shows which levels
pass available original input recordings. A passing recording proves that route
works; it does not prove every possible input behaves identically. Consult
`reference/compatibility_report.json` for each fixture's result and source hash.
Other levels have known physics mismatches, including Blast Processing. The old
synthetic Blast Processing completion is archived and is not evidence of original
click-pattern compatibility.

Controls: Space / Up / left mouse acts; R retries; P toggles practice;
Left / Right chooses practice sections; Tab pauses; M mutes; Escape returns to the
library. Losing focus pauses play and music. Cube holds repeat jumps; buffered
ball/orb actions consume one held press when eligible. UFO actions require new
presses. Rendering targets 60 FPS with VSync requested, interpolated drawing,
cached sprites, and fixed 240 Hz physics. Driver support determines VSync availability.

For a fresh environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Run checks and audit unchanged reference inputs:

```sh
.venv/bin/python -m unittest -q
.venv/bin/python verify_level.py
.venv/bin/python verify_level.py --level 17
```

The audit preserves recording timestamps, level geometry, and normal collisions.
It reports mismatches rather than changing inputs to obtain a pass.
The audit exits with status 1 while any selected level fails or lacks a recording.
The audit includes unchanged standard and all-coins input plans. A completing
all-coins input route does not assert that this recreation awards those coins.
Some reference recordings were verified on Windows GD 2.209; the installed macOS game is 2.2081.
Those source differences remain relevant when interpreting failures.

Open a recreation directly with `--level 17`. The earlier shape-only course is
available with `--classic`; `verify_level.py --classic` checks that separate course.
`verify_original.py --search` is an experimental recreation route search, not an
original-game parity check.

See [ASSET_CREDITS.md](ASSET_CREDITS.md). Re-extract all installed resources with
`.venv/bin/python prepare_original_assets.py --all` without modifying the original
game. Keep extracted assets and Python modules together.
Run `.venv/bin/python prepare_high_res_assets.py` to extract the original UHD
artwork too. High-resolution sprites retain their original logical world sizes.

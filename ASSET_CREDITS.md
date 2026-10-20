# Original level resources

Official level data, textures, backgrounds, grounds, portals, and the Pusab
bitmap font were imported from the user's local Steam installation of
**Geometry Dash**, by **RobTop Games**. The installed game was only read;
its application files and save files were not modified.

`prepare_high_res_assets.py` additionally extracts 1,153 UHD textures and menu
resources to `assets/original/uhd`. The home screen uses the installed game's logo,
buttons, difficulty faces, backgrounds, ground, and Pusab font. These resources
remain RobTop Games' artwork. Menu soundtrack attribution is in MUSIC_CREDITS.md.

`prepare_original_assets.py` reproduces the extraction. Runtime uses the extracted
files in `assets/original` and `assets/levels` (plus the legacy Blast Processing data file).

The soundtrack is **Blast Processing / -BlastProcess- by Waterflame**. The original
level player uses the game's own cut from that installation. The earlier shape
course retains the separately downloaded track described in MUSIC_CREDITS.md.

Technical references:

- Original object ID/type/frame metadata: https://gist.github.com/hiimjasmine00/13165cc812c21f03e25a9bdb5280f8b9
- Level property format: https://github.com/gd-programming/gd.docs/blob/main/docs/resources/client/level-components/level-object.md
- Physics timing/constant reference: https://github.com/camila314/gdp

The Python simulation and renderer are independent implementations. Original game
resources remain owned by their respective creators.

The library additionally imports all installed official main, Challenge, and Tower
level files into `assets/levels`, their soundtracks, backgrounds, grounds, and
robot/spider animation descriptions. These remain the original creators' resources.

Collision geometry numerical definitions are derived from OpenGD's `LongData.cpp`:
https://github.com/dlcasto6/GD . Its GPL-3.0 license is preserved in
`reference/OpenGD-LICENSE.txt`; source attribution accompanies the geometry JSON.

Unmodified original input fixtures and their SHA-256 hashes are listed in
`reference/original_replays/manifest.json`. The Eclipse main-level GDR2 recordings
are from https://github.com/Sovenok-Hacker/EclipseGDMainMacros (CC0). Additional
input plans and measured physics references are from https://github.com/gdsolver/gdsolver
(MIT). Their licenses are preserved beside the recordings. GDR2 parsing follows
https://github.com/maxnut/GDReplayFormat/tree/gdr2 .

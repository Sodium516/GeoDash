# Active objective and current evidence

The objective remains all installed official levels with original click-pattern
compatibility, polished Python play, and the authorized original-engine launch
option. It is ACTIVE and incomplete. Importing assets or one passing route does
not establish universal physics parity.

27 installed levels are imported. Main levels and Challenge open in Python;
Tower controls/triggers remain unfinished. O / the original-game button /
`geometry_dash.py --original` opens the installed app via macOS Launch Services.
It opens its own menu and never edits the installed game or save files.

## Latest compatibility results

`reference/compatibility_report.json` is authoritative, with untouched fixture
SHA-256 hashes and each individual result. The first eleven main levels plus
Clubstep (12 total) each have at least one unchanged original input route that
completes. Some alternative fixtures still fail. Regression tests replay these
completing routes: Stereo Madness GDR2; Back On Track plan; Polargeist plan;
Dry Out GDR2; Base After Base plan; Can't Let Go plan; Jumper plan; Time Machine
plan; Cycles plan; xStep GDR2; Clutterfunk plan; Clubstep all-coins plan. The latter
is a route completion, not proof that the recreation awards all coins.

55 unchanged reference fixtures now include 22 additional original all-coins
input plans copied byte-for-byte from the same MIT gdsolver source. Parser accepts
both _dp and _coins names, without modifying input timing. Manifest has original
hashes, route descriptions, source version and license attribution.

Blast Processing reaches 82.98466%, frame19746, x25642.2598,y69.0221, UFO.
The preceding late ball section now clears using the original inputs. Ramp fixes
were required: perpendicular radius; extrapolated center-line with targetY bounds;
repeated clamped target releases the rider; native slope exit velocity formula;
ride age retained across grounded seams; a live uphill ride refuses a downhill
neighbor/shallow successor. The ball now reaches its blue orb and the following
pink orbs on the original presses, then switches to UFO. The current UFO dies on
saw98 at25665,45 just before the next press19746; y needs investigation. It rides
an uphill ramp around25190..25284 then launches. No arbitrary timing/geometry
changes were made. Full slope physics is still incomplete (native flight vy on
ramps, ramp jump coupling, complex/opposite-face contact, slope ordering).

Other best results: Electrodynamix80.94% ball;
Hexagon Force13.08%; Theory of Everything3.94%; Electroman Adventures6.51%;
TOE2 1.05%; Geometrical Dominator2.95%; Deadlocked3.78%; Fingerdash5.96%; Dash2.49%.
Challenge/Tower still lack reference recordings and Tower lacks platformer gameplay.

## Shared corrections made

- Native 240Hz input phases, float32 positions, 3dp velocity setter.
- Ball flip3.354, per-mode portal velocity halves, independent dual bodies.
- Rectangular orb contacts and preceding-tick contact list for a new press.
- Legacy upside-down grounded latch, gated by level kA32 (gravity fix).
- Wave solid kill half1.5, asymmetric slope sample3.072/-4.068 and vertical4;
  mini slope scale.7 is bracketed reference approximation.
- Turned hazards first check bounding rectangles then both oriented boxes,
  including player angle. Wave rotation eases .0625/tick (.1mini).
- Exact boundary contacts count. This fixed native cube presses at platform edges
  and let levels2,5,6,8 complete their plans.
- Upright rising cube/robot can clear a ledge inside10-unit top-face tolerance;
  avoids killing mini cube after Clutterfunk's final pad. No forced landing.
- Native per-mode/size pad table, facing gate for blue pads; pad attempt latch
  retained (reference confirms it persists for whole attempt).
- Red pad/orb and drop-orb velocity-limit exemption persists across mode changes,
  clears when incoming flight velocity is inside the normal band.
- Ball/spider gravity uses fixed base gravity across speed changes.
- Native fixed/legacy/dual falling thresholds; twin retains dual status.
- Replay streams share one button in single-player: a release on either releases
  it, rather than OR-ing independent held buttons. This let xStep GDR2 complete.
- Pause clears twin input too; size portal uses each mode's own contact radius.

## Validation and follow-up

58 tests pass, including all 12 completing routes and native slope/contact regressions. The suite checks native
launch errors with mocks, original route hashes, collisions, buffering, and UI pause.
Audit CLI now exits1 on failed/missing selected recordings;0 on all selected
passing. Selected invalid IDs reject. Reports write atomically. README truthful.
Headless busy dual-section render benchmark: mean4.94ms,p955.10ms (120warmedframes),
under16.67ms CPU frame budget. This is not an end-to-end VSync/tearing test.
Screenshot /private/tmp/geodash-render-check.png uses artificial player positioning,
so it is a rendering check, not a playthrough or legal player location.

Remaining: native slope riding/exit and jump coupling; flight trajectory mismatches;
moving objects, groups/spawn/toggle/alpha/camera triggers; rotated2.2 gameplay,
free movement and Tower platformer logic; exact visual layering/effects.
Old synthetic BP route is archived/obsolete, never proof of native input parity.

Primary references /private/tmp/geodash-references: gdsolver-main (MIT,Windows2.209,
measured rules but its model is itself approximate and needs an original-game oracle),
gdp-2.2 (decompiled methods), GD-main/OpenGD (GPL geometry definitions), untouched
Eclipse CC0GDR2. Licenses/attribution in ASSET_CREDITS.md. Native macOS2.2081 ARM64
read-only copy /private/tmp/geodash-arm64-reference and matching bindings
/private/tmp/geometrydash-bindings-current.bro. llvm-objdump without --macho respects
start/stop addresses. Never modify original application or saves.

Latest detail: globally changing the existing reverse surface order to native
ascending cells/uid was tested and reverted. It regressed an already passing
original route near18.75% because the current engine separates surfaces from
interactive/hazard phases; changing just the sort is not a faithful full pass.
Keep that limitation explicit and fix collision phase/order together later.

## Menu soundtrack and UHD follow-up

User identified a recent download: `/Users/aydinozkaya/Downloads/vintage vuitton.mp3`.
Copied unchanged to `assets/menu/vintage_vuitton.mp3` (2,653,221 bytes), SHA-256
verified identical. MenuMusic now starts the exact track on library entry, loops,
pauses on focus loss, resumes on focus gain, and stops before gameplay. M toggles
persisted mute. Library saves now merge settings instead of erasing preferences.
Dummy-audio smoke check verified MP3 decoding, playback, mute, pause/resume, stop.

UHD extraction produced 1,153 original textures. asset_paths prefers UHD while
Renderer and BitmapFont compensate logical dimensions. Native-style home/menu
redesign and warmed UHD performance verification remain pending.
Native velocity samples now cover 1,840 supported installed-binary cases; the
float32 flight-limit correction matches those samples. This is velocity evidence,
not full collision or level parity.

## Native-art menu implemented

Replaced the old 960x540 card grid with a 1280x720 original-UHD home screen,
single-level carousel, and complete 27-level library. Native logo, buttons,
difficulty icons, original Pusab font, blue background and scrolling ground.
Functional music settings (persistent mute and clamped volume), progress panel,
about panel, native launcher, keyboard navigation/back and platformer guard.
Entering a level stops the menu song; returning rebuilds menu and resumes it.
Compatibility badges still distinguish passing reference routes from unfinished
input matching. Existing gameplay logical dimensions and physics are unchanged.
Screenshots reviewed at /private/tmp/geodash-menu-{home,levels,library,...}.png.
63 tests pass, including four new navigation/launch/settings tests. Warmed dummy
render means/p95 ms: home1.33/1.43, carousel1.49/1.59, library2.46/2.53; UHD
gameplay starting scene1.63/1.65. These are CPU draw checks, not end-to-end
VSync measurements or busy-scene guarantees.

Experimental contact probe in /private/tmp/geodash_contact_probe.py now executes
collidedWithObjectInternal for one inverted-cube case (native x1016.5404,
y165.4088, old_y163.677, vy7.696, rect1020,140,30,30). Native returns1 and sets
y125. Minimal virtual position/rotation accessors and no real GameObject are
used; need a parameter sweep and native-method context before changing physics.
No physics rule changed from this single observation.

## Contact sweep and rejected hypothesis

Previous goal turn made progress: native-art menu and four navigation tests were
implemented and verified. This turn added reproducible native contact evidence:
reference/tools/native_contact_probe.py plus native_contact_samples.json (46
supported,14explicitly unsupported; all60cases retained). Hash-guarded read-only
ARM64 isolated collidedWithObjectInternal with synthetic virtual accessors, null
GameObject and static rectangle. Documentation in reference/NATIVE_PROBES.md.

Native isolated inverted contacts admit a broad snap. Tested translating that
directly into the recreation: TOE12 moved3.94→5.46%, but five previously passing
levels regressed (CantLetGo,TimeMachine,Cycles,Clutterfunk,Clubstep; several
alternative routes also failed). Experiment fully reverted from backup; report
was not overwritten (--no-save). Do not mistake the temporary audit for current
compatibility. Broad snap is not an accepted fix. Next: native caller filtering,
actual GameObject attributes and collision ordering, rather than extending a
null-object microprobe result into a universal contact rule.

## Static GameObject comparison

Previous turn produced evidence and a reverted hypothesis (progress, not a wait).
Extended native_contact_probe.py with --object: static regular solid GameObject,
original last-position/scale-delta helpers, synthetic rect/real-position/type
accessors. Saved reference/native_static_object_contact_samples.json. Same46
supported/14unsupported as prior60-case sweep; every supported result agrees.
Null-object omission alone is not the cause. Native collidedWithObject wrapper
(0x37dca0) simply dispatches non-sideways toInternal; earlier candidate selection,
ordering and prior state require investigation. Gameplay unchanged; prior63-test
pass remains applicable, no claim of new completing levels.

## UFO queued-input correction

Native pushButton0x38957c tail explicitly bypasses zero-dt updateJump for UFO,
ship,wave,swing, whereas grounded ball and cube invoke it. Corrected UFO edge
handling: queue fresh press at input phase; on following physics update apply
flap then native gravity and caps. Holding does not repeat flaps.
Added optional hash-guarded reference/tools/native_flap_probe.py and16 untouched
native numerical outputs in reference/native_flap_samples.json. Graphical burst
helper skipped; velocity helpers execute. New test covers all16cases, and existing
UFO timing test updated to measured native behavior. Existing63tests passed plus
new16-case test passed (64tests total across these runs).
Full unchanged55fixture audit --no-save retains all12passing levels. BP remains
82.98%UFO, so not a new route completion or full parity claim. No recordings,
geometry or click timings changed. Goal remains active.

## Native position arithmetic corrected

Previous goal turn made a verified UFO timing correction. This turn inspected
BP's failing saw contact: id98 at25665,45 radius12; atframe19746 the player is
x25642.2598,y69.0221. Installed objectIntersectsCircle0xfbf74 confirms the legacy
center/corner algorithm already used, so no unjustified smaller hazard was added.

Installed PlayerObject::update0x375754 integration slice0x375c6c..0x375df8 confirms
float32(dt*.9) and float32 displacement before CCPoint addition. Added
native_translate and corrected vertical displacement rounding. Native position
probe and16samples recorded; new regression compares all16. Existing64tests
passed after correction, then new position test passed (65across these runs).
Blast Processing still82.98%: numerical correction is not a route completion.
Full audit launched to refresh current authoritative report; see report output.

## Swing queued input

Previous goal turn corrected native displacement rounding and saved verified
numerical evidence. This turn corrected Swing input phase: fresh presses queue
until next updateJump, flip once, scale old velocity0.8, then apply new-gravity
acceleration. Added regression holding/releasing/repressing;66tests pass.
Added native_swing_probe.py and16native samples, explicitly excluding the
identified artwork/scale/streak block and fire update, with empty collision logs.
The direction and velocity helpers execute. This is sampled free-flight evidence
only; no new level completion claim. Additional16-case comparison test added.
BP and other outstanding routes still require further collision/mechanic work.

## Ground-action precision

Previous turn corrected Swing queued actions (progress). Size-toggle disassembly
0x3884b0 shows no ordinary vertical-impulse change. Grounded-ball updateJump
0x377d54..0x377d80 instead revealed a precision difference: flipGravity halves
rawvelocity, then multiplication byfloat32(0.6) writes rawdouble with no setter
rounding. Corrected ground_action accordingly. Native_ground_probe.py and8
measured cube/ball size/gravity samples retained with explicit clock/statistics/
visual exclusions. Existing67tests pass, plus new8-case ground impulse test
passes (68across these runs). This preserves the12completing original routes.
A numerical fix, not a full parity or additional level-completion claim.

## Pad/portal activation phase corrected

Previous turn fixed measured ball-flip precision (progress). Inspected early
failures13/18/19 and shared collision ordering. Updated touch_objects with an
activation-only pass: pads and portals execute before solid resolution, while
ring input stays in its existing later phase and touched-ring history remains
unchanged by the activation-only pass. Radius refreshes after mode/size changes.
This matches the native activation-before-solid ordering documented in the
read-only collision references (GJBaseGameLayer::checkCollisions, macOS0xfe188;
Windows reference0x2137f0 activation calls before0x214687solid pass).

Full55fixture audit --no-save retained all12completing levels; later mismatch
frontiers remain essentially the same (BP82.98%, Electroman6.51%, TOE2 1.05%).
Existing68tests pass. Added pad/platform overlap regression: vy16prevents false
landing/stair snap and preserves the current tick's integrated position. New
test passes, for69tests across these runs. No fixture/geometry changes.
This corrects the shared phase but does not claim full collision ordering or
additional level completion; rotated/moving/group objects and Tower remain open.

## Functional original-art garage

Previous goal turn fixed shared pad/portal activation ordering and retained all
12completing routes (progress). This turn improved native-style menu fidelity:
original garage button now occupies the home screen's left large slot; settings
uses the lower utility row alongside stats, music and info. Added primary/secondary
color palettes with original-UHD cube/ship/ball/UFO/wave previews. Preferences
merge atomically and preserve selected level, audio volume, and music path.

Renderer reads saved colors once per level load; all mode icons, ship/UFO rider,
robot/spider animated parts (darker rear parts) and wave trail use them. Cached
color previews preserve source aspect ratio. Screenshot reviewed under/tmp.
New persistence/navigation test verifies both colors and unchanged other settings.
All70tests pass, including unchanged original completing routes and native samples.
Gameplay physics was not modified by the garage work. Full goal remains active.

## Ramp-assisted jump coupling implemented

Previous goal turn added a functional high-res garage (progress). This turn
implemented missing ground-jump slope contribution. Split raw slope_velocity
from age-scaled slope_exit_velocity; ground_action adds quarter of native ramp
velocity (age-scaled for cube, raw for ball) when jumping uphill, capped at1.4
base launch. Both held jumps from the preceding slope and fresh actions on a
current ramp use it. Ball gravity flip/postscale still occurs after the bonus.

Native getModifiedSlopeYVel0x37b378 and updateJump ground-jump branch verified
via read-only hash-guarded probe.96samples across modes, sizes, gravity, ages
and raw slope speeds retained with explicit clock/statistics/visual exclusions.
Existing70tests pass, plus the new96-case test passes (71across those runs).
Sampled calculation is verified; actual slope-derived state/collision parity
remains incomplete. Full audit running to refresh the compatibility report.

## Missing brick platform collision fixed

Previous turn added native-measured ramp jump coupling (progress). This turn
found type21/id143brick platforms were rendered but entirely absent from collision
buckets. Added type21as one-way footing (landing, non-lethal pass-through sides),
including wave transparency and foreground solid styling.32such bricks in
Electroman Adventures and8inTOE2; other imported levels have none.

First change moved lv13best6.51→11.35%. Stair snap then incorrectly nudged x
when the previous footing was type21. Added snap_type and gate on the previous
object being ordinary type0; a type21TARGET still permits snap from ordinary
footing. This matches documented native checkSnapJumpToObject behavior.
Lv13standard untouched route now19.13%, all-coins route59.15%ship. Neither is a
completion. Full55fixture audit retained12passing levels and saved currentreport.
New regressions cover indexedplatforms, both original lv13routes, upward/wave
pass-through and downwardlanding, plus previous-vs-target snaptype. The first
newroute test incorrectly attributed59.15%toDP; fixed to assert each fixture's
actual frontier separately. Existing routes and native arithmetic tests pass.

## UHD font cache lifetime fixed

Previous turn added missing brick platforms and advanced lv13best to59.15%
(progress). Investigated next lv13ship deaths: DP19.13%atpit61, coins59.15%
atblade187. No hazard shrink or timing change was justified. Inspected reference
injection scheduler: processCommands feeds inputs at g_tick then increments; no
unsupported global frame-offset adjustment was applied.

Found BitmapFont.render's class-wide LRU held strong references to discarded
font instances. Beforefix one rendered font remained alive after del+gc.collect;
its UHD atlas occupies4,194,304bytes. Cache now belongs to each font instance,
matching other renderer caches. A weak-reference lifecycle regression proves
rendered text reuse while allowing the font to be collected. All75tests pass.
Additional8instance lifecycle check and moving dual UHD draw benchmark run.
Removed incorrect universal Waterflame credit from every level's retry overlay;
it now shows the actual return-to-level-menu control. Physics unchanged thisturn.
Moving dual UHD draw check (150sampled frames after30warmup, artificial player
positions/rotations): mean5.78ms,p958.46ms, under16.67ms CPUdraw budget.
Eight discarded fonts:0retained after collection. This does not establish
end-to-end60FPS/VSync or legal gameplay for the synthetic renderer positions.

## Robot jump and sustain mechanics corrected

Previous turn fixed UHD font retention (progress). Corrected Robot launch order:
half base impulse before mini scaling/setter and slope bonus, rather than
halving the final slope-assisted launch. Added robot_jumping latch; held input
only sustains an actual ground jump, not arbitrary rising velocity after a pad,
orb or mode change. Release/activation clears the latch; failed gravity-pad
facing checks leave it untouched. Native air probe24cases and launch48cases
retained, with explicit partial-method/visual exclusions. New regressions cover
all72native samples and pad takeover during a sustained jump. Full test suite
launched after the final changes; no new route-completion claim.

## Native-style flying rotation

Previous turn corrected Robot launch/sustain and matched72native samples
(progress). This turn replaced instantaneous velocity angles for Ship/UFO/Swing
with original mode-specific easing. Wave retains its native ease coefficient
but now uses actual float32 position displacement. UFO uses the opposite tilt
response and gravity-dependent clamp. Small displacement, dash and active slope
exits are respected by the helper; slope-specific rotation remains separate work.

Native_rotation_probe.py executes installed updateShipRotation and Slerp2D with
synthetic accessors and float32 external libm adapters.320samples stored; max
angular error0.0000153degrees, below.00002regression threshold. Existing78tests
pass plus new320-case test. Full original input audit running to refresh report.
This is rotation evidence; original full-engine parity remains unfinished.

## Native orb strengths completed for five common types

Previous turn added native flying rotation (progress). Replaced inline approximate
orb strengths with native mode/size table and arithmetic order: yellow Robot0.9,
green Ship0.7, red Ship1/1.4 and UFO1.02/1.36 normal/mini, Swing0.6postscale;
preserved ball/spider0.7postscale, pink mode coefficients, green-first/blue-last
gravity flip ordering. Float32 strength/size→setter rounding→rawmodepostscale.

Native_orb_probe.py executes ringJump impulse slice after activation bookkeeping
with documented statistics/visual exclusions and empty layer state.160native
samples verified via actual touch_objects calls across all modes/sizes/gravity.
Existing79tests pass plus the new160-case regression (80across those runs).
Full original-route audit running to save current results; no completing-route
claim from microprobes alone. Black/dash/spider orb branches remain separate.

Orb follow-up: extended native slice probe to black drop orbs (entry0x389d24,
stop0x389ef0 before effects).192/192samples supported and runtime test passes.
Corrected Spider drop16.5 and Swing14(previously both15); mini has no effect.
Full original audit retained12passing levels and unchanged frontiers; black
corrections affect later branches not yet reached by those routes. Full80-test
suite started after the final drop-table change. All recordings remain untouched.

## Orb boost carry corrected

Previous goal turn completed measured mode-specific orb strengths (progress).
Native orb probe now executes final boost writes while bypassing only the
identified sprite-animation block, with both incoming boost states.384cases
supported. Yellow/pink/blue/green preserve existing boost; red/black raise it.
Runtime previously cleared boost on the former four; fixed to preserve it.
Existing80tests pass with expanded384-case assertion; added downstream boosted
Ship→yelloworb→physics regression also passes (81across these runs).
Full55fixture audit retained all12completing levels and saved report; no new
route completion. Activation windows/moving objects/Tower remain unfinished.

## Pad state and downhill-release ordering

Previous goal turn fixed orb boost carry (progress). Native PlayerObject pad
wrapper confirms existing boost rule (ordinary clears; red enables). Broader
read-only pad probe runs native layer strength selection and player wrappers,
with eligibility/visual/event exclusions.192supported cases include both native
slope flags initially set. All clear them.
Runtime touch_objects now clears active slope on successful pad activation and
returns a pad-fired signal. Physics clears its captured previous-slope flag too,
so later downhill release cannot overwrite the new pad launch. Failed facing
checks leave slope flags alone. New regression covers this exact overwrite;
new192-case table test checks impulse/boost/slope writes. Full tests and original
route audit launched. Numerical evidence does not establish full pad activation
window or full-level parity. Blue/gravity pads remain outside this probe grid.

## Native Wave velocity/integration corrected

Previous goal turn fixed pad/slope ordering (progress). Native updateTimeMod
verified all SPEED_RULES constants, but exposed float32speed semantics. Added
native_horizontal_delta using storedfloat speed and nativefloat dt. Initial x
and ramp velocity derive from that same native displacement.

Wave was using physical dy/.225 as stored velocity and then integrating rounded
vy. Native stores multiplier*playerSpeed (normal5.193), while update bypassesvy
and sets vertical displacement from horizontal delta, doubledfor mini. Fixed
both, preserving correct wave-exit momentum.120native Wave samples match exact
positions and12decimal velocity. Existing83tests pass plus new120-case and
portal-momentum regressions pass (85across runs).
Full55fixture audit retained12completing levels. BP best advances82.98→83.07%
UFO with unchanged inputs; still fails, not complete. Selected17report refresh
launched after fullaudit --no-save. No inputs/geometry/hazards altered.

# Installed-engine numerical probes

`tools/native_velocity_probe.py` executes the installed macOS 2.2081 ARM64
`PlayerObject::updateJump` and explicitly whitelisted helpers in Unicorn. It
reads the application executable; it does not launch or modify the application,
its files, or saves. The exact ARM64 SHA-256 guards all addresses. Original
executable bytes are not included in the output.

`native_velocity_samples.json` contains 1,840 supported numerical samples and 32
explicitly unsupported cases. The regression suite compares the supported samples
against the recreation. These cover free-flight velocity updates across selected
modes, gravity directions, sizes, held states, boost and legacy/dual flags.
They do **not** establish contact, position, input scheduling, rendering, complete
level, or universal click-pattern parity. Unsupported samples are not passes.

Optional reproduction (Unicorn 2.1.4 is a developer dependency, not required to play):

```sh
PYTHONPATH=/path/to/optional-unicorn .venv/bin/python \
  reference/tools/native_velocity_probe.py \
  '/path/to/Geometry Dash.app/Contents/MacOS/Geometry Dash' \
  --output /tmp/native_velocity_samples.json
```

The probe accepts either the original fat Mach-O executable or its ARM64 slice.
Unicorn's JIT memory allocation traps in this environment's sandbox; successful
local reproduction used an approved unsandboxed process. No executable patching
or original-game launch is involved.

## Isolated static contact diagnostic

`tools/native_contact_probe.py` and `native_contact_samples.json` record a
60-case static-rectangle sweep: 46 supported samples, 14 explicitly unsupported.
The routine is `collidedWithObjectInternal`, with a null GameObject and synthetic
position, rectangle, scaled-rectangle and zero-rotation virtual accessors. It
bypasses the caller's candidate filtering and object state. An inverted cube can
snap from much farther inside a rectangle than the recreation currently permits
in this isolated setup. Applying that behavior directly regressed several
unchanged original routes, so the experiment was reverted. These samples are
diagnostics, not assertions that the recreation should match the isolated result
in its complete collision pass. Investigate the native caller and real object
state before changing that rule.

Reproduce with the same optional environment, replacing the script name with
`reference/tools/native_contact_probe.py` and supplying `--output /tmp/contacts.json`.

The contact probe also accepts `--object`, supplying a synthetic regular solid
GameObject with a static rectangle, matching previous/real positions, and the
regular type accessor. `native_static_object_contact_samples.json` retains all
60 comparison cases (46 supported,14 unsupported). Every supported result matches
the null-object sweep. Thus the synthetic object's omission alone does not
explain the broad inverted snap. Actual collision candidate selection, ordering
and prior state remain to be reproduced. This is still a microprobe, not full
original-game collision parity.

## Fresh UFO flaps

`tools/native_flap_probe.py` records 16 cases in `native_flap_samples.json`, with
held input and the fresh stateRingJump flag. All velocity helpers execute; the
graphical playBurstEffect helper is skipped. Both sizes and gravity directions
are included. Native normal-size fresh flap velocity after one update is6.871;
mini is6.648. Existing higher upward velocity is retained subject to flight caps.
The recreation's queued flaps match all16 cases.

Read-only native pushButton disassembly confirms that the UFO branch returns
without the zero-dt updateJump call used for grounded ball/cube input. The
recreation now queues UFO flaps until the following physics update, applying
impulse then gravity. These numerical checks do not prove full level parity.

## Position integration

`tools/native_position_probe.py` runs the installed update method's instruction
slice from0x375c6c through its position setter, after velocity calculation. It
uses synthetic position accessors and stops before rendering/effects. The16
cases in native_position_samples.json cover several world-coordinate ranges
and positive/negative vertical displacements, including cancellation near zero.
The native routine uses float32 dt and0.9 multiplication, converts each displacement
to float32, then adds that to float32 CCPoint coordinates. The recreation now
matches these16measured position results. This is an integration microprobe,
not a full native game update or level-completion claim.

## Swing fresh flips

`tools/native_swing_probe.py` and native_swing_samples.json cover16fresh flip
cases across sizes, gravity directions and incoming velocities. The probe runs
the native gravity flag change, velocity helpers and updateJump arithmetic. It
explicitly skips flipGravity's0x37b578..0x37b5fc artwork/scale/streak block and
updateSwingFire, and supplies empty collision-log containers. These exclusions
limit the evidence to flip direction and velocity in the sampled free-flight
states. They do not validate visuals, contacts, event dispatch or whole levels.
The native button handler queues Swing input; the recreation now does too.

## Grounded ball/cube impulses

`tools/native_ground_probe.py` records8normal/mini, upright/inverted ground-action
samples in native_ground_samples.json. Clock, statistics and rotation effects
are skipped; the flipGravity physics prefix executes before skipping its
visual/contact cleanup tail. These are free-standing velocity samples only.
Native ball velocity is halved, then multiplied directly by float32(0.6) without
a second velocity-setter rounding. Normal impulse3.3540001332759855 and mini
2.6832001066207884 are preserved. The recreation matches these eight samples
to12decimal places. Slope-coupled actions and full contact behavior remain open.

## Ramp-assisted ground jumps

`tools/native_slope_jump_probe.py` records96samples in
native_slope_jump_samples.json. Supplied ramp velocities0,8,16,100 are crossed
with cube/ball, both sizes and gravity directions, and ride ages.02,.06,.2.
The same ground-probe exclusions apply; native getModifiedSlopeYVel and velocity
setters execute. The recreation matches the resulting impulses to11decimal
places, including ride-age scaling for cube, unmodified ramp velocity for ball,
and the1.4launch cap. These validate impulse calculation with supplied state;
they do not prove that the collision solver derives identical ramp state.

## Robot airborne and launch states

`tools/native_robot_probe.py` records24airborne states without a ground-jump
latch in native_robot_samples.json. All native physics helpers execute. Holding
alone does not cancel gravity (normal upright vy5 becomes4.806 with either hold
state). The recreation now requires an active ground-jump sustain latch, cleared
by release, pad/orb takeover and a mode change.

`tools/native_slope_jump_probe.py --robot` records48launch samples in
native_robot_jump_samples.json. This variant stops at0x377d90 after the native
impulse write and before Robot sprite animation. Robot halves its base launch
before applying slope bonus/cap. Sample impulses: normal5.59flat,7.59at supplied
ramp velocity8; mini4.472flat and6.261capped. The recreation matches all48to
11decimal places. Supplied ramp state, not complete collision or level parity.

## Flying-mode rotation

`tools/native_rotation_probe.py` runs updateShipRotation0x382970 and original
Slerp2D0x22515c with synthetic position/rotation accessors. External atan2f,
sincosf,acosf,sinf use Python math rounded tofloat32; this adapter introduces a
numerical limit and is explicitly documented in the artifact.320cases cross
ship/UFO/wave/Swing, sizes, gravity, five vertical displacements and four old
angles including wraparound. native_rotation_samples.json retains all outputs.
The recreation differs by at most0.0000153degrees in this grid (test limit.00002).
Ship/Swing ease at.15per native-time unit; UFO at.07with its separate tilt
clamp; wave at.25normal/.4mini. Classic240Hz native dt is.25. This validates
free-flight rotation calculation, not portal/slope setup, whole collisions, or
level parity.

## Orb impulse table

`tools/native_orb_probe.py` starts ringJump at0x389d9c after activation
bookkeeping, supplies a synthetic orb type, and stops at0x38a468 after velocity
and gravity writes. Native strength arithmetic/setters/post-multipliers execute;
rotation/streak/statistics effects are skipped and manager/layer state is empty.
192samples in native_orb_samples.json cross yellow/pink/blue/green/black/red, all8
modes, both sizes and gravity directions. Runtime orb activation matches each
velocity to11decimal places and each resulting gravity direction.

Notable corrections: yellow Robot0.9strength; green Ship0.7; red Ship1.0normal/
1.4mini, UFO1.02normal/1.36mini; Swing0.6post-multiplier. Float32 strength and
size arithmetic precede velocity-setter rounding and mode postscale. Blue flips
after the impulse/postscale and halves velocity; green flips before it. These
validate sampled impulses, not activation windows or universal route parity.

Black-orb samples enter the drop branch at0x389d24 and stop at0x389ef0 after
impulse/boost writes, before effects. They bypass size and post-multipliers;
Spider uses16.5, Ship/Wave/Swing14,UFO11.2,other modes15. All32drop cases
match the runtime handler, completing192supported orb samples in the grid.

Orb-state extension: the probe now bypasses the identified Robot/Spider animation
block0x38a468..0x38a504, executes the final boost writes, and stops at0x389ef0
for every type. The grid now includes both incoming boost states (384cases).
Yellow/pink/blue/green retain that state; red/black raise it. Runtime tests
check velocity, gravity AND boost against each sample, plus a downstream Ship
step proving that yellow-orb carry is not prematurely capped at8.

## Yellow/pink/red pads

`tools/native_pad_probe.py` runs GJBaseGameLayer::bumpPlayer's strength selection
after eligibility, then original PlayerObject::bumpPlayer and propellPlayer.
Activation callbacks, Robot/Spider art, rotation/streak work and layer event
callbacks are excluded; static synthetic accessors provide the pad.192cases
cross3pad types,8modes,bothsizes,gravity andincomingboost states. Both native
slope flags begin true. native_pad_samples.json retains impulses/boost/current
and previous slope flags. Runtime matches impulses to11decimal places, boosts
exactly (red enables; ordinary clears), and clears current/previous slope state
after activation. A regression guards against downhill-release overwriting the
pad impulse. Blue/gravity and spider pads are outside this grid.

## Wave stored velocity versus integration

`tools/native_wave_probe.py` runs updateTimeMod's numerical prefix, native
updateJump, and native update's position-integration slice.120samples cross all
5speeds, sizes, held directions, gravity and3coordinate ranges. Synthetic
position accessors; contacts/input scheduling/rendering excluded.

The native speed settings match SPEED_RULES. Wave stores multiplier*float32speed
(normal5.193), but integrates vertical displacement from the horizontal delta
directly (doubled for mini). It does not integrate the rounded stored velocity
with the other modes'.9time factor. Runtime now matches all120positions exactly
and velocities to12decimal places. A portal regression checks that cube exit
receives half the stored5.193=2.5965, rather than the old derived2.885. This is
not full Wave collision/portal or level parity.

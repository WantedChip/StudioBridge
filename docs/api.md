# StudioBridge Python SDK Reference

The StudioBridge Python SDK provides a fully-typed, synchronous and asynchronous API for programmatic DAW automation, sound design, and offline project generation.

---

## 1. Quick Example

```python
from studiobridge import Studio

# Connect to the local DAW session via loopback SysEx RPC
with Studio.connect() as studio:
    # 1. Transport control
    if not studio.transport.is_playing():
        studio.transport.start()

    # 2. Mixer telemetry & adjustment
    master_vol = studio.mixer.get_volume(0)
    print(f"Master volume: {master_vol:.2f}")

    # 3. Channel rack inspection
    channels = studio.channels.get_channels()
    for ch in channels:
        print(f"[{ch.index}] {ch.name} (Pan: {ch.pan:.2f}, Vol: {ch.volume:.2f})")
```

For asynchronous automation (asyncio event loops, FastAPI/aiohttp servers), use `AsyncStudio`:

```python
import asyncio
from studiobridge import AsyncStudio


async def main() -> None:
    async with AsyncStudio.connect() as studio:
        tempo = await studio.transport.get_tempo()
        print(f"Tempo: {tempo} BPM")


asyncio.run(main())
```

---

## 2. Core Namespaces

### `studio.transport` — Transport & Playback Control

Controls playback state, song position, tempo, and loop modes:

```python
# Playback state
studio.transport.start()  # Start playback
studio.transport.stop()  # Stop playback
studio.transport.record()  # Toggle recording state
is_playing = studio.transport.is_playing()
is_recording = studio.transport.is_recording()

# Tempo (BPM)
tempo = studio.transport.get_tempo()  # Returns float (e.g. 128.0)
studio.transport.set_tempo(130.0)  # Sets tempo

# Song Position & Markers
pos = studio.transport.get_song_pos()  # Position in beats/bars
studio.transport.set_song_pos(0.0)  # Rewind to start
studio.transport.marker_jump(1)  # Jump to marker index
```

### `studio.mixer` — Mixer Strips & Master Bus

Inspects and controls mixer tracks (Master track `0`, Insert tracks `1` through `125`):

```python
# Track volumes (0.0 to 1.0 normalized)
vol = studio.mixer.get_volume(track=0)
studio.mixer.set_volume(track=1, volume=0.8)

# Stereo panning (-1.0 left to +1.0 right)
pan = studio.mixer.get_pan(track=1)
studio.mixer.set_pan(track=1, pan=0.0)

# Mute & Solo
studio.mixer.mute_track(track=2, muted=True)
studio.mixer.solo_track(track=1, solo=True)

# Peak levels & telemetry
peak_left, peak_right = studio.mixer.get_peak_levels(track=0)

# Effects slots inspection
slots = studio.mixer.get_track_slots(track=1)
for slot in slots:
    print(f"Slot {slot.index}: {slot.plugin_name} (Enabled: {slot.enabled})")
```

### `studio.channels` — Channel Rack & Generators

Manages generator instruments, samplers, and channel parameters:

```python
# Channel counts & queries
count = studio.channels.get_channel_count()
selected = studio.channels.get_selected()

# Channel properties
name = studio.channels.get_name(channel=0)
volume = studio.channels.get_volume(channel=0)
pan = studio.channels.get_pan(channel=0)
pitch = studio.channels.get_pitch(channel=0)

# Channel routing to mixer
target_track = studio.channels.get_target_fx_track(channel=0)
studio.channels.set_target_fx_track(channel=0, track=3)
```

### `studio.patterns` — Pattern Management

Inspects and selects patterns in the pattern picker:

```python
pattern_count = studio.patterns.get_pattern_count()
current_pattern = studio.patterns.get_current_pattern()
studio.patterns.select_pattern(pattern_number=2)
studio.patterns.set_pattern_name(pattern_number=2, name="Bass Drop")
```

### `studio.plugins` — Plugin Parameters

Inspects and automates loaded instrument and effect plugin parameters:

```python
# Query plugin parameters
param_count = studio.plugins.get_param_count(channel=0)
param_name = studio.plugins.get_param_name(channel=0, index=1)
value = studio.plugins.get_param_value(channel=0, index=1)

# Automate parameter
studio.plugins.set_param_value(channel=0, index=1, value=0.75)
```

### `studio.project` — Project Metadata

Queries project information without opening files:

```python
title = studio.project.get_title()
author = studio.project.get_author()
genre = studio.project.get_genre()
comments = studio.project.get_comments()
file_path = studio.project.get_file_path()
```

### `studio.notes` — Piano Roll Note Injection

Auditions notes and injects multi-bar sequences:

```python
from studiobridge.pianoroll import Note

# Audition note-on / note-off live
studio.notes.note_on(channel=0, pitch=60, velocity=100)  # Middle C
studio.notes.note_off(channel=0, pitch=60)

# Batch note injection
notes = [
    Note(pitch=60, start_step=0, length_steps=4, velocity=100),
    Note(pitch=64, start_step=4, length_steps=4, velocity=90),
    Note(pitch=67, start_step=8, length_steps=4, velocity=95),
]
studio.notes.inject_notes(channel=0, notes=notes)
```

---

## 3. Safety Modes, Checkpoints & Transactions

StudioBridge includes built-in safety controls for agent execution:

```python
from studiobridge.sdk import SafetyMode

with Studio.connect(safety_mode=SafetyMode.READ_ONLY) as studio:
    # Attempting to mutate in READ_ONLY raises ConfirmationRequired
    try:
        studio.mixer.set_volume(0, 0.5)
    except Exception as e:
        print(f"Write blocked by safety mode: {e}")

# Transactions with automatic rollback on error
with Studio.connect() as studio:
    with studio.transaction() as txn:
        studio.mixer.set_volume(1, 0.7)
        studio.mixer.set_pan(1, -0.5)
        # If an unhandled exception occurs inside this block,
        # the transaction rolls back changes using the mutation journal snapshot.
```

---

## 4. Offline Binary FLP Engine

StudioBridge includes a pure-Python parser and editor for `.flp` project files:

```python
from studiobridge.flp import Project, diff_projects, atomic_save

# 1. Load an existing FLP project
project = Project.load("my_song.flp")
print(f"Project title: {project.title}")
print(f"Channels: {len(project.channels)}")

# 2. Modify project channels
project.channels[0].name = "Lead Synth"
project.channels[0].volume = 0.85

# 3. Structural invariant verification & atomic save
project.validate_invariants()
atomic_save(project, "my_song_edited.flp")

# 4. Diff two projects
diff = diff_projects("my_song.flp", "my_song_edited.flp")
print(diff.summary())
```

---

## 5. Headless Render Supervisor

Orchestrates background audio exports without interactive GUI prompts:

```python
from studiobridge.render import RenderRunner, RenderConfig

runner = RenderRunner()
config = RenderConfig(
    project_path="my_song.flp",
    output_path="render/my_song.wav",
    format="wav",
    timeout_seconds=120,
)

job = runner.launch(config)
job.wait_until_complete()

# Validate acoustic signal properties
metrics = runner.validate_audio("render/my_song.wav")
print(
    f"Duration: {metrics.duration_seconds:.2f}s, RMS: {metrics.rms_db:.1f} dB, Peak: {metrics.peak_db:.1f} dB"
)
```

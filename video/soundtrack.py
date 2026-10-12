"""Makes the music of the video, `media/soundtrack.wav`, from nothing but numpy:
a soft pad over four chords, a plucked pattern, a bass and light drums.

It runs at 120 beats a minute, so every scene of the video starts on a beat; a bell
marks each of those starts. Change `SCENES` when the scenes change length.

    uv run python video/soundtrack.py
"""
import wave
from pathlib import Path

import numpy as np

RATE = 44100
BEAT = 0.5
# Seconds at which the scenes start, and the end of the video (`cargo run --release -- timeline`)
SCENES = [0, 5, 14, 24, 35, 46, 57, 68.5, 80.5, 92.5]
LENGTH = 98.0
# Four seconds each: bass note, then the notes of the pad (MIDI numbers)
CHORDS = [
    (41, [53, 57, 60, 64]),  # F major 7
    (45, [57, 60, 64, 67]),  # A minor 7
    (38, [50, 57, 60, 65]),  # D minor 7
    (36, [52, 55, 60, 62]),  # C with an added ninth
]
CHORD_SECONDS = 4.0
ENDING = SCENES[-1] - 0.5  # from here the first chord is held to the end

rng = np.random.default_rng(2026)
samples = int(LENGTH * RATE)
dry = np.zeros((samples, 2))
wet = np.zeros((samples, 2))  # what also goes through the reverb


def hertz(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def chord_at(second):
    return CHORDS[0] if second >= ENDING else CHORDS[int(second // CHORD_SECONDS) % len(CHORDS)]


def level(second, start, end, ramp=2.0):
    """1 between `start` and `end`, rising and falling over `ramp` seconds."""
    return float(np.clip((second - start) / ramp, 0, 1) * np.clip((end - second) / ramp, 0, 1))


def put(bus, second, sound, gain=1.0, pan=0.0):
    start = int(second * RATE)
    sound = sound[: max(0, samples - start)]
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    bus[start : start + len(sound), 0] += sound * gain * left
    bus[start : start + len(sound), 1] += sound * gain * right


def clock(seconds):
    return np.arange(int(seconds * RATE)) / RATE


def pad(note, seconds):
    t = clock(seconds + 1.6)
    tone = sum(
        np.sin(2 * np.pi * hertz(note) * 2 ** (cents / 1200) * harmonic * t + phase) * amount
        for cents, phase in ((-7, 0.0), (0, 1.3), (7, 2.1))
        for harmonic, amount in ((1, 1.0), (2, 0.3), (3, 0.1))
    )
    return tone * np.clip(t / 1.0, 0, 1) * np.clip((seconds + 1.6 - t) / 1.6, 0, 1)


def pluck(note, seconds=0.9):
    t = clock(seconds)
    f = hertz(note)
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) * np.exp(-t * 14)) * np.exp(-t * 6.5) * np.clip(t / 0.004, 0, 1)


def bass(note, seconds=1.7):
    t = clock(seconds)
    f = hertz(note)
    return (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)) * np.clip(t / 0.02, 0, 1) * np.exp(-t * 1.6)


def kick():
    t = clock(0.35)
    sweep = 45 + 70 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(sweep) / RATE) * np.exp(-t * 14)


def hat():
    t = clock(0.08)
    noise = np.diff(rng.standard_normal(len(t) + 1))  # the difference keeps only the high end
    return noise * np.exp(-t * 80)


def bell(note):
    t = clock(4.0)
    f = hertz(note)
    return (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 5)) * np.exp(-t * 1.8) * np.clip(t / 0.003, 0, 1)


# The pad, one chord after another, each fading into the next
second = 0.0
while second < LENGTH:
    seconds = LENGTH - second if second >= ENDING - CHORD_SECONDS and second + CHORD_SECONDS >= ENDING else CHORD_SECONDS
    _, notes = chord_at(second + 0.5)
    for index, note in enumerate(notes):
        sound = pad(note, seconds)
        put(dry, second, sound, 0.02, pan=(index - 1.5) * 0.4)
        put(wet, second, sound, 0.009, pan=(1.5 - index) * 0.4)
    second += seconds

# The plucked pattern on every half beat: up and down the chord, an octave above the pad
steps = [0, 1, 2, 3, 2, 1, 3, 2]
for step in range(int(LENGTH / (BEAT / 2))):
    second = step * BEAT / 2
    volume = level(second, SCENES[1], LENGTH - 3.0, 3.0)
    if volume <= 0:
        continue
    _, notes = chord_at(second)
    note = notes[steps[step % len(steps)]] + 12
    accent = 1.0 if step % 4 == 0 else 0.7
    put(wet, second, pluck(note), 0.10 * volume * accent, pan=0.5 if step % 2 else -0.5)
    # A second voice an octave higher while the maps are on
    high = level(second, SCENES[5], SCENES[8], 3.0)
    if high > 0 and step % 2 == 0:
        put(wet, second + BEAT / 4, pluck(note + 12, 0.6), 0.04 * high, pan=-0.6 if step % 4 else 0.6)

# Bass on the first beat of every bar, kick on the first and third, hats between the beats
for beat in range(int(LENGTH / BEAT)):
    second = beat * BEAT
    root, _ = chord_at(second)
    if beat % 4 == 0:
        put(dry, second, bass(root), 0.30 * level(second, SCENES[1], LENGTH - 1.0, 4.0))
    if beat % 2 == 0:
        put(dry, second, kick(), 0.42 * level(second, SCENES[2], SCENES[-1], 2.0))
    put(dry, second + BEAT / 2, hat(), 0.035 * level(second, SCENES[3], SCENES[8], 4.0), pan=0.3)

# A bell where each scene starts
for index, second in enumerate(SCENES):
    put(wet, second, bell(81 if index % 2 == 0 else 84), 0.09)
    put(wet, second + 0.02, bell(88), 0.04, pan=0.6)

# Reverb: the wet sounds played through two seconds of fading noise
t = clock(2.2)
size = samples + len(t)
room = np.zeros((samples, 2))
for channel in range(2):
    impulse = rng.standard_normal(len(t)) * np.exp(-t * 3.0) * np.clip(t / 0.01, 0, 1)
    impulse /= np.sqrt(np.sum(impulse**2))
    room[:, channel] = np.fft.irfft(np.fft.rfft(wet[:, channel], size) * np.fft.rfft(impulse, size), size)[:samples]

mix = dry + wet + 0.5 * room
mix *= np.clip((LENGTH - np.arange(samples) / RATE) / 3.0, 0, 1)[:, None]  # the last chord fades away
mix = np.tanh(mix * 1.2 / np.max(np.abs(mix))) / np.tanh(1.2) * 0.72  # a soft ceiling; about −14 LUFS

path = Path(__file__).resolve().parent / "media" / "soundtrack.wav"
with wave.open(str(path), "wb") as out:
    out.setnchannels(2)
    out.setsampwidth(2)
    out.setframerate(RATE)
    out.writeframes((mix * 32767).astype("<i2").tobytes())
print(f"{path.name}: {LENGTH:.0f} s")

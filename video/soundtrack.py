"""Makes the music of the video, `media/soundtrack.wav`, from nothing but numpy:
slow organ chords in A minor, a repeating four-note figure that grows with the video,
a clock ticking under it and a low hit where each scene starts. Focused rather than
cheerful, and without drums.

The figure and the clock move in half seconds, and every scene of the video starts on
a half second. Change `SCENES` when the scenes change length.

    uv run python video/soundtrack.py
"""
import wave
from pathlib import Path

import numpy as np

RATE = 44100
STEP = 0.5
# Seconds at which the scenes start, and the end of the video (`cargo run --release -- timeline`)
SCENES = [0, 5, 14, 24, 35, 46, 57, 68.5, 80.5, 92.5]
LENGTH = 98.0
# Eight seconds each: the pedal in the bass, the organ's notes, the four notes of the figure (MIDI numbers)
CHORDS = [
    (33, [45, 52, 57, 60], [57, 64, 69, 72]),  # A minor
    (29, [41, 48, 57, 60], [57, 65, 69, 72]),  # F
    (26, [38, 50, 57, 62], [57, 62, 65, 69]),  # D minor
    (28, [40, 47, 55, 59], [55, 59, 64, 67]),  # E minor
]
CHORD_SECONDS = 8.0
ENDING = SCENES[-1]  # from here the first chord is held to the end
# The loudest stretch: the last map and the scenarios
PEAK = (SCENES[6], SCENES[9])

rng = np.random.default_rng(2026)
samples = int(LENGTH * RATE)
dry = np.zeros((samples, 2))
wet = np.zeros((samples, 2))  # what goes through the reverb


def hertz(note):
    return 440.0 * 2 ** ((note - 69) / 12)


def chord_at(second):
    return CHORDS[0] if second >= ENDING else CHORDS[int(second // CHORD_SECONDS) % len(CHORDS)]


def level(second, start, end, rise=2.0, fall=2.0):
    """1 between `start` and `end`, rising over `rise` seconds and falling over `fall`."""
    return float(np.clip((second - start) / rise, 0, 1) * np.clip((end - second) / fall, 0, 1))


def put(bus, second, sound, gain=1.0, pan=0.0):
    start = int(second * RATE)
    sound = sound[: max(0, samples - start)]
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    bus[start : start + len(sound), 0] += sound * gain * left
    bus[start : start + len(sound), 1] += sound * gain * right


def clock(seconds):
    return np.arange(int(seconds * RATE)) / RATE


def organ(note, seconds, bright):
    """A held organ note; `bright` (0 to 1) opens the higher pipes."""
    t = clock(seconds + 3.0)
    f = hertz(note)
    pipes = ((1, 1.0), (2, 0.5), (3, 0.22 + 0.2 * bright), (4, 0.12 + 0.25 * bright), (6, 0.12 * bright), (8, 0.08 * bright))
    tone = sum(np.sin(2 * np.pi * f * harmonic * (1 + drift) * t + phase) * amount for harmonic, amount in pipes for drift, phase in ((-0.0015, 0.4), (0.0015, 2.0)))
    swell = 1 + 0.06 * np.sin(2 * np.pi * 0.23 * t + note)
    return tone * swell * np.clip(t / 2.5, 0, 1) ** 2 * np.clip((seconds + 3.0 - t) / 3.0, 0, 1)


def figure_note(note, bright):
    t = clock(1.6)
    f = hertz(note)
    tone = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.25 * bright * np.sin(6 * np.pi * f * t) * np.exp(-t * 4)
    return tone * np.clip(t / 0.03, 0, 1) * np.exp(-t * 3.2)


def tick(strong):
    t = clock(0.05)
    click = rng.standard_normal(len(t)) * np.exp(-t * 400)
    wood = np.sin(2 * np.pi * (1900 if strong else 1500) * t) * np.exp(-t * 160)
    return click * 0.5 + wood


def hit():
    t = clock(5.0)
    low = np.sin(2 * np.pi * (36 * t + 8 * (1 - np.exp(-t * 20)) / 20)) * np.exp(-t * 1.1)
    air = np.cumsum(rng.standard_normal(len(t)))  # rumble: noise with the high end taken off
    air = (air - np.linspace(air[0], air[-1], len(t))) / 300 * np.exp(-t * 2.5)
    return (low + 0.15 * air) * np.clip(t / 0.01, 0, 1)


def intensity(second):
    """0 at the quiet start, 1 in the loudest stretch."""
    return float(np.clip((second - SCENES[1]) / (PEAK[0] - SCENES[1]), 0, 1)) * level(second, 0, ENDING + 1.0, 1.0, 2.0)


# The organ, one chord after another, each swelling into the next; a pedal under it later on
second = 0.0
while second < LENGTH:
    seconds = LENGTH - second if second >= ENDING else min(CHORD_SECONDS, ENDING - second)
    pedal, notes, _ = chord_at(second)
    bright = intensity(second + seconds / 2)
    for index, note in enumerate(notes):
        sound = organ(note, seconds, bright)
        put(dry, second, sound, 0.016 + 0.014 * bright, pan=(index - 1.5) * 0.35)
        put(wet, second, sound, 0.014 + 0.010 * bright, pan=(1.5 - index) * 0.35)
    put(dry, second, organ(pedal, seconds, 0.0), 0.07 * level(second, SCENES[2], LENGTH, 16.0, 1.0))
    if second >= PEAK[0] and second < ENDING:
        for note in notes[2:]:
            put(wet, second, organ(note + 12, seconds, 1.0), 0.012)
    second += seconds

# The four-note figure, a note every half second; an octave above joins for the maps
for step in range(int(LENGTH / STEP)):
    second = step * STEP
    volume = level(second, SCENES[1], ENDING + 3.0, 14.0, 3.0)
    if volume <= 0:
        continue
    _, _, notes = chord_at(second)
    note = notes[step % 4]
    bright = intensity(second)
    accent = 1.0 if step % 4 == 0 else 0.75
    put(wet, second, figure_note(note, bright), (0.05 + 0.07 * bright) * volume * accent, pan=-0.25 if step % 2 else 0.25)
    high = level(second, SCENES[5], ENDING, 8.0, 1.0)
    if high > 0:
        put(wet, second, figure_note(note + 12, bright), 0.045 * high * accent, pan=0.45 if step % 2 else -0.45)

# The clock: a tick every half second, the one on the whole second a little stronger
for step in range(int(LENGTH / STEP)):
    second = step * STEP
    strong = step % 2 == 0
    put(dry, second, tick(strong), (0.05 if strong else 0.03) * level(second, 1.0, LENGTH - 1.0, 6.0, 4.0), pan=0.15 if strong else -0.15)

# A low hit where each scene starts
for second in SCENES[1:]:
    put(dry, second, hit(), 0.30)
    put(wet, second, hit(), 0.12)

# Reverb: the wet sounds played through four seconds of fading noise, a large room
t = clock(4.5)
size = samples + len(t)
room = np.zeros((samples, 2))
for channel in range(2):
    impulse = rng.standard_normal(len(t)) * np.exp(-t * 1.5) * np.clip(t / 0.02, 0, 1)
    impulse /= np.sqrt(np.sum(impulse**2))
    room[:, channel] = np.fft.irfft(np.fft.rfft(wet[:, channel], size) * np.fft.rfft(impulse, size), size)[:samples]

mix = dry + 0.6 * wet + 0.8 * room
mix *= np.clip((LENGTH - np.arange(samples) / RATE) / 4.0, 0, 1)[:, None]  # the last chord fades away
mix = np.tanh(mix * 1.1 / np.max(np.abs(mix))) / np.tanh(1.1) * 0.8  # a soft ceiling

path = Path(__file__).resolve().parent / "media" / "soundtrack.wav"
with wave.open(str(path), "wb") as out:
    out.setnchannels(2)
    out.setsampwidth(2)
    out.setframerate(RATE)
    out.writeframes((mix * 32767).astype("<i2").tobytes())
print(f"{path.name}: {LENGTH:.0f} s")

# Video of the Prague 2026 analyses

A 98-second, 1920×1080, 30 fps motion video made with [fframes](https://github.com/dmtrKovalenko/fframes)
from the figures of the four analyses in the app: the result, the seats, where the
Pirates' voters went, turnout, three maps of precincts, and what would have changed the
majority. It has no sound.

| File | What |
| --- | --- |
| `build_data.py` | reads the stored analyses and the precinct boundaries; writes `src/data.rs` and the maps `media/map-*.png` |
| `src/lib.rs` | the video, the title and the closing card |
| `src/charts.rs` | scenes drawn from numbers: result, seats, voter flows, turnout, scenarios |
| `src/maps.rs` | scenes with a map: the Pirates a year apart, travel time, housing |
| `src/main.rs` | the command line (`fframes::cli`) |
| `media/` | the fonts (Bebas Neue, DM Sans and IBM Plex Mono, all under the Open Font License) |

The maps and the rendered video are not in git.

## Making it again

Needs `cargo install --locked cargo-fframes`, and on a Mac `brew install nasm ninja ffmpeg x264`.
The app has to be running, because the precinct boundaries come from its API, and the
analyses have to be computed (`output/kv2026/cache/analysis_*.json`).

```sh
uv run python video/build_data.py            # --api http://localhost:8600 by default
cd video && touch src/lib.rs                 # so that changed maps are embedded again
cargo run --release -- render -o praha-2026.mp4
```

To look at a part without rendering everything: `cargo run --release -- frame 33s`
writes one frame, `strip Flows -n 8` a contact sheet of a scene, `inspect` reports text
that runs off the picture, and `preview` plays the video.

Every number on screen comes from `src/data.rs`, so the video follows the analyses when
they are recomputed. The sentences are written by hand in the scenes; read them again
when the figures change.

`Cargo.lock` is kept on purpose: fframes 1.1.0 does not compile with newer releases of
its dependencies. Nothing is stripped in the release profile, because macOS 27 refuses
to load a stripped proc-macro library.

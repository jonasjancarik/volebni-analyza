//! A motion video of the Prague 2026 analyses: the result, the seats, where the
//! Pirates' voters went, turnout, three maps of precincts and what would have
//! changed the outcome.
//!
//! Every scene is a struct that returns an SVG tree for each frame; `svgr!` is SVG
//! with `{rust expressions}` in attributes and text. The numbers come from
//! `data.rs` and the maps from `media/`, both made by `build_data.py`.
use fframes::{AudioMap, AudioTimestamp::*, AudioTrack, Color, Duration, FFramesContext, Frame, Scene, Scenes, Svgr, Video, include_media_dir};

mod charts;
mod data;
mod maps;

use data::*;

// The fonts, the maps and the music in `media/` are embedded into the binary.
include_media_dir!(pub struct VideoMedia, "media");

pub const WIDTH: usize = 1920;
pub const HEIGHT: usize = 1080;
const FPS: f32 = 30.0;

pub(crate) const PAPER: &str = "#f6f5f1";
pub(crate) const SURFACE: &str = "#fdfdfc";
pub(crate) const INK: &str = "#0b0b0b";
pub(crate) const INK_2: &str = "#52514e";
pub(crate) const INK_3: &str = "#85837c";
pub(crate) const LINE: &str = "#e3e2db";
pub(crate) const UP: &str = "#006300";
pub(crate) const DOWN: &str = "#b3261e";
pub(crate) const TITLE: &str = "Bebas Neue";
pub(crate) const TEXT: &str = "DM Sans";
pub(crate) const MONO: &str = "IBM Plex Mono";
/// Left and right edge of the content
pub(crate) const LEFT: f32 = 96.0;
pub(crate) const RIGHT: f32 = 1824.0;

pub(crate) fn clamp01(x: f32) -> f32 {
    x.clamp(0.0, 1.0)
}
/// 0 at `a`, 1 at `b`, eased at both ends.
pub(crate) fn smooth(a: f32, b: f32, x: f32) -> f32 {
    let u = clamp01((x - a) / (b - a));
    u * u * (3.0 - 2.0 * u)
}
/// Out fast, settling slowly.
pub(crate) fn settle(u: f32) -> f32 {
    1.0 - (1.0 - clamp01(u)).powi(3)
}
pub(crate) fn lerp(a: f32, b: f32, u: f32) -> f32 {
    a + (b - a) * u
}
/// 12345.6 as "12 346".
pub(crate) fn people(n: f32) -> String {
    let digits = format!("{}", n.round() as i64);
    let mut out = String::new();
    for (i, c) in digits.chars().enumerate() {
        if i > 0 && (digits.len() - i) % 3 == 0 {
            out.push(' ');
        }
        out.push(c);
    }
    out
}
/// 23.17 as "23,2".
pub(crate) fn number(value: f32, decimals: usize) -> String {
    format!("{value:.decimals$}").replace('.', ",").replace('-', "−")
}
/// 23.17 as "23,2 %".
pub(crate) fn percent(value: f32, decimals: usize) -> String {
    format!("{} %", number(value, decimals))
}
/// How visible a scene of `length` seconds is at second `t`: it fades in and out.
pub(crate) fn presence(t: f32, length: f32) -> f32 {
    smooth(0.0, 0.45, t) * (1.0 - smooth(length - 0.45, length - 0.05, t))
}

/// What a scene is about, in its top left corner: a small label, the title, a sentence under it.
pub(crate) fn header<'a>(t: f32, label: &'static str, title: &'static str, sentence: &'static str) -> Svgr<'a> {
    let rule = (56.0 * settle(t / 0.6)).max(0.5);
    fframes::svgr!(<g>
        <rect x={LEFT} y="96" width={rule} height="4" fill={INK} />
        <text x={LEFT + 76.0} y="108" font-family={MONO} font-size="24" letter-spacing="5" fill={INK_3} opacity={smooth(0.1, 0.5, t)}>{label}</text>
        <text x={LEFT} y={210.0 + 24.0 * (1.0 - settle((t - 0.1) / 0.7))} font-family={TITLE} font-size="84" letter-spacing="1" fill={INK} opacity={smooth(0.1, 0.6, t)}>{title}</text>
        <text x={LEFT} y="268" font-family={TEXT} font-size="32" fill={INK_2} opacity={smooth(0.5, 1.0, t)}>{sentence}</text>
    </g>)
}

pub struct AnalysisVideo<'a> {
    pub media: &'a VideoMedia,
    /// File in `media/` that plays under the video
    music: &'a str,
    opening: Opening,
    results: charts::Results,
    seats: charts::Seats,
    flows: charts::Flows,
    turnout: charts::Turnout,
    pirates_map: maps::PiratesMap,
    travel_time: maps::TravelTime,
    housing: maps::Housing,
    scenarios: charts::Scenarios,
    closing: Closing,
}

impl<'a> AnalysisVideo<'a> {
    pub fn new(media: &'a VideoMedia, music: &'a str) -> Self {
        Self {
            media,
            music,
            opening: Opening,
            results: charts::Results,
            seats: charts::Seats,
            flows: charts::Flows,
            turnout: charts::Turnout,
            pirates_map: maps::PiratesMap,
            travel_time: maps::TravelTime,
            housing: maps::Housing,
            scenarios: charts::Scenarios,
            closing: Closing,
        }
    }

    fn scenes(&self) -> [&dyn Scene; 10] {
        [
            &self.opening,
            &self.results,
            &self.seats,
            &self.flows,
            &self.turnout,
            &self.pirates_map,
            &self.travel_time,
            &self.housing,
            &self.scenarios,
            &self.closing,
        ]
    }
}

impl std::fmt::Debug for AnalysisVideo<'_> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AnalysisVideo").finish()
    }
}

/// Seconds of all scenes together; the line at the bottom shows how far the video is.
const TOTAL: f32 = Opening::SECONDS
    + charts::Results::SECONDS
    + charts::Seats::SECONDS
    + charts::Flows::SECONDS
    + charts::Turnout::SECONDS
    + maps::PiratesMap::SECONDS
    + maps::TravelTime::SECONDS
    + maps::Housing::SECONDS
    + charts::Scenarios::SECONDS
    + Closing::SECONDS;

impl Video for AnalysisVideo<'_> {
    const FPS: usize = 30;
    const WIDTH: usize = WIDTH;
    const HEIGHT: usize = HEIGHT;
    const BACKGROUND_COLOR: Color = Color::WHITE;

    fn duration(&self) -> Duration<'_> {
        Duration::Auto
    }

    fn audio(&self) -> AudioMap<'_> {
        // One track. The one `soundtrack.py` makes moves in half seconds, and so do the starts of the scenes.
        AudioMap::from([AudioTrack::new(self.music, Second(0.)..Eof).fade_in(0.3).fade_out(2.5)])
    }

    fn define_scenes(&self) -> Scenes<'_> {
        Scenes::from(self.scenes().to_vec())
    }

    fn render_frame<'a>(&'a self, frame: Frame, ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let done = clamp01(frame.index as f32 / (TOTAL * FPS));
        fframes::svgr!(
            <svg xmlns="http://www.w3.org/2000/svg" width={WIDTH} height={HEIGHT} viewBox="0 0 1920 1080">
                <rect width="1920" height="1080" fill={PAPER} />
                {ctx.render_scenes(&frame)}
                <rect x="0" y="1074" width="1920" height="6" fill={LINE} />
                <rect x="0" y="1074" width={(1920.0 * done).max(0.5)} height="6" fill={INK} />
            </svg>
        )
    }
}

/// The title, with the city's precincts beside it and the result as one strip.
#[derive(Debug)]
struct Opening;

impl Opening {
    const SECONDS: f32 = 5.0;
}

impl Scene for Opening {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        // The strip of the result grows from the left, list by list
        let grown = settle((t - 1.0) / 1.6) * 100.0;
        let mut from = 0.0;
        let mut strip = Vec::new();
        for (_, color, _, share, ..) in LISTS {
            let width = (grown - from).clamp(0.0, share) * 8.4;
            strip.push(fframes::svgr!(<rect x={LEFT + from * 8.4} y="800" width={width.max(0.01)} height="20" fill={color} />));
            from += share;
        }
        let rest = (grown - from).clamp(0.0, 100.0 - from) * 8.4;
        let zoom = 1.0 + 0.04 * t / Self::SECONDS;
        let (width, height) = (800.0 * zoom, 800.0 * zoom * MAP_SIZE.1 / MAP_SIZE.0);
        let map = |file: &str, opacity: f32| {
            ctx.get_image(file)
                .map(|image| fframes::svgr!(<image href={image.href()} x={1440.0 - width / 2.0} y={540.0 - height / 2.0} width={width} height={height} opacity={opacity} />))
                .into_iter()
                .collect::<Vec<_>>()
        };
        fframes::svgr!(<g opacity={presence(t, Self::SECONDS)}>
            {map("map-base.png", smooth(0.2, 1.0, t))}
            {map("map-kinds.png", 0.9 * smooth(1.6, 3.0, t))}
            <rect x={LEFT} y="300" width={(56.0 * settle(t / 0.6)).max(0.5)} height="4" fill={INK} />
            <text x={LEFT + 76.0} y="312" font-family={MONO} font-size="24" letter-spacing="5" fill={INK_3} opacity={smooth(0.2, 0.7, t)}>"KOMUNÁLNÍ VOLBY 2026 · PRAHA"</text>
            <text x={LEFT} y={480.0 + 30.0 * (1.0 - settle((t - 0.2) / 0.8))} font-family={TITLE} font-size="132" letter-spacing="2" fill={INK} opacity={smooth(0.2, 0.8, t)}>"PIRÁTI A PRAHA SOBĚ"</text>
            <text x={LEFT} y={610.0 + 30.0 * (1.0 - settle((t - 0.4) / 0.8))} font-family={TITLE} font-size="132" letter-spacing="2" fill={INK} opacity={smooth(0.4, 1.0, t)}>"V PRAŽSKÝCH VOLBÁCH"</text>
            <text x={LEFT} y="700" font-family={TEXT} font-size="38" fill={INK_2} opacity={smooth(0.9, 1.5, t)}>{format!("Co ukazují výsledky z {} okrsků", people(PRECINCTS))}</text>
            {strip}
            <rect x={LEFT + from * 8.4} y="800" width={rest.max(0.01)} height="20" fill="#cfcec6" />
        </g>)
    }
}

/// Where the whole analyses are, and what the numbers are made from.
#[derive(Debug)]
struct Closing;

impl Closing {
    const SECONDS: f32 = 5.5;
}

impl Scene for Closing {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, _ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let rule = (360.0 * settle((t - 0.3) / 0.9)).max(0.5);
        fframes::svgr!(<g opacity={smooth(0.0, 0.45, t)}>
            <text x="960" y="400" text-anchor="middle" font-family={MONO} font-size="26" letter-spacing="6" fill={INK_3} opacity={smooth(0.1, 0.6, t)}>"CELÉ ANALÝZY S MAPAMI A TABULKAMI"</text>
            <text x="960" y={540.0 + 30.0 * (1.0 - settle((t - 0.2) / 0.8))} text-anchor="middle" font-family={TITLE} font-size="128" letter-spacing="3" fill={INK} opacity={smooth(0.2, 0.8, t)}>"VOLBY.JONASJANCARIK.CZ/ANALYZY"</text>
            <rect x={960.0 - rule / 2.0} y="588" width={rule} height="5" fill={INK} />
            <text x="960" y="690" text-anchor="middle" font-family={TEXT} font-size="32" fill={INK_2} opacity={smooth(1.0, 1.6, t)}>"Přesuny voličů jsou odhad z výsledků v okrscích, ne měření."</text>
            <text x="960" y="800" text-anchor="middle" font-family={MONO} font-size="22" letter-spacing="4" fill={INK_3} opacity={smooth(1.4, 2.0, t)}>"DATA: VOLBY.CZ (ČSÚ) · JÍZDNÍ ŘÁDY PID · REGISTR BUDOV RÚIAN"</text>
        </g>)
    }
}

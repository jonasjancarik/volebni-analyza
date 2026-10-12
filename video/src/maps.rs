//! The scenes with a map of Prague's precincts: the Pirates a year apart, support
//! by travel time to the centre, and the kinds of buildings people live in.
use crate::data::*;
use crate::{INK, INK_2, INK_3, LEFT, LINE, MONO, TEXT, TITLE, clamp01, header, lerp, number, percent, presence, settle, smooth};
use fframes::{Duration, FFramesContext, Frame, Scene, Svgr};

const MAP_TOP: f32 = 330.0;

/// One of the map pictures, `width` wide from the left edge of the content.
fn map<'a>(ctx: &FFramesContext<'a, '_>, file: &str, width: f32, opacity: f32) -> Vec<Svgr<'a>> {
    if opacity < 0.003 {
        return Vec::new();
    }
    let height = width * MAP_SIZE.1 / MAP_SIZE.0;
    ctx.get_image(file)
        .map(|image| fframes::svgr!(<image href={image.href()} x={LEFT} y={MAP_TOP} width={width} height={height} opacity={opacity} />))
        .into_iter()
        .collect()
}

/// The Pirates' share in the same precincts in the parliamentary election and a year
/// later, then where Praha Sobě is strong now.
#[derive(Debug)]
pub struct PiratesMap;

impl PiratesMap {
    pub const SECONDS: f32 = 11.0;
}

impl Scene for PiratesMap {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let later = smooth(3.2, 4.6, t);
        let other = smooth(7.0, 8.2, t);
        let width = 880.0;
        let x = 1060.0;
        let legend = |colors: [&'static str; 7], low: &'static str, high: &'static str, opacity: f32| {
            let steps: Vec<_> = colors
                .iter()
                .enumerate()
                .map(|(i, color)| fframes::svgr!(<rect x={x + i as f32 * 56.0} y="640" width="56.5" height="18" fill={*color} />))
                .collect();
            fframes::svgr!(<g opacity={opacity}>
                {steps}
                <text x={x} y="690" font-family={TEXT} font-size="24" fill={INK_3}>{low}</text>
                <text x={x + 392.0} y="690" text-anchor="end" font-family={TEXT} font-size="24" fill={INK_3}>{high}</text>
            </g>)
        };
        fframes::svgr!(<g opacity={presence(t, Self::SECONDS)}>
            {header(t, "05 · MAPA", "STEJNÉ OKRSKY O ROK POZDĚJI", "Podíl hlasů v pražských okrscích: Sněmovna 2025 a zastupitelstvo 2026")}
            {map(ctx, "map-pirati-2025.png", width, smooth(0.3, 1.1, t))}
            {map(ctx, "map-pirati-2026.png", width, later)}
            {map(ctx, "map-praha-sobe.png", width, other)}

            <text x={x} y="400" font-family={MONO} font-size="24" letter-spacing="4" fill={INK_3} opacity={smooth(0.5, 1.0, t) * (1.0 - smooth(3.2, 3.7, t))}>"PIRÁTI · SNĚMOVNA 2025"</text>
            <text x={x} y="400" font-family={MONO} font-size="24" letter-spacing="4" fill={INK_3} opacity={smooth(4.1, 4.6, t) * (1.0 - smooth(7.0, 7.4, t))}>"PIRÁTI · ZASTUPITELSTVO 2026"</text>
            <text x={x} y="400" font-family={MONO} font-size="24" letter-spacing="4" fill={INK_3} opacity={smooth(7.8, 8.2, t)}>"PRAHA SOBĚ · ZASTUPITELSTVO 2026"</text>
            <text x={x - 6.0} y="590" font-family={TITLE} font-size="220" fill={PINK[5]} opacity={smooth(0.5, 1.0, t) * (1.0 - smooth(7.0, 7.5, t))}>{percent(lerp(CITY_PIRATI.0, CITY_PIRATI.1, later), 1)}</text>
            <text x={x - 6.0} y="590" font-family={TITLE} font-size="220" fill={GREEN[5]} opacity={smooth(7.7, 8.2, t)}>{percent(CITY_PRAHA_SOBE, 1)}</text>
            {legend(PINK, "0 %", "30 % a víc", smooth(0.7, 1.2, t) * (1.0 - other))}
            {legend(GREEN, "5 %", "35 % a víc", other)}

            <g font-family={TEXT} font-size="34" fill={INK} opacity={smooth(4.8, 5.4, t) * (1.0 - smooth(7.0, 7.4, t))}>
                <text x={x} y="800">"Proti sněmovním volbám ztratili Piráti"</text>
                <text x={x} y="846">"nejvíc blízko centra."</text>
            </g>
            <g font-family={TEXT} font-size="34" fill={INK} opacity={smooth(8.3, 8.9, t)}>
                <text x={x} y="800">"Právě tam je teď nejsilnější"</text>
                <text x={x} y="846">"Praha Sobě."</text>
            </g>
        </g>)
    }
}

/// The city filling in from the centre by minutes of travel, with each list's share
/// drawn band by band beside it.
#[derive(Debug)]
pub struct TravelTime;

impl TravelTime {
    pub const SECONDS: f32 = 11.5;
}

impl Scene for TravelTime {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let bands = BANDS.len();
        // How many bands are on the map and in the chart by now
        let reached = ((t - 0.9) / 0.55).clamp(0.0, bands as f32 - 1.0);
        let mut pictures = map(ctx, "map-base.png", 820.0, 0.55 * smooth(0.2, 0.9, t));
        for index in 0..bands {
            pictures.extend(map(ctx, &format!("map-band-{index}.png"), 820.0, smooth(0.0, 0.5, t - 0.9 - index as f32 * 0.55 + 0.25)));
        }

        let (x0, x1, y0, top) = (1060.0, 1590.0, 900.0, 30.0);
        let step = (x1 - x0) / (bands as f32 - 1.0);
        let y = |value: f32| y0 - value / top * 500.0;
        let grid: Vec<_> = [0.0, 10.0, 20.0, 30.0]
            .into_iter()
            .map(|value| {
                fframes::svgr!(<g>
                    <rect x={x0 - 14.0} y={y(value)} width={x1 - x0 + 28.0} height="2" fill={LINE} />
                    <text x={x0 - 28.0} y={y(value) + 8.0} text-anchor="end" font-family={TEXT} font-size="24" fill={INK_3}>{percent(value, 0)}</text>
                </g>)
            })
            .collect();
        let axis: Vec<_> = BANDS
            .iter()
            .enumerate()
            .map(|(index, name)| {
                let x = x0 + index as f32 * step;
                let lit = smooth(0.0, 0.4, reached - index as f32 + 0.6);
                fframes::svgr!(<g opacity={0.35 + 0.65 * lit}>
                    <rect x={x - 30.0} y={y0 + 20.0} width="60" height="10" fill={BAND_COLORS[index]} />
                    <text x={x} y={y0 + 62.0} text-anchor="middle" font-family={TEXT} font-size="21" fill={INK_2}>{*name}</text>
                </g>)
            })
            .collect();

        // Names at the ends of the lines, pushed apart where two lines end close together
        let mut ends: Vec<(usize, f32)> = BAND_SHARES.iter().enumerate().map(|(i, list)| (i, y(list.2[bands - 1]) + 10.0)).collect();
        ends.sort_by(|a, b| a.1.total_cmp(&b.1));
        for i in 1..ends.len() {
            ends[i].1 = ends[i].1.max(ends[i - 1].1 + 36.0);
        }
        let named = smooth(0.0, 0.5, t - 0.9 - (bands as f32 - 1.0) * 0.55);
        let lines: Vec<_> = BAND_SHARES
            .iter()
            .enumerate()
            .map(|(i, (name, color, shares))| {
                let whole = reached.floor() as usize;
                let mut points: Vec<String> = (0..=whole).map(|k| format!("{},{}", x0 + k as f32 * step, y(shares[k]))).collect();
                if whole + 1 < bands {
                    let part = reached - whole as f32;
                    points.push(format!("{},{}", x0 + (whole as f32 + part) * step, y(lerp(shares[whole], shares[whole + 1], part))));
                }
                // Praha Sobě, the Pirates and ANO change with distance; STAN and Spolu stay level
                let leading = i < 3;
                let label_y = ends.iter().find(|end| end.0 == i).map(|end| end.1).unwrap_or(0.0);
                fframes::svgr!(<g opacity={smooth(0.6, 1.0, t)}>
                    <polyline points={points.join(" ")} fill="none" stroke={*color} stroke-width={if leading { 8 } else { 4 }} stroke-linejoin="round" stroke-linecap="round" opacity={if leading { 1.0 } else { 0.6 }} />
                    <text x={x1 + 26.0} y={label_y} font-family={TEXT} font-size="28" fill={INK} opacity={named}>{format!("{name} {}", percent(shares[bands - 1], 0))}</text>
                    <rect x={x1 + 12.0} y={label_y - 20.0} width="6" height="24" fill={*color} opacity={named} />
                </g>)
            })
            .collect();

        fframes::svgr!(<g opacity={presence(t, Self::SECONDS)}>
            {header(t, "06 · VZDÁLENOST", "ČÍM DÁL OD CENTRA, TÍM SLABŠÍ PRAHA SOBĚ", "ANO se vzdáleností roste. STAN a Spolu mají všude zhruba stejně.")}
            {pictures}
            <g opacity={smooth(0.4, 0.9, t)}>
                {grid}
                {axis}
                <text x={(x0 + x1) / 2.0} y={y0 + 108.0} text-anchor="middle" font-family={MONO} font-size="20" letter-spacing="4" fill={INK_3}>"MINUT MHD NA MŮSTEK V RANNÍ ŠPIČCE"</text>
            </g>
            {lines}
        </g>)
    }
}

/// Precincts by the buildings most of their flats are in, and how each kind votes.
#[derive(Debug)]
pub struct Housing;

impl Housing {
    pub const SECONDS: f32 = 12.0;
}

impl Scene for Housing {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let columns = [("Praha", "Sobě", LISTS[2].1), ("Piráti", "", LISTS[4].1), ("ANO", "", LISTS[3].1), ("STAN", "a Spolu", INK_2), ("Účast", "", INK_3)];
        let column_x = |j: usize| 1330.0 + j as f32 * 112.0;
        let row_y = |i: usize| 490.0 + i as f32 * 122.0;
        // What the scene points at, one after another: (seconds from, to, cells as row and column, sentence)
        let notes: [(f32, f32, &[(usize, usize)], String); 3] = [
            (4.2, 6.6, &[(0, 0), (1, 0)], format!("Praha Sobě má ve starších domech {} a na sídlištích {}.", percent(KINDS[0].3[0], 0), percent(KINDS[1].3[0], 0))),
            (6.6, 9.0, &[(1, 2)], "Na sídlištích žije třetina voličů a nejsilnější je tam ANO.".to_string()),
            (9.0, 99.0, &[(3, 3), (3, 4)], "V rodinných domech je vysoká účast a vede STAN se Spolu.".to_string()),
        ];
        let during = |from: f32, to: f32| smooth(from, from + 0.4, t) * (1.0 - smooth(to - 0.4, to, t));

        let heads: Vec<_> = columns
            .iter()
            .enumerate()
            .map(|(j, (first, second, _))| {
                fframes::svgr!(<g font-family={TEXT} font-size="23" fill={INK_2} text-anchor="middle">
                    <text x={column_x(j)} y={if second.is_empty() { 408.0 } else { 392.0 }}>{*first}</text>
                    <text x={column_x(j)} y="420">{*second}</text>
                </g>)
            })
            .collect();
        let marks: Vec<_> = notes
            .iter()
            .flat_map(|(from, to, cells, _)| {
                let opacity = during(*from, *to);
                cells.iter().map(move |&(i, j)| {
                    fframes::svgr!(<rect x={column_x(j) - 52.0} y={row_y(i) - 52.0} width="104" height="96" rx="10" fill={columns[j].2} opacity={0.2 * opacity} />)
                })
            })
            .collect();
        let sentences: Vec<_> = notes
            .iter()
            .map(|(from, to, _, sentence)| fframes::svgr!(<text x="950" y="1000" font-family={TEXT} font-size="31" fill={INK} opacity={during(*from, *to)}>{sentence.clone()}</text>))
            .collect();
        let rows: Vec<_> = KINDS
            .iter()
            .enumerate()
            .map(|(i, (name, color, voters, values))| {
                let start = 1.2 + i as f32 * 0.35;
                let grown = settle((t - start) / 1.0);
                let cells: Vec<_> = values
                    .iter()
                    .enumerate()
                    .map(|(j, value)| {
                        fframes::svgr!(<g>
                            <text x={column_x(j)} y={row_y(i) + 6.0} text-anchor="middle" font-family={TITLE} font-size="54" fill={INK}>{number(value * grown, 0)}</text>
                            <rect x={column_x(j) - 42.0} y={row_y(i) + 22.0} width="84" height="8" rx="4" fill={LINE} />
                            <rect x={column_x(j) - 42.0} y={row_y(i) + 22.0} width={(84.0 * clamp01(value / 60.0) * grown).max(0.5)} height="8" rx="4" fill={columns[j].2} />
                        </g>)
                    })
                    .collect();
                fframes::svgr!(<g opacity={smooth(start, start + 0.5, t)}>
                    <rect x="950" y={row_y(i) - 62.0} width="874" height="2" fill={LINE} />
                    <rect x="950" y={row_y(i) - 30.0} width="22" height="22" rx="4" fill={*color} />
                    <text x="988" y={row_y(i) - 10.0} font-family={TEXT} font-size="29" fill={INK}>{*name}</text>
                    <text x="988" y={row_y(i) + 26.0} font-family={TEXT} font-size="23" fill={INK_3}>{format!("{} voličů", percent(*voters, 0))}</text>
                    {cells}
                </g>)
            })
            .collect();

        fframes::svgr!(<g opacity={presence(t, Self::SECONDS)}>
            {header(t, "07 · ZÁSTAVBA", "VÍC NEŽ VZDÁLENOST ROZHODUJE, V ČEM LIDÉ BYDLÍ", "Okrsky podle domů, ve kterých je aspoň polovina jejich bytů. Čísla jsou v procentech.")}
            {map(ctx, "map-base.png", 780.0, smooth(0.2, 0.8, t))}
            {map(ctx, "map-kinds.png", 780.0, smooth(0.6, 1.6, t))}
            <g opacity={smooth(1.4, 2.0, t)}>
                <rect x={LEFT} y="958" width="22" height="22" rx="4" fill={MIXED.1} />
                <text x={LEFT + 38.0} y="978" font-family={TEXT} font-size="24" fill={INK_3}>{MIXED.0}</text>
            </g>
            <g opacity={smooth(1.0, 1.5, t)}>{heads}</g>
            {marks}
            {rows}
            {sentences}
        </g>)
    }
}

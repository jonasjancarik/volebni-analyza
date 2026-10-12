//! The scenes drawn from numbers alone: the result, the seats, where the Pirates'
//! voters of 2022 went, turnout, and what would have changed the majority.
use crate::data::*;
use crate::{DOWN, INK, INK_2, INK_3, LEFT, LINE, MONO, RIGHT, SURFACE, TEXT, TITLE, UP, header, lerp, number, people, percent, presence, settle, smooth};
use fframes::{Duration, FFramesContext, Frame, Scene, Svgr};
use std::sync::LazyLock;

/// Shares of the five lists in 2022 turning into those of 2026.
#[derive(Debug)]
pub struct Results;

impl Results {
    pub const SECONDS: f32 = 9.0;
}

impl Scene for Results {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, _ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let now = smooth(3.0, 4.6, t);
        let (x0, per_point) = (400.0, 38.0);
        let rows: Vec<_> = LISTS
            .iter()
            .enumerate()
            .map(|(i, (name, color, before, after, ..))| {
                let y = 420.0 + i as f32 * 112.0;
                let grown = settle((t - 0.5 - i as f32 * 0.1) / 1.0);
                let value = lerp(*before, *after, now);
                let change = after - before;
                fframes::svgr!(<g opacity={smooth(0.3 + i as f32 * 0.1, 0.8 + i as f32 * 0.1, t)}>
                    <text x={LEFT} y={y + 15.0} font-family={TEXT} font-size="42" fill={INK}>{*name}</text>
                    <rect x={x0} y={y - 32.0} width={(before * per_point * grown).max(0.5)} height="64" rx="6" fill={*color} opacity={0.2 * now} />
                    <rect x={x0} y={y - 32.0} width={(value * per_point * grown).max(0.5)} height="64" rx="6" fill={*color} />
                    <text x={x0 + value * per_point * grown + 22.0} y={y + 25.0} font-family={TITLE} font-size="70" fill={INK}>{percent(value * grown, 1)}</text>
                    <text x={RIGHT} y={y + 20.0} text-anchor="end" font-family={TITLE} font-size="54" fill={if change > 0.0 { UP } else { DOWN }} opacity={smooth(4.8 + i as f32 * 0.12, 5.3 + i as f32 * 0.12, t)}>
                        {format!("{}{} p. b.", if change > 0.0 { "+" } else { "" }, number(change, 1))}
                    </text>
                </g>)
            })
            .collect();
        fframes::svgr!(<g opacity={presence(t, Self::SECONDS)}>
            {header(t, "01 · VÝSLEDEK", "STAN TŘIKRÁT SILNĚJŠÍ, PIRÁTI POLOVIČNÍ", "Podíl hlasů v komunálních volbách 2022 a 2026")}
            <text x={RIGHT} y="230" text-anchor="end" font-family={TITLE} font-size="170" fill={INK_3} opacity={smooth(0.4, 0.9, t) * (1.0 - now) * 0.55}>"2022"</text>
            <text x={RIGHT} y="230" text-anchor="end" font-family={TITLE} font-size="170" fill={INK} opacity={now}>"2026"</text>
            {rows}
        </g>)
    }
}

/// The seats of the council in the order the scene shows them: the Pirates, Praha Sobě,
/// STAN, Spolu, ANO (indexes into LISTS).
const BENCHES: [usize; 5] = [4, 2, 0, 1, 3];
const CHAMBER: (f32, f32) = (680.0, 930.0);

/// Where each seat is (x, y) and whose it is, from the left of the half circle to the right.
static CHAMBER_SEATS: LazyLock<Vec<(f32, f32, usize)>> = LazyLock::new(|| {
    let rows = [(250.0, 8), (320.0, 11), (390.0, 13), (460.0, 15), (530.0, 18)];
    let mut places: Vec<(f32, f32)> = rows
        .iter()
        .flat_map(|&(radius, count)| (0..count).map(move |k| (std::f32::consts::PI * (1.0 - k as f32 / (count - 1) as f32), radius)))
        .collect();
    places.sort_by(|a, b| b.0.total_cmp(&a.0).then(a.1.total_cmp(&b.1)));
    let owners = BENCHES.iter().flat_map(|&list| std::iter::repeat_n(list, LISTS[list].5));
    places.into_iter().zip(owners).map(|((angle, radius), list)| (CHAMBER.0 + radius * angle.cos(), CHAMBER.1 - radius * angle.sin(), list)).collect()
});

/// The 65 seats, the majority of STAN and Spolu in them, and how the blocks changed.
#[derive(Debug)]
pub struct Seats;

impl Seats {
    pub const SECONDS: f32 = 10.0;
}

impl Scene for Seats {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, _ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let focus = smooth(3.0, 3.7, t);
        let dots: Vec<_> = CHAMBER_SEATS
            .iter()
            .enumerate()
            .map(|(k, &(x, y, list))| {
                let grown = settle((t - 0.5 - k as f32 * 0.028) / 0.45);
                let majority = list < 2;
                fframes::svgr!(<circle cx={x} cy={y} r={(27.0 * grown).max(0.01)} fill={LISTS[list].1} opacity={if majority { 1.0 } else { 1.0 - 0.72 * focus }} />)
            })
            .collect();
        let together = LISTS[0].5 + LISTS[1].5;
        // Who sits where, under the half circle
        let legend: Vec<_> = BENCHES
            .iter()
            .enumerate()
            .map(|(k, &list)| {
                let x = 130.0 + k as f32 * 232.0;
                fframes::svgr!(<g opacity={smooth(1.6 + k as f32 * 0.12, 2.1 + k as f32 * 0.12, t)}>
                    <circle cx={x} cy="1012" r="10" fill={LISTS[list].1} />
                    <text x={x + 20.0} y="1021" font-family={TEXT} font-size="25" fill={INK_2}>{format!("{} {}", LISTS[list].0, LISTS[list].5)}</text>
                </g>)
            })
            .collect();
        let blocks = [
            ("STAN a Spolu", LISTS[0].4 + LISTS[1].4, together),
            ("Piráti a Praha Sobě", LISTS[4].4 + LISTS[2].4, LISTS[4].5 + LISTS[2].5),
            ("ANO", LISTS[3].4, LISTS[3].5),
            ("SPD", SPD_SEATS_BEFORE, 0),
        ];
        let changes: Vec<_> = blocks
            .iter()
            .enumerate()
            .map(|(i, (name, before, after))| {
                let start = 5.0 + i as f32 * 0.7;
                let y = 410.0 + i as f32 * 142.0;
                let counted = lerp(*before as f32, *after as f32, smooth(start + 0.4, start + 1.2, t)).round();
                fframes::svgr!(<g opacity={smooth(start, start + 0.5, t)}>
                    <rect x="1330" y={y - 44.0} width="494" height="2" fill={LINE} />
                    <text x="1330" y={y} font-family={TEXT} font-size="30" fill={INK_2}>{*name}</text>
                    <text x="1330" y={y + 76.0} font-family={TITLE} font-size="84" fill={INK_3}>{before.to_string()}</text>
                    <rect x="1440" y={y + 44.0} width="56" height="4" fill={INK_3} />
                    <path d={format!("M 1486 {} L 1502 {} L 1486 {} Z", y + 34.0, y + 46.0, y + 58.0)} fill={INK_3} />
                    <text x="1530" y={y + 76.0} font-family={TITLE} font-size="84" fill={INK}>{(counted as usize).to_string()}</text>
                    <text x="1640" y={y + 76.0} font-family={TEXT} font-size="26" fill={INK_3}>"mandátů"</text>
                </g>)
            })
            .collect();
        fframes::svgr!(<g opacity={presence(t, Self::SECONDS)}>
            {header(t, "02 · MANDÁTY", "STAN A SPOLU MAJÍ O MANDÁT VÍC, NEŽ POTŘEBUJÍ", "Zastupitelstvo hlavního města má 65 členů. K většině jich stačí 33.")}
            {dots}
            <g opacity={focus}>
                <text x={CHAMBER.0} y={CHAMBER.1 - 40.0} text-anchor="middle" font-family={TITLE} font-size="210" fill={INK}>{together.to_string()}</text>
                <text x={CHAMBER.0} y={CHAMBER.1 - 2.0} text-anchor="middle" font-family={MONO} font-size="22" letter-spacing="4" fill={INK_2}>"STAN A SPOLU"</text>
            </g>
            {legend}
            <text x="1330" y="340" font-family={MONO} font-size="22" letter-spacing="4" fill={INK_3} opacity={smooth(4.8, 5.3, t)}>"2022 A 2026"</text>
            {changes}
        </g>)
    }
}

/// The Pirates' voters of 2022 as one block, flowing to where they voted in 2026.
#[derive(Debug)]
pub struct Flows;

impl Flows {
    pub const SECONDS: f32 = 11.0;
}

impl Scene for Flows {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, _ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let voters = LISTS[4].6;
        let (source_x, target_x, top, per_point, gap): (f32, f32, f32, f32, f32) = (430.0, 1150.0, 345.0, 4.7, 24.0);
        // STAN is the flow that decided the majority
        let stan = 2;
        let focus = smooth(6.4, 7.0, t);
        let source_height = PIRATI_2022.iter().map(|flow| flow.2).sum::<f32>() * per_point;
        let targets_height = source_height + gap * (PIRATI_2022.len() - 1) as f32;
        let mut from = top + (targets_height - source_height) / 2.0;
        let mut to = top;
        let mut ribbons = Vec::new();
        for (i, (name, color, share)) in PIRATI_2022.iter().enumerate() {
            let thick = share * per_point;
            let (y0, y1) = (from + thick / 2.0, to + thick / 2.0);
            let middle = (source_x + 28.0 + target_x) / 2.0;
            // The ribbon is one thick line, drawn along its length
            let length = 1.15 * ((target_x - source_x - 28.0).powi(2) + (y1 - y0).powi(2)).sqrt() + 40.0;
            let start = 1.4 + i as f32 * 0.55;
            let drawn = smooth(start, start + 1.1, t);
            let dimmed = if i == stan { 1.0 } else { 1.0 - 0.6 * focus };
            let big = *share > 10.0;
            let label_y = y1 + if big { 0.0 } else { 9.0 };
            let label = if big {
                fframes::svgr!(<g>
                    <text x={target_x + 52.0} y={label_y + 26.0} font-family={TITLE} font-size="84" fill={INK}>{percent(share * settle((t - start - 0.6) / 0.8), 0)}</text>
                    <text x={target_x + 232.0} y={label_y - 4.0} font-family={TEXT} font-size="36" fill={INK}>{*name}</text>
                    <text x={target_x + 232.0} y={label_y + 32.0} font-family={TEXT} font-size="26" fill={INK_3}>{format!("asi {} tisíc lidí", number(voters * share / 100000.0, 0))}</text>
                </g>)
            } else {
                fframes::svgr!(<text x={target_x + 52.0} y={label_y} font-family={TEXT} font-size="28" fill={INK_2}>{format!("{} · {}", percent(*share, 0), name)}</text>)
            };
            ribbons.push(fframes::svgr!(<g opacity={dimmed}>
                <path d={format!("M {} {y0} C {middle} {y0}, {middle} {y1}, {target_x} {y1}", source_x + 28.0)} fill="none" stroke={*color} stroke-width={thick} opacity="0.5"
                    stroke-dasharray={format!("{length} {length}")} stroke-dashoffset={length * (1.0 - drawn)} />
                <rect x={target_x} y={to} width="28" height={thick} fill={*color} opacity={smooth(start + 0.7, start + 1.1, t)} />
                <g opacity={smooth(start + 0.6, start + 1.1, t)}>{label}</g>
            </g>));
            from += thick;
            to += thick + gap;
        }
        let source_top = top + (targets_height - source_height) / 2.0;
        let stan_people = voters * PIRATI_2022[stan].2 / 100.0;
        fframes::svgr!(<g opacity={presence(t, Self::SECONDS)}>
            {header(t, "03 · PŘESUNY VOLIČŮ", "KAM ODEŠLI VOLIČI PIRÁTŮ Z ROKU 2022", "Třetina zůstala, třetina přešla k Praze Sobě a třetina ke STAN.")}
            <g opacity={smooth(0.5, 1.0, t)}>
                <rect x={source_x} y={source_top} width="28" height={(source_height * settle((t - 0.5) / 0.9)).max(0.5)} fill={LISTS[4].1} />
                <text x={source_x - 28.0} y={source_top + source_height / 2.0 - 30.0} text-anchor="end" font-family={TEXT} font-size="30" fill={INK_2}>"Voliči Pirátů 2022"</text>
                <text x={source_x - 28.0} y={source_top + source_height / 2.0 + 60.0} text-anchor="end" font-family={TITLE} font-size="100" fill={INK}>{people(voters * settle((t - 0.5) / 1.0))}</text>
            </g>
            {ribbons}
            <g font-family={TEXT} font-size="31" fill={INK} opacity={smooth(6.6, 7.2, t)}>
                <text x={LEFT} y="978">"Přechod k Praze Sobě společný výsledek nezměnil."</text>
                <text x={LEFT} y="1022">{format!("Rozhodl odchod ke STAN: asi {} % všech, kdo letos volili.", number(stan_people / BALLOTS * 100.0, 0))}</text>
            </g>
            <text x={RIGHT} y="1040" text-anchor="end" font-family={MONO} font-size="19" letter-spacing="3" fill={INK_3} opacity={smooth(2.0, 2.6, t)}>{format!("ODHAD Z {} SROVNATELNÝCH OKRSKŮ", people(FLOW_PRECINCTS))}</text>
        </g>)
    }
}

/// The Pirates' voters of the parliamentary election, a dot for every thousand, and how
/// many of them did not come a year later.
#[derive(Debug)]
pub struct Turnout;

impl Turnout {
    pub const SECONDS: f32 = 11.0;
}

impl Scene for Turnout {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, _ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let pink = LISTS[4].1;
        let dots = (PIRATI_PARLIAMENT_VOTES / 1000.0).round() as usize;
        let home = (dots as f32 * PIRATI_HOME.0 / 100.0).round() as usize;
        let needed = (NEW_PIRATI_NEEDED / 1000.0).round() as usize;
        let (columns, pitch) = (18, 55.0);
        let grid: Vec<_> = (0..dots)
            .map(|k| {
                let (x, y) = (LEFT + 24.0 + (k % columns) as f32 * pitch, 400.0 + (k / columns) as f32 * pitch);
                let grown = settle((t - 0.5 - k as f32 * 0.012) / 0.4);
                // The last dots are the voters who stayed home; the first of those are the ones that would be enough
                let away = k + home >= dots;
                let k_away = (k + home).saturating_sub(dots) as f32;
                let greyed = if away { smooth(3.4 + k_away * 0.015, 3.8 + k_away * 0.015, t) } else { 0.0 };
                let back = if away && (k + home - dots) < needed { smooth(6.6 + k_away * 0.04, 7.0 + k_away * 0.04, t) } else { 0.0 };
                fframes::svgr!(<g>
                    <circle cx={x} cy={y} r={(22.0 * grown).max(0.01)} fill={pink} />
                    <circle cx={x} cy={y} r={(22.0 * grown).max(0.01)} fill="#d8d7d0" opacity={greyed} />
                    <circle cx={x} cy={y} r="19.5" fill={pink} fill-opacity="0.35" stroke={PINK[5]} stroke-width="5" opacity={back} />
                </g>)
            })
            .collect();
        let now = LISTS[4].7;
        fframes::svgr!(<g opacity={presence(t, Self::SECONDS)}>
            {header(t, "04 · ÚČAST", "NEJVĚTŠÍ REZERVA JE V ÚČASTI", "Voliči Pirátů v Praze: loni do Sněmovny a letos do zastupitelstva")}
            {grid}
            <text x={LEFT} y="755" font-family={MONO} font-size="19" letter-spacing="3" fill={INK_3} opacity={smooth(1.4, 1.9, t)}>"JEDNA TEČKA JE TISÍC VOLIČŮ"</text>

            <g opacity={smooth(0.6, 1.1, t)}>
                <text x="1180" y="520" font-family={TITLE} font-size="170" fill={INK}>{format!("{} tisíc", number(PIRATI_PARLIAMENT_VOTES / 1000.0 * settle((t - 0.6) / 1.4), 0))}</text>
                <text x="1184" y="568" font-family={TEXT} font-size="30" fill={INK_2}>"hlasů do Sněmovny 2025"</text>
            </g>
            <g opacity={smooth(2.0, 2.5, t)}>
                <text x="1180" y="730" font-family={TITLE} font-size="170" fill={PINK[5]}>{format!("{} tisíc", number(now / 1000.0 * settle((t - 2.0) / 1.2), 0))}</text>
                <text x="1184" y="778" font-family={TEXT} font-size="30" fill={INK_2}>"voličů do zastupitelstva 2026"</text>
            </g>

            <g opacity={smooth(3.6, 4.2, t)}>
                <circle cx={LEFT + 24.0} cy="848" r="16" fill="#d8d7d0" />
                <text x={LEFT + 60.0} y="859" font-family={TEXT} font-size="33" fill={INK}>{format!("Podle odhadu jich {} až {} letos k volbám nepřišlo.", number(PIRATI_HOME.1, 0), percent(PIRATI_HOME.2, 0))}</text>
            </g>
            <g opacity={smooth(6.8, 7.4, t)}>
                <circle cx={LEFT + 24.0} cy="922" r="14" fill={pink} fill-opacity="0.35" stroke={PINK[5]} stroke-width="4" />
                <text x={LEFT + 60.0} y="933" font-family={TEXT} font-size="33" fill={INK}>{format!("K jinému výsledku by stačilo asi {} tisíc z nich.", number(NEW_PIRATI_NEEDED / 1000.0, 0))}</text>
            </g>
        </g>)
    }
}

/// What would have left STAN and Spolu with how many seats.
#[derive(Debug)]
pub struct Scenarios;

impl Scenarios {
    pub const SECONDS: f32 = 12.0;
}

impl Scene for Scenarios {
    fn duration(&self) -> Duration<'_> {
        Duration::Seconds(Self::SECONDS)
    }

    fn render_frame<'a>(&'a self, frame: Frame, _ctx: &FFramesContext<'a, '_>) -> Svgr<'a> {
        let t = frame.seconds();
        let lost = MAJORITY - 1;
        let options = [
            ("Skutečný výsledek".to_string(), LISTS[0].5 + LISTS[1].5),
            ("Společná kandidátka Pirátů a Prahy Sobě".to_string(), JOINT_SEATS.0),
            (format!("Společná kandidátka a k ní všech {} voličů kandidátky SEN", people(SEN_VOTERS)), JOINT_SEATS.1),
            (format!("{} voličů STAN volí Prahu Sobě", people(STAN_TO_PRAHA_SOBE_NEEDED)), lost),
            (format!("{} voličů STAN volí Piráty", people(STAN_TO_PIRATI_NEEDED)), lost),
            (format!("{} nových voličů Pirátů", people(NEW_PIRATI_NEEDED)), lost),
        ];
        let rows: Vec<_> = options
            .into_iter()
            .enumerate()
            .map(|(i, (what, seats))| {
                let start = 1.0 + i as f32 * 0.9;
                let y = 412.0 + i as f32 * 92.0;
                let holds = seats >= MAJORITY;
                let tone = if i == 0 { INK } else if holds { INK_3 } else { UP };
                let slide = (1.0 - settle((t - start) / 0.7)) * -40.0;
                fframes::svgr!(<g opacity={smooth(start, start + 0.45, t)} transform={format!("translate({slide} 0)")}>
                    <rect x={LEFT} y={y - 39.0} width={RIGHT - LEFT} height="78" rx="12" fill={SURFACE} stroke={LINE} stroke-width="2" />
                    <rect x={LEFT} y={y - 39.0} width="10" height="78" rx="5" fill={tone} />
                    <text x={LEFT + 44.0} y={y + 13.0} font-family={TEXT} font-size="36" fill={INK}>{what}</text>
                    <text x="1392" y={y + 27.0} font-family={TITLE} font-size="78" fill={tone}>{seats.to_string()}</text>
                    <text x="1480" y={y + 12.0} font-family={TEXT} font-size="29" fill={tone}>{if i == 0 { "těsná většina" } else if holds { "většina zůstává" } else { "většina končí" }}</text>
                </g>)
            })
            .collect();
        let kept = STAN_TO_PIRATI_NEEDED / (LISTS[4].6 * PIRATI_2022[2].2 / 100.0);
        fframes::svgr!(<g opacity={presence(t, Self::SECONDS)}>
            {header(t, "08 · CO BY ZMĚNILO VÝSLEDEK", "PRVNÍ MANDÁT BYL BLÍZKO. ROZHODOVAL AŽ DRUHÝ.", "STAN a Spolu mají 34 mandátů a k většině jim stačí 33.")}
            <text x="1392" y="352" font-family={MONO} font-size="19" letter-spacing="3" fill={INK_3} opacity={smooth(1.0, 1.5, t)}>"MANDÁTY STAN A SPOLU"</text>
            {rows}
            <text x={LEFT} y="990" font-family={TEXT} font-size="36" fill={INK} opacity={smooth(7.6, 8.3, t)}>
                {if kept < 0.5 { "Stačilo udržet necelou polovinu voličů, kteří od Pirátů odešli ke STAN." } else { "O většině rozhodl hlavně odchod voličů od Pirátů ke STAN." }}
            </text>
        </g>)
    }
}

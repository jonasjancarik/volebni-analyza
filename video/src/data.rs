//! Figures of the Prague 2026 analyses. Written by `build_data.py`; do not edit by hand.

pub const BALLOTS: f32 = 422092.0;
pub const PRECINCTS: f32 = 1120.0;
pub const MAJORITY: usize = 33;
/// Name, colour, share in 2022 and 2026, seats in 2022 and 2026, voters in 2022 and 2026
pub const LISTS: [(&str, &str, f32, f32, usize, usize, f32, f32); 5] = [("STAN", "#2a78d6", 7.769, 23.169, 5, 17, 31067.0, 97794.0), ("Spolu", "#eb6834", 24.72, 22.053, 19, 17, 98857.0, 93085.0), ("Praha Sobě", "#1baf7a", 14.728, 17.908, 11, 13, 58899.0, 75587.0), ("ANO", "#eda100", 19.339, 14.357, 14, 11, 77338.0, 60599.0), ("Piráti", "#e87ba4", 17.73, 9.376, 13, 7, 70902.0, 39573.0)];
pub const SPD_SEATS_BEFORE: usize = 3;
/// Where the Pirates' voters of 2022 went: name, colour, percent of them
pub const PIRATI_2022: [(&str, &str, f32); 5] = [("Piráti", "#e87ba4", 32.5), ("Praha Sobě", "#1baf7a", 29.47), ("STAN", "#2a78d6", 30.11), ("Spolu", "#eb6834", 4.59), ("Jinam nebo nepřišli", "#a3a199", 3.33)];
pub const FLOW_PRECINCTS: f32 = 1087.0;
pub const PIRATI_PARLIAMENT_VOTES: f32 = 106657.0;
/// Percent of the Pirates' parliamentary voters who did not vote: estimate, low, high
pub const PIRATI_HOME: (f32, f32, f32) = (64.34, 50.19, 68.61);
pub const NEW_PIRATI_NEEDED: f32 = 17956.0;
pub const STAN_TO_PRAHA_SOBE_NEEDED: f32 = 6557.0;
pub const STAN_TO_PIRATI_NEEDED: f32 = 9716.0;
/// Seats of STAN and Spolu had the two lists run together: without and with the votes of SEN
pub const JOINT_SEATS: (usize, usize) = (33, 33);
pub const SEN_VOTERS: f32 = 12260.0;
/// The Pirates' share in the parliamentary election and now, in the precincts on the map
pub const CITY_PIRATI: (f32, f32) = (16.857, 9.362);
pub const CITY_PRAHA_SOBE: f32 = 17.869;
/// Minutes to the centre by public transport
pub const BANDS: [&str; 8] = ["do 10", "10–15", "15–20", "20–25", "25–30", "30–35", "35–40", "40+"];
pub const BAND_SHARES: [(&str, &str, [f32; 8]); 5] = [("Praha Sobě", "#1baf7a", [23.37, 23.083, 22.736, 19.796, 16.055, 14.396, 14.371, 13.063]), ("Piráti", "#e87ba4", [9.955, 11.408, 10.342, 9.811, 8.714, 8.995, 8.542, 7.608]), ("ANO", "#eda100", [9.239, 9.683, 11.193, 13.064, 15.611, 18.444, 17.229, 15.134]), ("STAN", "#2a78d6", [22.003, 22.931, 23.017, 22.845, 22.591, 22.648, 23.921, 25.989]), ("Spolu", "#eb6834", [22.724, 21.542, 20.707, 21.133, 22.523, 21.29, 22.874, 26.895])];
pub const BAND_COLORS: [&str; 8] = ["#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#93bef2", "#b5d3f6", "#d0e3f9"];
/// Name, colour, percent of voters living there; shares of Praha Sobě, the Pirates, ANO, STAN with Spolu, and turnout
pub const KINDS: [(&str, &str, f32, [f32; 5]); 4] = [("Starší bytové domy", "#a4573c", 31.807, [23.136, 10.666, 10.657, 43.7, 44.209]), ("Panelové domy", "#62788f", 33.433, [14.284, 8.952, 19.533, 41.66, 43.411]), ("Novější bytové domy", "#b377a6", 12.467, [16.842, 9.374, 11.702, 49.505, 45.904]), ("Rodinné domy", "#7d9a35", 12.252, [15.269, 7.782, 13.903, 51.611, 56.946])];
pub const MIXED: (&str, &str) = ("Smíšená zástavba", "#b9b6ab");
pub const MAP_SIZE: (f32, f32) = (1500.0, 1141.0);
pub const PINK: [&str; 7] = ["#f6e9ee", "#f2cbdb", "#eaa3c0", "#e0749f", "#c94f84", "#a2356a", "#6b1d45"];
pub const GREEN: [&str; 7] = ["#e9f3ee", "#c5e6d6", "#93d3b6", "#55bb91", "#1f9c6f", "#0f7653", "#084c36"];

# Volební analýza

Results of Czech municipal and parliamentary elections by council and precinct:
a web app with maps, estimates of how voters moved between two elections, the
votes of single candidates, and written analyses of the 2026 municipal
election. It runs at <https://volby.jonasjancarik.cz>.

The app has two parts. A JSON API (`src/web_api.py`, FastAPI) reads the result
files that the download scripts write to `output/`, and a React frontend in
`web/` shows them. You search for a council and pick the list you follow; the
page of the council then has these views:

- **Přehled**: turnout, seats and the result of every list, with the change
  since the previous election
- **Mapa okrsků**: precincts coloured by turnout or by a list's result, or
  votes drawn as dots
- **Přesuny voličů**: estimated voter flows from the previous election,
  non-voters included, and how the estimate is made
- **Okrsky**: the table of precincts
- **Kandidáti**: votes of every candidate
- **Data ke stažení**: the tables behind the page

A city-wide election (such as the Prague city council) can be narrowed to one
city district. For the parliamentary election the place of a council is taken
by one of the 14 electoral regions.

Party shares are votes divided by all valid votes. ČSÚ recalculates its own
percentage in municipal elections for lists with fewer candidates than seats;
the app shows that one too where it differs, because it decides about the
five-percent threshold. Precincts that ČSÚ corrected and re-sent are counted
once (the latest record wins).

## Getting started

Python dependencies are managed with [uv](https://docs.astral.sh/uv/), the
frontend with npm.

```bash
uv sync
npm --prefix web install
```

### Election results

Results are not in Git. `run_all_municipalities.py` downloads them from ČSÚ
(volby.cz) and writes one folder per election to `input/` and `output/`:

```bash
uv run python run_all_municipalities.py --list-elections

uv run python run_all_municipalities.py --election kv2026
uv run python run_all_municipalities.py --election kv2022   # needed for the comparison with 2022
uv run python run_all_municipalities.py --election ps2025

# Work with files downloaded earlier
uv run python run_all_municipalities.py --election kv2026 --no-download
```

The elections are set up in `src/election_config.py`: the municipal elections
of 2026, 2022, 2018 and 2014 and the parliamentary election of 2025. The app
offers those whose results it finds in `output/`. Notes on the files of the
parliamentary election are in [docs/ps2025-data.md](docs/ps2025-data.md).

For 2026 the precinct batches are static files under
`volby.cz/appdata/kv2026/20261009/odata/okrsky/` (the older `vysledky_okrsky`
endpoint is gone); see `districts_batch_url_template` in
`src/election_config.py`. Maps use the 2025 precinct boundaries. ČSÚ lists the
2026 boundaries in its [GIS catalogue](https://geodata.csu.gov.cz/as/dp-gis/),
but the download links did not work on 11 October 2026. Once they do, point
`boundaries_file` of `kv2026` at the new file.

The maps need the outlines of precincts, which the scripts do not download.
Put the files of ČSÚ in `input/raw/` as `electoral_districts_boundaries.geojson`
(2022) and `electoral_districts_boundaries_2025.geojson` (2025). The `ps2025`
collection converts the 2025 file to WGS84 and the `kv2026` collection then
makes `electoral_districts_boundaries_2025_municipal.geojson` from it, so run
`ps2025` first.

### Running the app

```bash
# API on port 8600
uv run uvicorn --app-dir src web_api:app --host 0.0.0.0 --port 8600

# Frontend with hot reload on port 5180 (proxies /api to the API)
npm --prefix web run dev
```

For a single process, build the frontend once with `npm --prefix web run build`;
the API then serves it from `web/dist` on port 8600.

The map uses the free OpenFreeMap base map and needs no API key.

### Running in Docker

`docker compose up -d --build` serves the app on `127.0.0.1:3023` (change
the port with `VOLBY_APP_PORT`). The image holds only the code. Election
results and precinct boundaries are not in Git, so copy `output/` and the files
the app reads from `input/` (`input/raw/*.geojson`, `input/raw/*.gpkg`,
`input/raw/address_points.npy`, `input/raw/transit_minutes.npy`,
`input/raw/buildings_554782.npy` and `input/ps2025/processed/`) next to
`docker-compose.yml` before starting it.

## Voter flows

Voter-flow estimates take a few seconds each, so the API computes all of them
in the background when it starts (`src/web_prepare.py`, about half a minute
the first time) and keeps them in `output/<election>/cache/`, or in
`VOLBY_CACHE_DIR` when that is set. A stored estimate is used only while the
results of both elections and the model (`FLOW_MODEL_VERSION`) are the ones it
was computed from. Set `VOLBY_PRECOMPUTE=0` to compute them only when a page
asks for them. The figures of the analyses below are prepared and stored the
same way.

The voter-flow tab has a second view, "Jak odhad vzniká" (`?pohled=metoda`),
that explains the method on the precincts of the council being viewed: what a
single precinct leaves open, how precincts differ, the search for the
transition table played back step by step, and the repeated fits behind the
ranges. It repeats the estimate in the browser (`web/src/method/model.ts`)
from the model inputs served by `/api/elections/<election>/councils/<code>/comparison/inputs`,
so a change to the estimate in `src/election_comparison.py` has to be mirrored there.

### How the estimate is made

`src/election_comparison.py` matches precincts of the two elections by number
(dropping those whose electorate changed by more than 35 %), converts votes to
voters (a list's share of the precinct's votes times the returned envelopes),
merges lists under 3 % into one group and adds non-voters. It then fits one
transition matrix: an ecological regression like the Goodman model in
`src/ei_models.py`, but for all groups at once and with the shares constrained
to be non-negative and to add up to 100 %.

Two refinements make the estimate more honest:

- **Types of precincts.** Voters of one list need not behave alike across a
  city. Precincts are clustered by how they voted in the previous election and
  a separate matrix is fitted for each cluster. The number of clusters (1 to 6)
  is the one that best predicts the current result in precincts left out of the
  fit; small municipalities stay with one.
- **Intervals.** The fit is repeated on 100 resamples of the precincts and the
  app shows the 90 % range next to every estimate. The range tells how much a
  number depends on which precincts are in the data. It does not cover the
  error of the model's assumptions.

Treat the result as a model estimate. It ignores people who moved, died or came
of age, and it underestimates movement between voters and non-voters: precinct
results pin down the net change in turnout, not the gross exchange. Flows are
shown only for councils with at least 50 matched precincts, and with a warning
below 100. The thresholds come from running the simple Bayesian model below on the
13 largest Prague districts: from about 100 precincts the two methods agreed within
3-5 points on average, under about 60 they could differ by tens of points.

`research/bayesian_flows_check.py` fits a Bayesian hierarchical model
(multinomial-Dirichlet, every precinct with its own rates) to the same data as
a one-off cross-check. It needs PyMC and takes much longer, so it is not part of the app:

```bash
PYTENSOR_FLAGS='cxx=' uv run --with pymc --with nutpie python research/bayesian_flows_check.py --code 554782
```

(`PYTENSOR_FLAGS='cxx='` avoids a C compiler failure seen on macOS 27.)

That hierarchical model did not converge in our runs (Prague: 137 min, R-hat 1.85;
Prague 5: 86 min, R-hat 1.20). For district councils use `--model simple`: one set of
rates for the council plus estimated noise. It converges in under a minute:

```bash
PYTENSOR_FLAGS='cxx=' uv run --with pymc --with nutpie python research/bayesian_flows_check.py --code 500143 --model simple --draws 2000 --tune 2000
```

`research/bayesian_flows_batch.py` runs the simple model for every council with
50+ matched precincts (27 in 2026) and writes
`output/kv2026/reports/bayesian_simple_summary.csv` with its agreement with the
app's estimate. All 27 converged; the mean difference grows from 1.7 points for
Prague (1 087 precincts) to 5-7 points for councils with 50-60 precincts.

`python3 research/bayesian_progress.py` shows how far running fits are.

## Analyses

The "Analýzy" section (`/analyzy`) holds written analyses: an article about
one result, with its tables and charts drawn from the same data as the rest
of the app. The first one looks at the Pirates and Praha Sobě in the 2026
Prague election: seats and what would have changed them, voter flows since
2022, precincts and city districts, and an estimate of how the Pirates'
voters of the 2025 parliamentary election voted a year later. The second one
asks where the voters of Spolu and STAN are least firmly theirs: how many of
Spolu's parliamentary voters it keeps in the municipal election, by precinct
and city district, where STAN's new voters came from, and the smallest shift
that would end the two lists' majority. The third one weighs what would have
changed the result: how many seats the voters of SEN would bring on another
list depending on how many of them follow, what more voters or voters coming
back from STAN would take, and the combinations of these. The fourth one looks at
geography: support by travel time to the centre by public transport and by
what people live in (older apartment buildings, panel housing estates, newer
apartment buildings, family houses), with a map of the precincts the reader
can recolour, radar charts and a chart of all precincts. It needs the two
files described under "Travel times and buildings" below.

The fifth one is about a single city district, Praha 5. It has no voter-flow
estimate, because 81 precincts give only a rough one. Instead it looks at the
seats of the district's two blocs and how close the last seat was, compares
how the same voters filled in their two ballots (for the council of the
district and for the council of the city), and goes through the precincts: a
map the reader can recolour, the Pirates' losses by how strong they were
before, neighbourhoods, kinds of housing, a table of all precincts, and whether
turnout goes with the result (precincts by how much it rose and how high it is).
Kinds of housing need the buildings file; without it the article leaves that
part out.

The sixth one does the same for Praha 1, which has 27 seats and only 21
precincts. Its council is split among seven lists, so in place of two blocs it
shows how many votes each list was short of one more seat (one list missed the
five-percent threshold, and a seat, by about 13 voters) and lists every
precinct in a table instead of grouping them.

The seventh one is about the whole country: errors in the records of precinct
commissions that show in the official results (a candidate with no votes among
neighbours with dozens, or with ten times theirs), where putting them right
would change the seats or the people who hold them, and where a few votes
decide. Its figures come from `src/web_anomalies.py`, which turns the tables of
`src/precinct_anomalies.py` (see "Looking for counting errors" below) into what
the article shows; the notes on single cities in `Records2026.tsx` were written
after reading their records one by one. It needs the official results with
the votes of every candidate, which it downloads to
`input/<election>/official/` when first computed (about a minute).

The figures of both districts come from `src/web_districts.py`: `_District`
holds what any district's analysis shows, and each district adds its lists,
its groups of lists and its neighbourhoods. Neighbourhoods are lists of
precinct numbers (`PRAGUE_5_PARTS`, `PRAGUE_1_PARTS`) that
`research/praha5_neighbourhoods.py` helps to rebuild from the address
register. On the page, `districtBlocks.tsx` and `DistrictMap.tsx` hold what
the two articles share.

An analysis has two halves that are kept apart on purpose:

- `src/web_analyses.py` computes every number (`ANALYSES` maps the address of
  an analysis to the function that builds its figures; those of city districts
  are in `src/web_districts.py`) and serves them at
  `/api/analyses/<slug>`. Bump `ANALYSIS_VERSION` when the figures change, so
  that stored ones are recomputed.
- `web/src/analyses/` holds the text and the page: `index.tsx` lists the
  analyses, one file per analysis (`Prague2026.tsx`) writes the article around
  the figures, and `blocks.tsx` has the tables and charts they share.
  `PrecinctMap.tsx` is a map of a council's precincts for an article: it is
  given the layers to offer, each a number on a colour scale or a named kind.

The estimate between a parliamentary and a municipal election is rougher than
the one between two municipal elections: turnout differs a lot, the lists are
not the same, and the result moves with the number of precinct types more than
with the choice of precincts. Its ranges therefore also cover every number of
precinct types the data allow (`flows_across_settings`).

## Looking for counting errors

`src/precinct_anomalies.py` goes through the precinct results of a
municipal election for signs of counting errors, for every list in every
council. It reads the official results with the votes of every candidate in
every precinct, which the precinct batches above do not hold; ČSÚ publishes
them as two archives (about 23 MB) that the script downloads to
`input/<election>/official/` on its first run. The whole country takes about a
minute.

```bash
uv run python src/precinct_anomalies.py                    # every council
uv run python src/precinct_anomalies.py --city 554782      # Prague and its districts
uv run python src/precinct_anomalies.py --council 500143   # Praha 5, with the findings printed
```

It writes these tables to `output/<election>/anomalies/` (a run for one
council or one city writes to a folder of its own there):

- `prehled.csv`: every council, first those where putting the clear errors
  right would change the seats or the people who hold them, then by how large
  the largest finding is against the closest seat.
- `mandaty.csv`: how many votes each list was from one more seat, from one
  fewer and from the five-percent threshold, next to the votes missing at its
  candidates and those added by a slip of the pen, and the seats it would have
  with both put right.
- `poradi.csv`: for every list with a seat, how few votes at one candidate
  would seat somebody else, and whether the clear errors put right would.
- `kandidati.csv`: single candidates with a zero or a fraction of the votes of
  their neighbours on the list in one precinct, or a multiple of them. These
  are visible in the data as they are. Two kinds can be mistaken for real
  voting and are counted on stricter terms. A list with votes at only a few of
  its candidates may be a record left incomplete, or a few voters naming the
  same people; it counts when the votes match the whole-list ballots the list
  would be expected to have in a precinct of that size, when seven voters or
  more would have had to name the same candidates, or when the commission left
  other lists incomplete beyond doubt. A count several times the neighbours'
  may be a candidate people there know; it counts as a slip of the pen
  (`zjevny_preklep`, with the reason in `duvod_preklepu`) when it reads as a
  digit typed twice or one too many, equals the candidate's number on the
  ballot, or would need more than 15 % of the precinct's voters to name the
  candidate.
- `okrsky.csv`: precincts with unusually many or few votes counted per
  returned envelope.
- `listky.csv`: in cities with districts, lists with far more or fewer votes
  on one ballot than the other ballot of the same precinct suggests.

What the script can be trusted with differs by part:

- The seats and the order of candidates are arithmetic. They equal the
  official ones in every council of the 2026 election except 17 villages where
  a lot decided between equal votes; `prehled.csv` says so for each council.
  Two details are not in the wording of the law and were found by comparing
  with the official results: the average a candidate has to beat by a tenth is
  cut to a whole number, and a withdrawn candidate does not count for the
  five-percent threshold of a list shorter than the council.
- Errors at candidates are looked for only where voters mark whole lists, so
  that a list's candidates have nearly the same votes in a precinct, and where
  there are at least ten precincts to learn a candidate's usual place from
  (about a hundred cities and city districts in 2026). In villages and small
  towns people vote for names, and a zero is a result. `prehled.csv` gives the
  measure (`rovnomernost_hlasu_kandidatu`) and whether candidates were checked.
- A council with more than one electoral district (Lišov in 2026) is left out.

Only `kandidati.csv` is evidence. `okrsky.csv` and `listky.csv` are hints: a
precinct may differ for a reason of the place (a candidate who lives there, a
new housing estate), and only a recount of the ballots can tell.

## MCP server for AI assistants

The API also offers the same data as tools for AI assistants over the Model
Context Protocol (`src/web_mcp.py`): the list of elections, search for a
council, its results, results by precinct, voter flows and candidates. The
tools only read, and their answers leave out what only the charts and maps
need.

A running app serves them at `/mcp` (streamable HTTP, no sign-in), so an
assistant connects to the address of the app:

```bash
claude mcp add --transport http volby http://localhost:8600/mcp
```

Without a running app, a client can start the server itself over stdio:

```bash
claude mcp add volby -- uv run --project /path/to/volebni-analyza python /path/to/volebni-analyza/src/web_mcp.py
```

Set `VOLBY_PUBLIC_URL` to the public address of the app to have the answers
link to the matching page.

## Address points for the dot map

The map of precincts can show votes as dots, one for a given number of votes.
The dots are drawn next to addresses of the precinct, so that forests, parks
and fields stay empty. The addresses come from the monthly export of the
address register (RÚIAN, about 60 MB to download):

```bash
uv run python src/address_points.py
```

This writes `input/raw/address_points.npy`. Without the file the map still
works and spreads the dots at random inside each precinct.

## Travel times and buildings

One analysis places every precinct by how long it takes to the centre of
Prague and by the buildings its people live in. Both come from open data that
two scripts download and reduce to small files:

```bash
# Timetable of Prague Integrated Transport (GTFS, about 50 MB), under a minute
uv run python src/transit_times.py

# Buildings of Prague from the address register (RÚIAN, about 48 MB), a few minutes
uv run python src/buildings.py --municipality 554782
```

`transit_times.py` writes `input/raw/transit_minutes.npy`: for every stop, the
minutes to Můstek on a working morning. It scans the timetable backwards from
the arrival time, so the number is how long before a deadline one has to be at
the stop, averaged over deadlines between 7:30 and 9:00; waiting and changes
are in it. `buildings.py` writes `input/raw/buildings_554782.npy`: position,
flats, floors, use, construction and year of every building.

`src/places.py` puts the two together with the outlines of the precincts. A
precinct's travel time is that of its middle flat: on foot to the stop that
gets to the centre soonest, then by public transport. Its kind of housing is
the kind of building that holds at least half of its flats, otherwise it is
mixed. Apartment buildings built of panels are housing estates; the others
are split at 1990. Without the two files the analysis says what is missing.

## Video

`video/` holds a short motion video made from the figures of the analyses; see
[video/README.md](video/README.md) for how to render it.

## Ecological inference (Praha 5 split-ticket)

Estimate where OBEC Pirate support likely goes in MCMO using Goodman ecological
regression with Duncan-Davis bounds.

```bash
uv run python src/ecological_inference.py --election kv2022 --share-mode votes
```

Outputs:
- `output/kv2022/reports/ei_prague5_pirates_mcmo_votes.csv`
- `output/kv2022/detailed/ei_prague5_inputs_votes.csv`
- `output/kv2022/reports/ei_prague5_pirates_mcmo_votes_by_family.csv`
- `output/kv2022/reports/ei_prague5_pirates_mcmo_votes_summary.json`

Notes:
- If Pirates are part of a coalition list, pass `--obec-list-number` or tweak
  `--pirate-alias`. Use `--mcmo-list-number` if MČ list differs.
- Use `--share-mode ballots` to normalize by seat counts (defaults: OBEC 65,
  MCMO 41).

### All parties (OBEC → MČ)

```bash
uv run python src/ecological_inference_all_parties.py --election kv2022 --share-mode ballots
```

Outputs:
- `output/kv2022/reports/ei_prague5_all_parties_ballots.csv`
- `output/kv2022/reports/ei_prague5_all_parties_ballots_summary.csv`
- `output/kv2022/reports/ei_prague5_all_parties_ballots_by_family.csv`

## Where things are

```
src/
  web_api.py                 the API and, once built, the frontend
  web_store.py               reads the result files and shapes them for the pages
  web_analyses.py            figures of the written analyses
  web_districts.py           figures of the analyses of single city districts
  web_anomalies.py           figures of the analysis of precinct records
  web_mcp.py                 the same data as tools for AI assistants
  web_prepare.py             computes voter flows and analyses ahead of time
  election_comparison.py     the voter-flow estimate
  election_config.py         the elections and where their files are
  precinct_anomalies.py      looks for counting errors
  places.py, transit_times.py, buildings.py, address_points.py
                             travel times, buildings and addresses of precincts
  municipality_registry.py, all_municipalities_scraper.py,
  parliamentary_scraper.py, parliamentary_parsers.py
                             download and read the results of ČSÚ
  ecological_inference*.py, ei_models.py
                             split-ticket estimates for Praha 5 in 2022
web/                         the React frontend
run_all_municipalities.py    downloads the results of one election
research/                    one-off checks and notes that the app does not use
video/                       a short video made from the figures of the analyses
tests/
```

## Tests

```bash
uv run --with pytest pytest tests/
```

## License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE](LICENSE) file for details. If you run a modified version as a public web service, you must offer its users the source code of your changes.

The election results come from the Czech Statistical Office (volby.cz), addresses and buildings from the RÚIAN register (ČÚZK), and map tiles from OpenFreeMap with data © OpenStreetMap contributors. Those data keep their own terms.

#!/usr/bin/env python3
"""
MCP server over the data of the web app, so that an AI assistant can look up
election results, precincts and voter flows the same way the pages do.

The API serves it at /mcp (see web_api.py). For a local client that starts the
server itself, run it over stdio:
    uv run python src/web_mcp.py
"""

import functools
import json
import os
import unicodedata
from pathlib import Path
from typing import Annotated, Literal, Optional

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import Field

import web_store as store

MAX_ROWS = 200

server = MCPServer(
    "volebni-analyza",
    title="Volební analýza",
    instructions=(
        "Výsledky českých komunálních a sněmovních voleb po zastupitelstvech a okrscích, "
        "včetně odhadu přesunů voličů mezi dvěma volbami. Začni nástrojem seznam_voleb, "
        "kód zastupitelstva najdi přes hledej_zastupitelstvo. U sněmovních voleb se místo "
        "zastupitelstev pracuje s volebními kraji. Všechny podíly jsou v procentech."
    ),
)

Election = Annotated[str, Field(description="Identifikátor voleb ze seznam_voleb, např. kv2026")]
Code = Annotated[
    str, Field(description="Kód zastupitelstva nebo volebního kraje z hledej_zastupitelstvo")
]
Area = Annotated[
    Optional[str],
    Field(description="Kód městské části nebo obce (pole areas ve vysledky_zastupitelstva)"),
]


def tool(function):
    """Registers a read-only tool that answers with compact JSON. The store
    reads large files and can spend seconds on an estimate, so it runs outside
    the event loop."""

    @functools.wraps(function)
    async def run(*args, **kwargs):
        try:
            result = await anyio.to_thread.run_sync(functools.partial(function, *args, **kwargs))
        except (store.NotFound, FileNotFoundError) as error:
            raise ToolError(str(error)) from error
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))

    server.tool(
        structured_output=False,
        annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
    )(run)
    return function


def _plain(text) -> str:
    """Lower case without diacritics, so that "plzen" finds Plzeň."""
    decomposed = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn").strip()


def _rounded(value):
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(item) for item in value]
    return value


def _page_url(election_id: str, code: str = "", tab: str = "") -> Optional[str]:
    """Address of the matching page, when the public address of the app is known."""
    base = (os.environ.get("VOLBY_PUBLIC_URL") or "").rstrip("/")
    if not base:
        return None
    return "/".join(part for part in (base, election_id, code, tab) if part)


def _with_url(result: dict, *page) -> dict:
    url = _page_url(*page)
    return {**result, "url": url} if url else result


def _find_list(lists: list, wanted: str) -> int:
    """Position of the list given by its number or a part of its name."""
    needle = _plain(wanted)
    exact = [
        i
        for i, item in enumerate(lists)
        if needle in (item["number"], _plain(item["name"]), _plain(item["fullName"]))
    ]
    found = exact or [
        i
        for i, item in enumerate(lists)
        if needle in _plain(item["name"]) or needle in _plain(item["fullName"])
    ]
    if len(found) == 1:
        return found[0]
    names = ", ".join(f"{lists[i]['number']}: {lists[i]['name']}" for i in found or range(len(lists)))
    problem = "odpovídá více kandidátkám" if found else "neodpovídá žádné kandidátce"
    raise ToolError(f"„{wanted}“ {problem}. Na výběr: {names}")


@tool
def seznam_voleb() -> dict:
    """Volby, které jsou k dispozici, a ke kterým dřívějším volbám se dají srovnat."""
    return {"elections": [e for e in store.list_elections() if e["hasData"]]}


@tool
def prehled_voleb(volby: Election) -> dict:
    """Celostátní souhrn voleb: počet zastupitelstev, účast a největší města s vítězem.
    U sněmovních voleb vrací volební kraje a celostátní výsledky stran."""
    return _with_url(_rounded(store.election_overview(volby)), volby)


@tool
def hledej_zastupitelstvo(
    volby: Election,
    dotaz: Annotated[str, Field(description="Název obce, městské části nebo kraje, i bez diakritiky")],
    limit: Annotated[int, Field(ge=1, le=50)] = 10,
) -> dict:
    """Najde zastupitelstva (u sněmovních voleb volební kraje) podle názvu a vrátí jejich kódy.
    Obce stejného jména rozliší pole note s okresem nebo nadřazeným městem."""
    needle = _plain(dotaz)
    matches = [c for c in store.list_councils(volby) if needle in _plain(c["name"])]

    def rank(council):
        name = _plain(council["name"])
        return (name != needle, not name.startswith(needle), -council["registered"])

    matches.sort(key=rank)
    return {"total": len(matches), "councils": matches[:limit]}


@tool
def vysledky_zastupitelstva(volby: Election, kod: Code) -> dict:
    """Výsledek voleb v jednom zastupitelstvu nebo volebním kraji: účast, hlasy, podíly
    a mandáty kandidátek a jejich výsledek v předchozích volbách, pokud jsou k dispozici."""
    council = store.council(volby, kod)
    result = {
        key: council[key]
        for key in (
            "code", "name", "kind", "parent", "election", "previous",
            "seats", "summary", "previousSummary", "lists", "areas",
        )
    }
    result["flowsAvailable"] = bool(
        council["previous"] and len(council["precincts"]) >= council["minPrecinctsForFlows"]
    )
    return _with_url(_rounded(result), volby, kod)


@tool
def vysledky_okrsku(
    volby: Election,
    kod: Code,
    kandidatka: Annotated[
        Optional[str],
        Field(description="Číslo nebo část názvu kandidátky; bez ní se u okrsku vrací vítěz"),
    ] = None,
    cast: Area = None,
    radit: Annotated[
        Literal["cislo", "ucast", "volici", "podil"],
        Field(description="Řazení: číslo okrsku, účast, počet voličů, nebo podíl kandidátky"),
    ] = "cislo",
    sestupne: bool = False,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS)] = 50,
    od: Annotated[int, Field(ge=0, description="Kolik okrsků přeskočit, pro další stránku")] = 0,
) -> dict:
    """Výsledky po volebních okrscích: voliči, účast a buď výsledek zvolené kandidátky,
    nebo vítěz okrsku. Hodí se k otázkám typu „kde byla kandidátka nejsilnější“.
    V komunálních volbách má volič tolik hlasů, kolik se volí zastupitelů, takže
    hlasů (validVotes, votes) je víc než voličů; share je podíl ze všech hlasů v okrsku."""
    council = store.council(volby, kod)
    lists = council["lists"]
    followed = _find_list(lists, kandidatka) if kandidatka else None
    if radit == "podil" and followed is None:
        raise ToolError("Řazení podle podílu potřebuje parametr kandidatka.")
    area_names = {area["code"]: area["name"] for area in council["areas"]}

    rows = []
    for precinct in council["precincts"]:
        if cast and precinct["area"] != cast:
            continue
        votes = precinct["votes"]
        valid = sum(votes)
        slot = followed if followed is not None else max(range(len(votes)), key=votes.__getitem__, default=None)
        row = {
            "number": precinct["number"],
            "registered": precinct["registered"],
            "turnout": precinct["turnout"],
            "validVotes": valid,
        }
        if area_names:
            row["area"] = area_names.get(precinct["area"], precinct["area"])
        if slot is not None:
            share = votes[slot] / valid * 100 if valid else 0.0
            row["votes"], row["share"] = votes[slot], share
            if followed is None:
                row["winner"] = lists[slot]["name"]
        rows.append(row)

    def number(row):
        return (row.get("area", ""), int(row["number"]) if row["number"].isdigit() else 0)

    keys = {
        "cislo": number,
        "ucast": lambda row: row["turnout"],
        "volici": lambda row: row["registered"],
        "podil": lambda row: row.get("share", 0),
    }
    rows.sort(key=keys[radit], reverse=sestupne)
    result = {
        "council": council["name"],
        "list": lists[followed]["name"] if followed is not None else None,
        "total": len(rows),
        "from": od,
        "precincts": rows[od : od + limit],
    }
    return _with_url(_rounded(result), volby, kod, "okrsky")


@tool
def presuny_volicu(
    volby: Election,
    kod: Code,
    cast: Area = None,
    nejmensi_podil: Annotated[
        float,
        Field(ge=0, description="Vynechá přesuny menší než tolik procent všech voličů v seznamu"),
    ] = 0.3,
) -> dict:
    """Odhad, kam se mezi předchozími a těmito volbami přesunuli voliči jednotlivých
    kandidátek a nevoliči. Jde o statistický odhad z výsledků okrsků, proto má každý
    přesun rozpětí (low–high); ber ho jako přibližný, zvlášť když rough je true.
    Jen pro komunální volby a zastupitelstva s dostatkem okrsků."""
    comparison = store.comparison(volby, kod, cast)
    result = {
        key: comparison[key]
        for key in ("previousYear", "currentYear", "matched", "skipped", "rough")
    }
    flows = comparison["flows"]
    if not flows:
        result["flows"] = None
        result["reason"] = (
            f"Odhad potřebuje aspoň {comparison['minPrecincts']} okrsků, "
            f"které jdou mezi volbami spárovat; tady jich je {comparison['matched']}."
        )
        return result

    sources, targets = flows["sources"], flows["targets"]
    rows = []
    for i, source in enumerate(sources):
        for j, target in enumerate(targets):
            if flows["electorate"][i][j] < nejmensi_podil:
                continue
            rows.append(
                {
                    "from": source,
                    "to": target,
                    # Share of the source group that made this move
                    "share": flows["transitions"][i][j],
                    "low": flows["transitionsLow"][i][j],
                    "high": flows["transitionsHigh"][i][j],
                    "ofAllVoters": flows["electorate"][i][j],
                    # Share of the target group that came this way
                    "ofTarget": flows["origin"][i][j],
                }
            )
    rows.sort(key=lambda row: -row["ofAllVoters"])
    result.update(
        {
            "units": (
                "share, low a high: procenta voličů skupiny from, kteří přešli ke skupině to. "
                "ofAllVoters: procenta všech voličů v seznamu. ofTarget: jakou část skupiny to "
                "tito voliči tvoří. size: procenta všech voličů v seznamu."
            ),
            "interval": flows["interval"],
            "previousGroups": [
                {"name": name, "size": size} for name, size in zip(sources, flows["sourceSize"])
            ],
            "currentGroups": [
                {"name": name, "size": size} for name, size in zip(targets, flows["targetSize"])
            ],
            "flows": rows,
            "newlyVoted": flows["newlyVoted"],
            "stoppedVoting": flows["stoppedVoting"],
            "stayedHome": flows["stayedHome"],
            "explained": flows["explained"],
        }
    )
    return _with_url(_rounded(result), volby, kod, "presuny")


@tool
def kandidati(
    volby: Election,
    kod: Code,
    strana: Annotated[Optional[str], Field(description="Část názvu strany")] = None,
    jmeno: Annotated[Optional[str], Field(description="Část jména kandidáta")] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS)] = 50,
) -> dict:
    """Kandidáti ve volebním kraji seřazení podle přednostních hlasů. Jen pro sněmovní volby."""
    if not store.council(volby, kod)["hasCandidates"]:
        raise ToolError("Kandidáty máme jen u sněmovních voleb, po volebních krajích.")
    everyone = store.candidates(volby, kod)
    # Without a single elected candidate the data do not say who got a seat
    knows_elected = any(candidate["elected"] for candidate in everyone)
    party, name = _plain(strana), _plain(jmeno)
    rows = [
        candidate if knows_elected else {k: v for k, v in candidate.items() if k != "elected"}
        for candidate in everyone
        if party in _plain(candidate["list"]) and name in _plain(candidate["name"])
    ]
    rows.sort(key=lambda candidate: -(candidate["votes"] or 0))
    result = {"total": len(rows), "candidates": rows[:limit]}
    return _with_url(_rounded(result), volby, kod, "kandidati")


def http_routes(path: str = "/mcp") -> list:
    """Routes that serve the tools over HTTP, to be added to the API.

    Each request stands alone and gets a plain JSON answer, which is all that
    tools without progress or notifications need. The check of the Host header
    is off because the app is reached under the address of whoever deploys it,
    and the tools only read public data.
    """
    app = server.streamable_http_app(
        streamable_http_path=path,
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return list(app.routes)


if __name__ == "__main__":
    # The data are found relative to the repository root, and a client may
    # start the server from anywhere
    os.chdir(Path(__file__).resolve().parent.parent)
    server.run()

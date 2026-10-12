"""Run with: uv run --with pytest pytest tests/"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parent.parent / "src"))

import web_mcp  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

LISTS = [
    {"number": "4", "name": "ANO 2011", "fullName": "ANO 2011"},
    {"number": "11", "name": "Piráti", "fullName": "Česká pirátská strana"},
    {"number": "8", "name": "ODS", "fullName": "Občanská demokratická strana"},
]


def precinct(number, registered, turnout, votes):
    return {
        "id": number, "number": number, "area": "1", "registered": registered,
        "ballots": 0, "turnout": turnout, "votes": votes,
    }


COUNCIL = {
    "name": "Testov",
    "lists": LISTS,
    "areas": [],
    "precincts": [
        precinct("1", 500, 40.0, [50, 30, 20]),
        precinct("2", 800, 55.0, [10, 60, 30]),
        precinct("3", 300, 35.0, [45, 5, 50]),
    ],
}


def call(name, **arguments):
    result = asyncio.run(web_mcp.server.call_tool(name, arguments))
    return json.loads(result.content[0].text)


@pytest.fixture(autouse=True)
def fake_store(monkeypatch):
    monkeypatch.delenv("VOLBY_PUBLIC_URL", raising=False)
    monkeypatch.setattr(web_mcp.store, "council", lambda election, code: COUNCIL)
    monkeypatch.setattr(
        web_mcp.store,
        "list_councils",
        lambda election: [
            {"code": "1", "name": "Plzeň 1", "note": "", "registered": 900},
            {"code": "2", "name": "Plzeň", "note": "", "registered": 500},
            {"code": "3", "name": "Brno", "note": "", "registered": 800},
            {"code": "4", "name": "Dolní Plzeň", "note": "", "registered": 950},
        ],
    )


def test_search_ignores_diacritics_and_puts_the_exact_name_first():
    found = call("hledej_zastupitelstvo", volby="kv2026", dotaz="plzen")
    assert found["total"] == 3
    assert [c["name"] for c in found["councils"]] == ["Plzeň", "Plzeň 1", "Dolní Plzeň"]


def test_precincts_are_ranked_by_the_share_of_the_chosen_list():
    result = call(
        "vysledky_okrsku", volby="kv2026", kod="1",
        kandidatka="pirat", radit="podil", sestupne=True, limit=2,
    )
    assert result["list"] == "Piráti"
    assert result["total"] == 3
    assert [(p["number"], p["share"]) for p in result["precincts"]] == [("2", 60.0), ("1", 30.0)]


def test_precincts_without_a_list_name_their_winner():
    result = call("vysledky_okrsku", volby="kv2026", kod="1")
    assert [p["winner"] for p in result["precincts"]] == ["ANO 2011", "Piráti", "ODS"]


def test_list_is_found_by_number_and_an_unknown_one_lists_the_choices():
    assert call("vysledky_okrsku", volby="kv2026", kod="1", kandidatka="8")["list"] == "ODS"
    with pytest.raises(ToolError, match="11: Piráti"):
        call("vysledky_okrsku", volby="kv2026", kod="1", kandidatka="zelení")


def test_page_address_is_added_only_when_the_public_address_is_known(monkeypatch):
    assert "url" not in call("vysledky_okrsku", volby="kv2026", kod="1")
    monkeypatch.setenv("VOLBY_PUBLIC_URL", "https://volby.example/")
    result = call("vysledky_okrsku", volby="kv2026", kod="1")
    assert result["url"] == "https://volby.example/kv2026/1/okrsky"

"""Tests for anait_lanzamientos.py"""

import json
import os
import sys
import tempfile
from datetime import date

import pytest
from bs4 import BeautifulSoup
from icalendar import Calendar

import anait_lanzamientos
from anait_lanzamientos import (
    GameLaunch,
    _adjust_year_crossing,
    _find_steam_url,
    _parse_metadata_block,
    extract_date_from_text,
    get_existing_uids,
    load_existing_calendar,
    load_state,
    main,
    merge_events,
    parse_article,
    parse_featured_games,
    parse_list_games,
    parse_spanish_date,
    save_state,
)


# ── parse_spanish_date ─────────────────────────────────────────────────


class TestParseSpanishDate:
    def test_basic(self):
        assert parse_spanish_date("19", "marzo", 2025) == date(2025, 3, 19)

    def test_case_insensitive(self):
        assert parse_spanish_date("1", "Enero", 2025) == date(2025, 1, 1)

    def test_invalid_month(self):
        assert parse_spanish_date("1", "foobar", 2025) is None

    def test_invalid_day(self):
        assert parse_spanish_date("31", "febrero", 2025) is None

    def test_leading_whitespace_month(self):
        assert parse_spanish_date("5", " abril ", 2025) == date(2025, 4, 5)


# ── _adjust_year_crossing ──────────────────────────────────────────────


class TestAdjustYearCrossing:
    def test_november_to_january(self):
        d = date(2025, 1, 15)
        assert _adjust_year_crossing(d, 2025, article_month=11) == date(2026, 1, 15)

    def test_december_to_february(self):
        d = date(2025, 2, 10)
        assert _adjust_year_crossing(d, 2025, article_month=12) == date(2026, 2, 10)

    def test_no_crossing_same_year(self):
        d = date(2025, 3, 10)
        assert _adjust_year_crossing(d, 2025, article_month=3) == date(2025, 3, 10)

    def test_november_to_november_no_crossing(self):
        d = date(2025, 11, 20)
        assert _adjust_year_crossing(d, 2025, article_month=11) == date(2025, 11, 20)

    def test_october_article_no_crossing(self):
        d = date(2025, 1, 5)
        assert _adjust_year_crossing(d, 2025, article_month=10) == date(2025, 1, 5)


# ── extract_date_from_text ─────────────────────────────────────────────


class TestExtractDateFromText:
    def test_basic_date(self):
        assert extract_date_from_text("Lanzamiento: 19 de marzo", 2025) == date(2025, 3, 19)

    def test_date_in_longer_text(self):
        text = "Sale el 5 de junio en todas las plataformas"
        assert extract_date_from_text(text, 2025) == date(2025, 6, 5)

    def test_no_date(self):
        assert extract_date_from_text("No hay fecha aquí", 2025) is None

    def test_year_crossing(self):
        result = extract_date_from_text("15 de enero", 2025, article_month=12)
        assert result == date(2026, 1, 15)


# ── _parse_metadata_block ─────────────────────────────────────────────


class TestParseMetadataBlock:
    def test_full_block(self):
        text = (
            "Desarrolla: Studio X\n"
            "Publica: Editor Y\n"
            "Lanzamiento: 19 de marzo\n"
            "Disponible en: PC, PS5 y Xbox Series"
        )
        meta = _parse_metadata_block(text, 2025, 3)
        assert meta["developer"] == "Studio X"
        assert meta["publisher"] == "Editor Y"
        assert meta["launch_date"] == date(2025, 3, 19)
        assert meta["platforms"] == "PC, PS5 y Xbox Series"

    def test_desarrolla_y_publica(self):
        text = "Desarrolla y publica: Indie Dev\nLanzamiento: 1 de abril"
        meta = _parse_metadata_block(text, 2025, 4)
        assert meta["developer"] == "Indie Dev"
        assert meta["publisher"] == "Indie Dev"

    def test_edita_alias(self):
        text = "Desarrolla: A\nEdita: B\nLanzamiento: 10 de mayo"
        meta = _parse_metadata_block(text, 2025, 5)
        assert meta["publisher"] == "B"

    def test_no_date(self):
        text = "Desarrolla: X\nSin fecha aquí"
        meta = _parse_metadata_block(text, 2025, 3)
        assert meta["launch_date"] is None

    def test_commentary_collected(self):
        text = (
            "Lanzamiento: 1 de abril\n"
            "Short\n"
            "This is a long enough commentary line to be included in the output."
        )
        meta = _parse_metadata_block(text, 2025, 4)
        assert "long enough commentary" in meta["commentary"]
        assert "Short" not in meta["commentary"]

    def test_platform_from_lanzamiento_slash(self):
        text = "Lanzamiento: 5 de junio/ También disponible en PC y PS5"
        meta = _parse_metadata_block(text, 2025, 6)
        assert meta["launch_date"] == date(2025, 6, 5)
        assert "PC" in meta["platforms"]


# ── _find_steam_url ────────────────────────────────────────────────────


class TestFindSteamUrl:
    def test_finds_steam_link(self):
        html = '<p><a href="https://store.steampowered.com/app/12345">Steam</a></p>'
        soup = BeautifulSoup(html, "html.parser")
        elements = list(soup.children)
        assert _find_steam_url(elements) == "https://store.steampowered.com/app/12345"

    def test_no_steam_link(self):
        html = '<p><a href="https://example.com">Link</a></p>'
        soup = BeautifulSoup(html, "html.parser")
        assert _find_steam_url(list(soup.children)) == ""

    def test_empty_elements(self):
        assert _find_steam_url([]) == ""


# ── parse_featured_games ───────────────────────────────────────────────


FEATURED_HTML = """
<h2>Test Game</h2>
<p>Desarrolla: Cool Studio<br>
Publica: Big Publisher<br>
Lanzamiento: 19 de marzo<br>
Disponible en: PC, PS5 (<a href="https://store.steampowered.com/app/999">Steam</a>)</p>
<p>This is a really long editorial commentary about the game that should be captured.</p>
<hr>
"""


class TestParseFeaturedGames:
    def test_basic_featured(self):
        soup = BeautifulSoup(FEATURED_HTML, "html.parser")
        games = parse_featured_games(soup, 2025, 3, "https://example.com/article")
        assert len(games) == 1
        g = games[0]
        assert g.name == "Test Game"
        assert g.launch_date == date(2025, 3, 19)
        assert g.developer == "Cool Studio"
        assert g.publisher == "Big Publisher"
        assert g.featured is True
        assert "steampowered" in g.steam_url
        assert g.source_url == "https://example.com/article"

    def test_no_lanzamiento_field_skipped(self):
        html = "<h2>Some Header</h2><p>No date info here</p>"
        soup = BeautifulSoup(html, "html.parser")
        games = parse_featured_games(soup, 2025, 3, "")
        assert games == []

    def test_very_long_h2_skipped(self):
        html = f'<h2>{"A" * 200}</h2><p>Lanzamiento: 1 de enero</p>'
        soup = BeautifulSoup(html, "html.parser")
        games = parse_featured_games(soup, 2025, 1, "")
        assert games == []


# ── parse_list_games ───────────────────────────────────────────────────


LIST_HTML = """
<ul>
  <li>16 de marzo:
    <ul>
      <li><a href="https://store.steampowered.com/app/111">Game A</a> (PC, PS5)</li>
      <li>Game B (Xbox)</li>
    </ul>
  </li>
  <li>18 de marzo:
    <ul>
      <li><a href="https://example.com">Game C</a> (Switch)</li>
    </ul>
  </li>
</ul>
"""


class TestParseListGames:
    def test_basic_list(self):
        soup = BeautifulSoup(LIST_HTML, "html.parser")
        games = parse_list_games(soup, 2025, 3, "https://example.com/article")
        assert len(games) == 3

        a = games[0]
        assert a.name == "Game A"
        assert a.launch_date == date(2025, 3, 16)
        assert a.platforms == "PC, PS5"
        assert "steampowered" in a.steam_url
        assert a.featured is False

        b = games[1]
        assert b.name == "Game B"
        assert b.platforms == "Xbox"
        assert b.steam_url == ""

        c = games[2]
        assert c.launch_date == date(2025, 3, 18)
        assert c.steam_url == ""  # not a steam link

    def test_empty_ul(self):
        soup = BeautifulSoup("<ul></ul>", "html.parser")
        games = parse_list_games(soup, 2025, 3, "")
        assert games == []

    def test_year_crossing_in_list(self):
        html = """
        <ul><li>15 de enero:
            <ul><li>Game X (PC)</li></ul>
        </li></ul>
        """
        soup = BeautifulSoup(html, "html.parser")
        games = parse_list_games(soup, 2025, 12, "")
        assert len(games) == 1
        assert games[0].launch_date == date(2026, 1, 15)


# ── parse_article ──────────────────────────────────────────────────────


class TestParseArticle:
    def test_deduplication_featured_wins(self):
        html = (
            '<h2>Dupe Game</h2>'
            '<p>Desarrolla: Studio<br>Lanzamiento: 10 de abril</p>'
            '<p>A long editorial note that qualifies as commentary in the output.</p>'
            '<ul><li>10 de abril:<ul>'
            '<li>Dupe Game (PC)</li>'
            '</ul></li></ul>'
        )
        article = {
            "id": 1,
            "date": "2025-04-07T10:00:00",
            "title": "Test",
            "link": "https://example.com/noticias/test",
            "content_html": html,
        }
        games = parse_article(article)
        assert len(games) == 1
        assert games[0].featured is True


# ── merge_events ───────────────────────────────────────────────────────


class TestMergeEvents:
    def _new_cal(self):
        cal = Calendar()
        cal.add("prodid", "-//Test//")
        cal.add("version", "2.0")
        return cal

    def test_adds_events(self):
        cal = self._new_cal()
        games = [
            GameLaunch(name="Game A", launch_date=date(2025, 3, 19)),
            GameLaunch(name="Game B", launch_date=date(2025, 3, 20), featured=True),
        ]
        added = merge_events(cal, games)
        assert added == 2
        uids = get_existing_uids(cal)
        assert len(uids) == 2

    def test_dedup_skips_existing(self):
        cal = self._new_cal()
        games = [GameLaunch(name="Game A", launch_date=date(2025, 3, 19))]
        merge_events(cal, games)
        added = merge_events(cal, games)
        assert added == 0
        assert len(get_existing_uids(cal)) == 1

    def test_featured_prefix(self):
        cal = self._new_cal()
        games = [GameLaunch(name="Cool Game", launch_date=date(2025, 1, 1), featured=True)]
        merge_events(cal, games)
        for component in cal.walk():
            if component.name == "VEVENT":
                assert str(component.get("summary")).startswith("\U0001f3ae")


# ── GameLaunch.uid ─────────────────────────────────────────────────────


class TestGameLaunchUid:
    def test_deterministic(self):
        g = GameLaunch(name="Test", launch_date=date(2025, 1, 1))
        assert g.uid == g.uid

    def test_different_for_different_games(self):
        a = GameLaunch(name="Game A", launch_date=date(2025, 1, 1))
        b = GameLaunch(name="Game B", launch_date=date(2025, 1, 1))
        assert a.uid != b.uid

    def test_format(self):
        g = GameLaunch(name="Test", launch_date=date(2025, 1, 1))
        assert g.uid.endswith("@anait-lanzamientos")
        prefix = g.uid.split("@")[0]
        assert len(prefix) == 16


# ── load_state / save_state ────────────────────────────────────────────


class TestStateRoundTrip:
    def test_round_trip(self, tmp_path):
        path = str(tmp_path / "state.json")
        state = {"processed_ids": [100, 200], "last_run": None}
        save_state(path, state)
        loaded = load_state(path)
        assert set(loaded["processed_ids"]) == {100, 200}
        assert loaded["last_run"] is not None

    def test_missing_file_returns_default(self, tmp_path):
        path = str(tmp_path / "nonexistent.json")
        state = load_state(path)
        assert state == {"processed_ids": [], "last_run": None}

    def test_corrupt_json_returns_default(self, tmp_path):
        path = str(tmp_path / "corrupt.json")
        with open(path, "w") as f:
            f.write("{invalid json!!")
        state = load_state(path)
        assert state == {"processed_ids": [], "last_run": None}


# ── load_existing_calendar ─────────────────────────────────────────────


class TestLoadExistingCalendar:
    def test_missing_file_creates_new(self, tmp_path):
        path = str(tmp_path / "nonexistent.ics")
        cal = load_existing_calendar(path)
        assert cal.get("prodid") is not None

    def test_corrupt_ics_creates_new(self, tmp_path):
        path = str(tmp_path / "corrupt.ics")
        with open(path, "wb") as f:
            f.write(b"NOT VALID ICS DATA {{{")
        cal = load_existing_calendar(path)
        assert cal.get("prodid") is not None


# ── main: API failure detection ────────────────────────────────────────


class TestMainApiFailure:
    """main() must fail loudly when the API yields nothing usable.

    A silent 'No new articles' on an empty API response would leave the
    repo without commits, and GitHub disables scheduled workflows after
    60 days without activity.
    """

    @pytest.fixture(autouse=True)
    def _paths(self, tmp_path, monkeypatch):
        self.state_path = tmp_path / "state.json"
        self.ics_path = tmp_path / "out.ics"
        # Non-empty state so main() takes the incremental path.
        save_state(str(self.state_path), {"processed_ids": [1], "last_run": None})
        monkeypatch.setattr(
            sys, "argv",
            ["anait_lanzamientos.py",
             "--state", str(self.state_path),
             "--output", str(self.ics_path)],
        )

    def test_exits_1_when_api_returns_no_articles(self, monkeypatch, capsys):
        monkeypatch.setattr(
            anait_lanzamientos, "fetch_articles_from_api", lambda max_pages: []
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert "[error]" in capsys.readouterr().err
        assert not self.ics_path.exists()

    def test_exits_1_when_no_article_matches_weekly_url_pattern(
        self, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            anait_lanzamientos, "fetch_articles_from_api",
            lambda max_pages: [
                {"id": 5, "link": "https://www.anaitgames.com/articulos/x"},
                {"id": 6, "link": "https://www.anaitgames.com/articulos/y"},
            ],
        )
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert "[error]" in capsys.readouterr().err
        assert not self.ics_path.exists()

    def test_returns_normally_when_all_articles_already_processed(
        self, monkeypatch, capsys
    ):
        monkeypatch.setattr(
            anait_lanzamientos, "fetch_articles_from_api",
            lambda max_pages: [
                {"id": 1, "link": "https://www.anaitgames.com/noticias/x"},
            ],
        )
        main()  # must not raise
        assert "No new articles found." in capsys.readouterr().err
        assert not self.ics_path.exists()

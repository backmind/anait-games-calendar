"""Regression tests using real AnaitGames article HTML as fixtures.

These tests verify that the parser extracts the expected number and type
of games from actual articles.  If a parser refactor breaks extraction
from a known-good format, these tests catch it.

Fixtures were captured on 2026-04-13 from the WP REST API.
"""

import json
from pathlib import Path

import pytest

from anait_lanzamientos import parse_article

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)


# ── Weekly article: 2026-04-13 ─────────────────────────────────────────


class TestArticle20260413:
    """'Los videojuegos, una vida de ensueño' — weekly article."""

    @pytest.fixture(autouse=True)
    def parse(self):
        article = _load_fixture("los-videojuegos-una-vida-de-ensueno")
        self.games = parse_article(article)
        self.featured = [g for g in self.games if g.featured]
        self.listed = [g for g in self.games if not g.featured]

    def test_total_games(self):
        assert len(self.games) == 28

    def test_featured_count(self):
        assert len(self.featured) == 7

    def test_listed_count(self):
        assert len(self.listed) == 21

    def test_featured_names(self):
        names = {g.name for g in self.featured}
        assert "Pragmata" in names
        assert "Tomodachi Life: Una vida de ensueño" in names

    def test_dates_within_week(self):
        dates = {g.launch_date for g in self.games}
        for d in dates:
            assert d.year == 2026
            assert d.month == 4
            assert 13 <= d.day <= 19

    def test_no_duplicates(self):
        names_dates = [(g.name, g.launch_date) for g in self.games]
        assert len(names_dates) == len(set(names_dates))


# ── Weekly article: 2026-03-30 ─────────────────────────────────────────


class TestArticle20260330:
    """'Qué fue primero, el huevo o el pulpo' — weekly article."""

    @pytest.fixture(autouse=True)
    def parse(self):
        article = _load_fixture("que-fue-primero-el-huevo-o-el-pulpo")
        self.games = parse_article(article)
        self.featured = [g for g in self.games if g.featured]
        self.listed = [g for g in self.games if not g.featured]

    def test_total_games(self):
        assert len(self.games) == 28

    def test_featured_count(self):
        assert len(self.featured) == 7

    def test_listed_count(self):
        assert len(self.listed) == 21

    def test_featured_names(self):
        names = {g.name for g in self.featured}
        assert "South of Midnight" in names
        assert "Temtem: Swarm" in names

    def test_no_duplicates(self):
        names_dates = [(g.name, g.launch_date) for g in self.games]
        assert len(names_dates) == len(set(names_dates))


# ── Quarterly article (should be filtered upstream, but parser still works) ──


class TestQuarterlyArticle:
    """'Prima la calidad en primavera' — quarterly article.

    These are filtered by URL (/articulos/ vs /noticias/) in main(),
    but the parser itself should not crash on them.
    """

    def test_does_not_crash(self):
        article = _load_fixture("prima-la-calidad-en-primavera")
        games = parse_article(article)
        # Quarterly articles have variable structure; we just verify no exception
        assert isinstance(games, list)

#!/usr/bin/env python3
"""
anait_lanzamientos.py
─────────────────────
Incremental generator for an iCal calendar of video game launches
published weekly on AnaitGames (https://www.anaitgames.com/tag/lanzamientos).

Uses the WordPress REST API to discover articles and parses the HTML
content to extract game launch data.  Maintains a JSON state file to
track already-processed articles by WordPress post ID.

Usage:
    python anait_lanzamientos.py [--output FILE] [--state FILE] [--seed-pages N] [-v]
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup, NavigableString, Tag
from icalendar import Calendar, Event

# ── Config ──────────────────────────────────────────────────────────────

BASE_URL = "https://www.anaitgames.com"
API_POSTS_URL = f"{BASE_URL}/wp-json/wp/v2/posts"
TAG_LANZAMIENTOS_ID = 6806

HEADERS = {
    "User-Agent": "AnaitLanzamientosBot/1.0 (calendar; personal use)",
    "Accept-Language": "es",
}

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# ── Data model ──────────────────────────────────────────────────────────

@dataclass
class GameLaunch:
    name: str
    launch_date: date
    platforms: str = ""
    developer: str = ""
    publisher: str = ""
    commentary: str = ""
    steam_url: str = ""
    source_url: str = ""
    featured: bool = False

    @property
    def uid(self) -> str:
        raw = f"{self.name}:{self.launch_date.isoformat()}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16] + "@anait-lanzamientos"

# ── State management ────────────────────────────────────────────────────

def load_state(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"processed_ids": [], "last_run": None}


def save_state(path: str, state: dict):
    state["last_run"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

# ── ICS load/merge ──────────────────────────────────────────────────────

def load_existing_calendar(path: str) -> Calendar:
    if os.path.exists(path):
        with open(path, "rb") as f:
            return Calendar.from_ical(f.read())
    cal = Calendar()
    cal.add("prodid", "-//AnaitGames Lanzamientos//ES")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Lanzamientos — AnaitGames")
    cal.add("x-wr-caldesc", "Calendario de lanzamientos de videojuegos vía AnaitGames")
    return cal


def get_existing_uids(cal: Calendar) -> set[str]:
    uids = set()
    for component in cal.walk():
        if component.name == "VEVENT":
            uid = str(component.get("uid", ""))
            if uid:
                uids.add(uid)
    return uids


def merge_events(cal: Calendar, new_games: list[GameLaunch]) -> int:
    existing = get_existing_uids(cal)
    added = 0
    for g in new_games:
        if g.uid in existing:
            continue

        ev = Event()
        ev.add("uid", g.uid)
        ev.add("dtstart", g.launch_date)
        ev.add("dtend", g.launch_date + timedelta(days=1))

        prefix = "🎮 " if g.featured else ""
        ev.add("summary", f"{prefix}{g.name}")

        desc_parts: list[str] = []
        if g.developer:
            dev_line = f"Desarrolla: {g.developer}"
            if g.publisher and g.publisher != g.developer:
                dev_line += f"\nPublica: {g.publisher}"
            desc_parts.append(dev_line)
        if g.platforms:
            desc_parts.append(f"Plataformas: {g.platforms}")
        if g.commentary:
            desc_parts.append(f"\n{g.commentary}")
        if g.steam_url:
            desc_parts.append(f"\nSteam: {g.steam_url}")
        if g.source_url:
            desc_parts.append(f"Fuente: {g.source_url}")

        ev.add("description", "\n".join(desc_parts))

        if g.source_url:
            ev.add("url", g.source_url)

        cats = ["Lanzamiento"]
        if g.featured:
            cats.append("Destacado")
        ev.add("categories", cats)

        cal.add_component(ev)
        existing.add(g.uid)
        added += 1

    return added

# ── Parsing helpers ─────────────────────────────────────────────────────

_DATE_RE = re.compile(
    r"(\d{1,2})\s+de\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)",
    re.IGNORECASE,
)


def parse_spanish_date(day_str: str, month_str: str, year: int) -> Optional[date]:
    m = MESES.get(month_str.lower().strip())
    if m is None:
        return None
    try:
        return date(year, m, int(day_str))
    except ValueError:
        return None


def extract_date_from_text(
    text: str, year: int, article_month: int = 0
) -> Optional[date]:
    m = _DATE_RE.search(text)
    if m:
        d = parse_spanish_date(m.group(1), m.group(2), year)
        if d and article_month >= 11 and d.month <= 2:
            d = d.replace(year=year + 1)
        return d
    return None

# ── WordPress REST API ──────────────────────────────────────────────────

def fetch_articles_from_api(max_pages: int = 1) -> list[dict]:
    """Fetch article metadata from the WP REST API.

    Returns a list of dicts with keys: id, date, title, link, content_html.
    """
    articles: list[dict] = []
    for page_num in range(1, max_pages + 1):
        params = {
            "tags": TAG_LANZAMIENTOS_ID,
            "per_page": 10,
            "orderby": "date",
            "order": "desc",
            "page": page_num,
        }
        try:
            r = requests.get(
                API_POSTS_URL, params=params, headers=HEADERS, timeout=20
            )
            if r.status_code == 400:
                break
            r.raise_for_status()
        except Exception as e:
            print(f"[warn] API page {page_num}: {e}", file=sys.stderr)
            break

        posts = r.json()
        if not posts:
            break

        for post in posts:
            articles.append({
                "id": post["id"],
                "date": post["date"],
                "title": post["title"]["rendered"],
                "link": post["link"],
                "content_html": post["content"]["rendered"],
            })
    return articles

# ── Article parser ──────────────────────────────────────────────────────

def parse_featured_games(
    soup: BeautifulSoup, year: int, article_month: int, source_url: str
) -> list[GameLaunch]:
    """Parse featured games from <h2> sections with metadata in <p><br> blocks."""
    games: list[GameLaunch] = []

    for h2 in soup.find_all("h2"):
        name = h2.get_text(strip=True)
        if not name or len(name) > 120:
            continue

        # Collect text between this h2 and the next h2/hr
        block_parts: list[str] = []
        block_elements: list[Tag] = []
        for sib in h2.next_siblings:
            if isinstance(sib, NavigableString):
                t = sib.strip()
                if t:
                    block_parts.append(t)
                continue
            if isinstance(sib, Tag):
                if sib.name in ("h2", "hr"):
                    break
                block_parts.append(sib.get_text("\n", strip=True))
                block_elements.append(sib)

        block_text = "\n".join(block_parts)

        if "lanzamiento:" not in block_text.lower():
            continue

        launch_date = None
        developer = ""
        publisher = ""
        platforms = ""
        steam_url = ""
        commentary_lines: list[str] = []

        for line in block_text.split("\n"):
            line_s = line.strip()
            if not line_s:
                continue
            low = line_s.lower()

            if low.startswith("desarrolla y publica:"):
                developer = line_s.split(":", 1)[1].strip()
                publisher = developer
            elif low.startswith("desarrolla:"):
                developer = line_s.split(":", 1)[1].strip()
            elif low.startswith("publica:") or low.startswith("edita:"):
                publisher = line_s.split(":", 1)[1].strip()
            elif low.startswith("lanzamiento:"):
                # Handle cases like "Lanzamiento: 27 de mayo/ Ver en Steam"
                parts = line_s.split("/")
                launch_date = extract_date_from_text(
                    parts[0], year, article_month
                )
                # Check remaining parts for platform info
                for part in parts[1:]:
                    ps = part.strip()
                    ps_low = ps.lower()
                    if not platforms and (
                        "también" in ps_low
                        or any(
                            p in ps_low
                            for p in ["pc", "ps4", "ps5", "xbox", "switch"]
                        )
                    ):
                        platforms = re.sub(
                            r"^también\s+(se publica|disponible)\s+en:?\s*",
                            "",
                            ps,
                            flags=re.IGNORECASE,
                        )
            elif low.startswith("disponible en:"):
                raw_plat = line_s.split(":", 1)[1].strip()
                raw_plat = re.sub(r"\s*\(\s*$", "", raw_plat)
                raw_plat = re.sub(
                    r"\s*\(?ver en [^)]*\)?\s*$", "", raw_plat, flags=re.IGNORECASE
                )
                platforms = raw_plat
            else:
                if len(line_s) > 30:
                    commentary_lines.append(line_s)

        # Extract Steam URL from links in the block
        for el in block_elements:
            for a in el.find_all("a") if hasattr(el, "find_all") else []:
                href = a.get("href", "")
                if "store.steampowered.com" in href:
                    steam_url = href
                    break
            if steam_url:
                break

        if launch_date is None:
            print(
                f"  [warn] No date parsed for featured game: {name!r}",
                file=sys.stderr,
            )
            continue

        games.append(GameLaunch(
            name=name,
            launch_date=launch_date,
            platforms=platforms,
            developer=developer,
            publisher=publisher,
            commentary="\n".join(commentary_lines),
            steam_url=steam_url,
            source_url=source_url,
            featured=True,
        ))

    return games


def parse_list_games(
    soup: BeautifulSoup, year: int, article_month: int, source_url: str
) -> list[GameLaunch]:
    """Parse the additional games list at the end of articles (<ul>/<li>)."""
    games: list[GameLaunch] = []

    for ul in soup.find_all("ul"):
        for li in ul.find_all("li", recursive=False):
            li_text = li.get_text(strip=True)
            date_match = _DATE_RE.match(li_text)
            if date_match:
                current_date = parse_spanish_date(
                    date_match.group(1), date_match.group(2), year
                )
                if current_date and article_month >= 11 and current_date.month <= 2:
                    current_date = current_date.replace(year=year + 1)

                sub_ul = li.find("ul")
                if sub_ul and current_date:
                    for sub_li in sub_ul.find_all("li", recursive=False):
                        sub_text = sub_li.get_text(strip=True)
                        link_el = sub_li.find("a")
                        steam_url = ""
                        if link_el:
                            href = link_el.get("href", "")
                            if "store.steampowered.com" in href:
                                steam_url = href
                            game_name = link_el.get_text(strip=True)
                        else:
                            paren_idx = sub_text.find("(")
                            game_name = (
                                sub_text[:paren_idx].strip()
                                if paren_idx > 0
                                else sub_text
                            )

                        platforms = ""
                        paren_match = re.search(r"\(([^)]+)\)", sub_text)
                        if paren_match:
                            platforms = paren_match.group(1)

                        if game_name:
                            games.append(GameLaunch(
                                name=game_name,
                                launch_date=current_date,
                                platforms=platforms,
                                steam_url=steam_url,
                                source_url=source_url,
                                featured=False,
                            ))
    return games


def parse_article(article: dict) -> list[GameLaunch]:
    """Parse a single article from API data into a list of game launches."""
    content_html = article["content_html"]
    source_url = article["link"]

    article_dt = datetime.fromisoformat(article["date"])
    year = article_dt.year
    article_month = article_dt.month

    soup = BeautifulSoup(content_html, "html.parser")

    featured = parse_featured_games(soup, year, article_month, source_url)
    listed = parse_list_games(soup, year, article_month, source_url)

    # Deduplicate: featured takes priority (has commentary)
    seen: set[str] = set()
    result: list[GameLaunch] = []
    for g in featured:
        key = f"{g.name.lower()}:{g.launch_date}"
        if key not in seen:
            seen.add(key)
            result.append(g)
    for g in listed:
        key = f"{g.name.lower()}:{g.launch_date}"
        if key not in seen:
            seen.add(key)
            result.append(g)

    return result

# ── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Incremental AnaitGames launch calendar generator."
    )
    parser.add_argument(
        "--output", "-o", default="anait_lanzamientos.ics",
        help="Output .ics file (default: anait_lanzamientos.ics)",
    )
    parser.add_argument(
        "--state", "-s", default="anait_state.json",
        help="State file tracking processed post IDs (default: anait_state.json)",
    )
    parser.add_argument(
        "--seed-pages", type=int, default=0,
        help="Scrape N API pages to build history (0 = auto: 2 if first run, 1 otherwise)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
    )
    args = parser.parse_args()

    state = load_state(args.state)
    processed_ids = set(state["processed_ids"])
    is_first_run = len(processed_ids) == 0

    if args.seed_pages > 0:
        pages = args.seed_pages
    elif is_first_run:
        pages = 2
    else:
        pages = 1

    print(
        f"{'Seed' if is_first_run else 'Incremental'} run, "
        f"checking {pages} API page(s)...",
        file=sys.stderr,
    )

    all_articles = fetch_articles_from_api(max_pages=pages)

    # Only process weekly articles (/noticias/), skip quarterly (/articulos/)
    weekly_articles = [a for a in all_articles if "/noticias/" in a["link"]]
    skipped = len(all_articles) - len(weekly_articles)
    if skipped:
        print(f"Skipped {skipped} non-weekly article(s).", file=sys.stderr)

    new_articles = [a for a in weekly_articles if a["id"] not in processed_ids]

    if not new_articles:
        print("No new articles found.", file=sys.stderr)
        return

    print(
        f"Found {len(new_articles)} new article(s) to process.", file=sys.stderr
    )

    new_games: list[GameLaunch] = []
    for i, article in enumerate(new_articles, 1):
        print(f"  [{i}/{len(new_articles)}] {article['link']}", file=sys.stderr)
        games = parse_article(article)
        new_games.extend(games)
        processed_ids.add(article["id"])

        if args.verbose:
            for g in games:
                star = "★" if g.featured else " "
                print(f"    {star} {g.launch_date}  {g.name}", file=sys.stderr)

    cal = load_existing_calendar(args.output)
    added = merge_events(cal, new_games)

    with open(args.output, "wb") as f:
        f.write(cal.to_ical())

    state["processed_ids"] = sorted(processed_ids)
    save_state(args.state, state)

    print(
        f"Done: {added} new events added "
        f"({len(new_games)} parsed, dupes skipped).",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()

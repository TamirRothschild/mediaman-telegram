import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

PLEX_URL   = os.getenv("PLEX_URL", "http://192.168.1.166:32400")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")


def _get(endpoint: str, params: dict = {}) -> ET.Element | None:
    """GET request to Plex, returns parsed XML root or None."""
    try:
        resp = requests.get(
            f"{PLEX_URL}/{endpoint}",
            params={"X-Plex-Token": PLEX_TOKEN, **params},
            timeout=5,
        )
        return ET.fromstring(resp.text)
    except Exception:
        return None


def _thumb_url(thumb: str) -> str | None:
    if not thumb:
        return None
    return f"{PLEX_URL}{thumb}?X-Plex-Token={PLEX_TOKEN}"


def _match_type(item_type: str, media_type: str) -> bool:
    if media_type == "movie":
        return item_type == "movie"
    if media_type == "tv":
        return item_type in ("show", "series")
    return False


def search_plex(title: str, media_type: str = "movie", year: str = None, imdb_id: str = None) -> dict | None:
    """
    Search Plex for a title using two strategies:
    1. Text search (finds Hebrew titles via Original Title)
    2. IMDB ID lookup (fallback)
    Returns dict {title, year, thumb} or None.
    """
    if not PLEX_TOKEN:
        return None

    # Strategy 1 — text search
    root = _get("search", {"query": title})
    if root is not None:
        for tag in ("Video", "Directory"):
            for item in root.iter(tag):
                item_type = item.get("type", "")
                if not _match_type(item_type, media_type):
                    continue
                item_year = item.get("year", "")
                if year and item_year and item_year != str(year):
                    continue
                return {
                    "title": item.get("title", title),
                    "year": item_year,
                    "thumb": _thumb_url(item.get("thumb", "")),
                }

    # Strategy 2 — IMDB ID lookup per section
    if imdb_id:
        sections_root = _get("library/sections")
        if sections_root is not None:
            for section in sections_root.iter("Directory"):
                sec_type = section.get("type", "")
                if media_type == "movie" and sec_type != "movie":
                    continue
                if media_type == "tv" and sec_type != "show":
                    continue
                sec_key = section.get("key")
                sec_root = _get(f"library/sections/{sec_key}/all", {"guid": f"imdb://{imdb_id}"})
                if sec_root is None:
                    continue
                for tag in ("Video", "Directory"):
                    for item in sec_root.iter(tag):
                        return {
                            "title": item.get("title", title),
                            "year": item.get("year", ""),
                            "thumb": _thumb_url(item.get("thumb", "")),
                        }

    return None


def is_available_on_plex(title: str, media_type: str = "movie") -> bool:
    return search_plex(title, media_type) is not None
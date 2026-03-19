import os
import requests
from dotenv import load_dotenv

load_dotenv()

PLEX_URL   = os.getenv("PLEX_URL", "http://192.168.1.166:32400")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")


def _headers() -> dict:
    return {
        "X-Plex-Token": PLEX_TOKEN,
        "Accept": "application/json",
    }


def _thumb_url(thumb: str) -> str | None:
    if not thumb:
        return None
    return f"{PLEX_URL}{thumb}?X-Plex-Token={PLEX_TOKEN}"


def _parse_result(item: dict, media_type: str) -> dict | None:
    """Validate and return a Plex result dict if type matches."""
    plex_type = item.get("type", "")
    if media_type == "movie" and plex_type != "movie":
        return None
    if media_type == "tv" and plex_type not in ("show", "series"):
        return None
    return {
        "title": item.get("title", ""),
        "year": str(item.get("year", "")),
        "thumb": _thumb_url(item.get("thumb", "")),
        "plex_url": PLEX_URL,
    }


def search_plex(title: str, media_type: str = "movie", year: str = None, imdb_id: str = None) -> dict | None:
    """
    Search Plex for a title.
    Tries multiple strategies:
    1. Search by English title
    2. Search by year (if provided) to filter results
    3. Search by IMDB ID via Plex's GUID matching

    Returns dict {title, year, thumb, plex_url} or None.
    """
    if not PLEX_TOKEN:
        return None

    # Strategy 1 — search by title
    result = _search_by_query(title, media_type, year)
    if result:
        return result

    # Strategy 2 — search by IMDB ID if available
    if imdb_id:
        result = _search_by_imdb(imdb_id, media_type)
        if result:
            return result

    return None


def _search_by_query(title: str, media_type: str, year: str = None) -> dict | None:
    """Search Plex /search endpoint by title string."""
    try:
        resp = requests.get(
            f"{PLEX_URL}/search",
            params={"query": title},
            headers=_headers(),
            timeout=5,
        )
        items = resp.json().get("MediaContainer", {}).get("Metadata", [])

        for item in items:
            parsed = _parse_result(item, media_type)
            if not parsed:
                continue
            # If year provided, verify it matches
            if year and parsed["year"] and parsed["year"] != str(year):
                continue
            return parsed

    except Exception:
        pass
    return None


def _search_by_imdb(imdb_id: str, media_type: str) -> dict | None:
    """
    Search Plex library sections for a specific IMDB ID.
    Useful when the title is in Hebrew or another language.
    """
    try:
        # Get list of library sections
        resp = requests.get(
            f"{PLEX_URL}/library/sections",
            headers=_headers(),
            timeout=5,
        )
        sections = resp.json().get("MediaContainer", {}).get("Directory", [])

        for section in sections:
            sec_type = section.get("type", "")
            if media_type == "movie" and sec_type != "movie":
                continue
            if media_type == "tv" and sec_type != "show":
                continue

            sec_key = section.get("key")
            # Search this section by IMDB GUID
            search_resp = requests.get(
                f"{PLEX_URL}/library/sections/{sec_key}/all",
                params={"guid": f"imdb://{imdb_id}"},
                headers=_headers(),
                timeout=5,
            )
            items = search_resp.json().get("MediaContainer", {}).get("Metadata", [])
            if items:
                item = items[0]
                return {
                    "title": item.get("title", ""),
                    "year": str(item.get("year", "")),
                    "thumb": _thumb_url(item.get("thumb", "")),
                    "plex_url": PLEX_URL,
                }

    except Exception:
        pass
    return None


def is_available_on_plex(title: str, media_type: str = "movie") -> bool:
    return search_plex(title, media_type) is not None
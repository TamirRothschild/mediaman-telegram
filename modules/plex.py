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


def search_plex(title: str, media_type: str = "movie") -> dict | None:
    """
    Search Plex library for a title.
    Returns dict with {title, year, thumb, url} if found, else None.
    """
    if not PLEX_TOKEN:
        return None

    try:
        resp = requests.get(
            f"{PLEX_URL}/search",
            params={"query": title},
            headers=_headers(),
            timeout=5,
        )
        data = resp.json()
        results = data.get("MediaContainer", {}).get("Metadata", [])

        for item in results:
            plex_type = item.get("type", "")
            if media_type == "movie" and plex_type != "movie":
                continue
            if media_type == "tv" and plex_type not in ("show", "series"):
                continue

            thumb = item.get("thumb", "")
            thumb_url = f"{PLEX_URL}{thumb}?X-Plex-Token={PLEX_TOKEN}" if thumb else None

            return {
                "title": item.get("title", title),
                "year": str(item.get("year", "")),
                "thumb": thumb_url,
                "plex_url": PLEX_URL,
            }

    except Exception:
        return None

    return None


def is_available_on_plex(title: str, media_type: str = "movie") -> bool:
    """Quick check — is this title available on Plex?"""
    return search_plex(title, media_type) is not None
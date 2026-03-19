import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

PLEX_URL   = os.getenv("PLEX_URL", "http://192.168.1.166:32400")
PLEX_TOKEN = os.getenv("PLEX_TOKEN", "")


def _get_xml(endpoint: str, params: dict = {}) -> ET.Element | None:
    try:
        resp = requests.get(
            f"{PLEX_URL}/{endpoint}",
            params={"X-Plex-Token": PLEX_TOKEN, **params},
            timeout=5,
        )
        # Use content (bytes) instead of text to handle encoding correctly
        return ET.fromstring(resp.content)
    except Exception as e:
        return None


def _thumb_url(thumb: str) -> str | None:
    if not thumb:
        return None
    return f"{PLEX_URL}{thumb}?X-Plex-Token={PLEX_TOKEN}"


def _match_type(plex_type: str, media_type: str) -> bool:
    if media_type == "movie":
        return plex_type == "movie"
    if media_type == "tv":
        return plex_type == "show"
    return False


def search_plex(title: str, media_type: str = "movie", year: str = None, imdb_id: str = None) -> dict | None:
    if not PLEX_TOKEN:
        return None

    # Strategy 1 — text search
    root = _get_xml("search", {"query": title})
    if root is not None:
        for item in root.iter():
            plex_type = item.get("type", "")
            if not _match_type(plex_type, media_type):
                continue
            item_year = item.get("year", "")
            if year and item_year and item_year != str(year):
                continue
            return {
                "title": item.get("title", title),
                "year": item_year,
                "thumb": _thumb_url(item.get("thumb", "")),
            }

    # Strategy 2 — IMDB ID per section
    if imdb_id:
        sections_root = _get_xml("library/sections")
        if sections_root is not None:
            for section in sections_root.iter("Directory"):
                sec_type = section.get("type", "")
                if media_type == "movie" and sec_type != "movie":
                    continue
                if media_type == "tv" and sec_type != "show":
                    continue
                sec_key = section.get("key")
                sec_root = _get_xml(
                    f"library/sections/{sec_key}/all",
                    {"guid": f"imdb://{imdb_id}"}
                )
                if sec_root is None:
                    continue
                for item in sec_root.iter():
                    plex_type = item.get("type", "")
                    if not _match_type(plex_type, media_type):
                        continue
                    return {
                        "title": item.get("title", title),
                        "year": item.get("year", ""),
                        "thumb": _thumb_url(item.get("thumb", "")),
                    }

    return None


def is_available_on_plex(title: str, media_type: str = "movie") -> bool:
    return search_plex(title, media_type) is not None


def get_stream_url(title: str, media_type: str = "movie") -> str | None:
    """Return a direct stream URL for the title."""
    root = _get_xml("search", {"query": title})
    if root is None:
        return None

    for item in root.iter():
        plex_type = item.get("type", "")
        if not _match_type(plex_type, media_type):
            continue
        key = item.get("key", "")
        if key:
            return f"{PLEX_URL}/web/index.html#!/server/{item.get('machineIdentifier', '')}/details?key={key}&X-Plex-Token={PLEX_TOKEN}"
    return None


def get_episode_stream(show: str, season: int, episode: int) -> dict | None:
    """
    Find a specific episode in Plex and return stream info.
    Returns dict {title, stream_url, file_size} or None.
    """
    # Find the show first
    root = _get_xml("search", {"query": show})
    if root is None:
        return None

    show_key = None
    for item in root.iter():
        if item.get("type") == "show":
            show_key = item.get("ratingKey")
            break

    if not show_key:
        return None

    # Get seasons
    seasons_root = _get_xml(f"library/metadata/{show_key}/children")
    if seasons_root is None:
        return None

    season_key = None
    for item in seasons_root.iter("Directory"):
        if item.get("type") == "season" and item.get("index") == str(season):
            season_key = item.get("ratingKey")
            break

    if not season_key:
        return None

    # Get episodes
    episodes_root = _get_xml(f"library/metadata/{season_key}/children")
    if episodes_root is None:
        return None

    for item in episodes_root.iter("Video"):
        if item.get("type") == "episode" and item.get("index") == str(episode):
            # Get file part
            part = item.find(".//Part")
            if part is None:
                return None

            file_key  = part.get("key", "")
            file_size = int(part.get("size", 0))
            duration  = int(item.get("duration", 0)) // 1000  # seconds
            ep_title  = item.get("title", f"S{season:02d}E{episode:02d}")

            return {
                "title": ep_title,
                "show": item.get("grandparentTitle", show),
                "season": season,
                "episode": episode,
                "stream_url": f"{PLEX_URL}{file_key}?X-Plex-Token={PLEX_TOKEN}",
                "file_size": file_size,
                "duration": duration,
                "thumb": _thumb_url(item.get("thumb", "")),
            }

    return None
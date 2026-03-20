import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

load_dotenv()

PLEX_URL      = os.getenv("PLEX_URL", "http://192.168.1.166:32400")
PLEX_TOKEN    = os.getenv("PLEX_TOKEN", "")


_machine_id = None

def get_machine_id() -> str:
    """Get Plex server machine identifier (cached)."""
    global _machine_id
    if _machine_id:
        return _machine_id
    try:
        root = _get_xml("identity")
        if root is not None:
            _machine_id = root.get("machineIdentifier", "")
    except Exception:
        pass
    return _machine_id or ""


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


def get_show_seasons(show: str) -> list | None:
    """Return list of seasons for a show. Each: {key, season_num, title, episode_count}"""
    root = _get_xml("search", {"query": show})
    if root is None:
        return None

    show_key = None
    show_title = show
    for item in root.iter():
        if item.get("type") == "show":
            show_key = item.get("ratingKey")
            show_title = item.get("title", show)
            break

    if not show_key:
        return None

    seasons_root = _get_xml(f"library/metadata/{show_key}/children")
    if seasons_root is None:
        return None

    seasons = []
    for item in seasons_root.iter("Directory"):
        if item.get("type") == "season":
            seasons.append({
                "key": item.get("ratingKey"),
                "season_num": int(item.get("index", 0)),
                "title": item.get("title", f"Season {item.get('index')}"),
                "episode_count": int(item.get("leafCount", 0)),
                "show_title": show_title,
            })

    return sorted(seasons, key=lambda x: x["season_num"])


def get_season_episodes(season_key: str) -> list | None:
    """Return list of episodes for a season key."""
    episodes_root = _get_xml(f"library/metadata/{season_key}/children")
    if episodes_root is None:
        return None

    episodes = []
    for item in episodes_root.iter("Video"):
        if item.get("type") == "episode":
            part = item.find(".//Part")
            rating_key = item.get("ratingKey", "")
            machine_id = get_machine_id()

            # Get plex:// GUID for native app deep link
            guid = item.get("guid", "")  # e.g. plex://episode/5d9c...
            plex_app_url = guid if guid.startswith("plex://") else None

            # Web player URL
            plex_web_url = (
                f"{PLEX_URL}/web/index.html"
                f"#!/server/{machine_id}/details"
                f"?key=%2Flibrary%2Fmetadata%2F{rating_key}"
                f"&X-Plex-Token={PLEX_TOKEN}"
            )

            # Direct file URL — works with VLC, MX Player, etc.
            direct_url = (
                f"{PLEX_URL}{part.get('key')}?X-Plex-Token={PLEX_TOKEN}"
                if part is not None else None
            )

            episodes.append({
                "key": rating_key,
                "episode_num": int(item.get("index", 0)),
                "title": item.get("title", f"Episode {item.get('index')}"),
                "duration": int(item.get("duration", 0)) // 60000,  # minutes
                "thumb": _thumb_url(item.get("thumb", "")),
                "stream_url": plex_web_url,
                "direct_url": direct_url,
                "plex_app_url": plex_app_url,
                "show": item.get("grandparentTitle", ""),
                "season": int(item.get("parentIndex", 0)),
                "machine_id": machine_id,
            })

    return sorted(episodes, key=lambda x: x["episode_num"])
import os
import requests
from dotenv import load_dotenv

load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"


def _p(**kwargs):
    return {"api_key": TMDB_API_KEY, **kwargs}


def search_media(query: str) -> list:
    results = []
    try:
        for r in requests.get(f"{BASE_URL}/search/movie", params=_p(query=query), timeout=10).json().get("results", [])[:5]:
            # Fetch IMDB ID for better Plex matching
            imdb_id = None
            try:
                ext = requests.get(f"{BASE_URL}/movie/{r['id']}/external_ids", params=_p(), timeout=5).json()
                imdb_id = ext.get("imdb_id")
            except Exception:
                pass
            results.append({
                "id": r["id"],
                "title": r["title"],
                "year": (r.get("release_date") or "")[:4] or "Unknown",
                "poster_path": r.get("poster_path"),
                "rating": round(r.get("vote_average", 0), 1),
                "type": "movie",
                "imdb_id": imdb_id,
            })
    except Exception:
        pass
    try:
        for r in requests.get(f"{BASE_URL}/search/tv", params=_p(query=query), timeout=10).json().get("results", [])[:5]:
            imdb_id = None
            try:
                ext = requests.get(f"{BASE_URL}/tv/{r['id']}/external_ids", params=_p(), timeout=5).json()
                imdb_id = ext.get("imdb_id")
            except Exception:
                pass
            results.append({
                "id": r["id"],
                "title": r["name"],
                "year": (r.get("first_air_date") or "")[:4] or "Unknown",
                "poster_path": r.get("poster_path"),
                "rating": round(r.get("vote_average", 0), 1),
                "type": "tv",
                "imdb_id": imdb_id,
            })
    except Exception:
        pass
    return results


def get_movie_details(tmdb_id: int, media_type: str = "movie") -> dict:
    """Fetch runtime and full details for a movie or TV show."""
    try:
        endpoint = "movie" if media_type == "movie" else "tv"
        data = requests.get(
            f"{BASE_URL}/{endpoint}/{tmdb_id}",
            params=_p(),
            timeout=10
        ).json()

        if media_type == "movie":
            runtime = data.get("runtime", 0) or 0
            runtime_str = f"{runtime}min" if runtime else "N/A"
        else:
            ep_runtime = data.get("episode_run_time", [])
            runtime_str = f"{ep_runtime[0]}min/ep" if ep_runtime else "N/A"

        return {
            "rating": round(data.get("vote_average", 0), 1),
            "runtime": runtime_str,
            "overview": data.get("overview", ""),
        }
    except Exception:
        return {"rating": "N/A", "runtime": "N/A", "overview": ""}


def get_trending(media_type: str = "movie") -> list:
    try:
        results = []
        for r in requests.get(f"{BASE_URL}/trending/{media_type}/week", params=_p(), timeout=10).json().get("results", [])[:10]:
            title = r.get("title") if media_type == "movie" else r.get("name", "")
            year_key = "release_date" if media_type == "movie" else "first_air_date"
            results.append({
                "id": r["id"],
                "title": title,
                "year": (r.get(year_key) or "")[:4] or "Unknown",
                "rating": round(r.get("vote_average", 0), 1),
                "poster_path": r.get("poster_path"),
                "type": media_type,
            })
        return results
    except Exception:
        return []
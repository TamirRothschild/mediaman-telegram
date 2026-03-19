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
            results.append({"id": r["id"], "title": r["title"], "year": (r.get("release_date") or "")[:4] or "Unknown", "poster_path": r.get("poster_path"), "type": "movie"})
    except Exception:
        pass
    try:
        for r in requests.get(f"{BASE_URL}/search/tv", params=_p(query=query), timeout=10).json().get("results", [])[:5]:
            results.append({"id": r["id"], "title": r["name"], "year": (r.get("first_air_date") or "")[:4] or "Unknown", "poster_path": r.get("poster_path"), "type": "tv"})
    except Exception:
        pass
    return results

def get_trending() -> list:
    try:
        results = []
        for r in requests.get(f"{BASE_URL}/trending/movie/week", params=_p(), timeout=10).json().get("results", [])[:10]:
            results.append({"id": r["id"], "title": r["title"], "year": (r.get("release_date") or "")[:4] or "Unknown", "rating": r.get("vote_average", "N/A"), "poster_path": r.get("poster_path"), "type": "movie"})
        return results
    except Exception:
        return []
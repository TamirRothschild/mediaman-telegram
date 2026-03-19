import os
import requests
from dotenv import load_dotenv

load_dotenv()

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"


def search_media(query):
    """
    Search TMDb for movies and TV shows matching the query.
    Returns a list of dicts: {id, title, year, poster_path, type}
    """
    results = []

    # movies
    try:
        resp = requests.get(
            f"{BASE_URL}/search/movie",
            params={"api_key": TMDB_API_KEY, "query": query},
            timeout=10,
        )
        movies = resp.json().get("results", [])
        for r in movies[:5]:
            results.append({
                "id": r["id"],
                "title": r["title"],
                "year": r.get("release_date", "")[:4] or "Unknown",
                "poster_path": r.get("poster_path"),
                "type": "movie",
            })
    except Exception:
        pass

    # tv shows
    try:
        resp = requests.get(
            f"{BASE_URL}/search/tv",
            params={"api_key": TMDB_API_KEY, "query": query},
            timeout=10,
        )
        shows = resp.json().get("results", [])
        for r in shows[:5]:
            results.append({
                "id": r["id"],
                "title": r["name"],
                "year": r.get("first_air_date", "")[:4] or "Unknown",
                "poster_path": r.get("poster_path"),
                "type": "tv",
            })
    except Exception:
        pass

    return results
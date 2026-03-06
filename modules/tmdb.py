import os
from tmdbv3api import TMDb, Search
from dotenv import load_dotenv

load_dotenv()

# אתחול TMDb
tmdb = TMDb()
tmdb.api_key = os.getenv("TMDB_API_KEY")

search = Search()

def search_media(query):
    """
    Search TMDb for movies and TV shows matching the query.
    Returns a list of dicts: {id, title, year, poster_path, type}
    """
    results = []

    # movies
    movies = list(search.movies(query))  # המרה ל-list
    for r in movies[:5]:
        results.append({
            "id": r.id,
            "title": r.title,
            "year": r.release_date[:4] if r.release_date else "Unknown",
            "poster_path": r.poster_path,
            "type": "movie"
        })

    # tv shows
    tv = list(search.tv_shows(query))  # המרה ל-list
    for r in tv[:5]:
        results.append({
            "id": r.id,
            "title": r.name,
            "year": r.first_air_date[:4] if r.first_air_date else "Unknown",
            "poster_path": r.poster_path,
            "type": "tv"
        })

    return results
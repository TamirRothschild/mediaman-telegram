import os
from dotenv import load_dotenv
from tmdbv3api import TMDb, Search


load_dotenv()

tmdb = TMDb()
tmdb.api_key = os.getenv("TMDB_API_KEY")

search = Search()

def search_media(query):

    results = []

    # movies
    movies = search.movies(query)

    for r in movies[:5]:
        results.append({
            "id": r.id,
            "title": r.title,
            "year": r.release_date[:4] if r.release_date else "Unknown",
            "poster_path": r.poster_path,
            "type": "movie"
        })

    # tv shows
    tv = search.tv_shows(query)

    for r in tv[:5]:
        results.append({
            "id": r.id,
            "title": r.name,
            "year": r.first_air_date[:4] if r.first_air_date else "Unknown",
            "poster_path": r.poster_path,
            "type": "tv"
        })

    return results
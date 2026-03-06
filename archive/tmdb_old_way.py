import os
from tmdbv3api import TMDb, Search

tmdb = TMDb()
tmdb.api_key = os.getenv("TMDB_API_KEY")

search = Search()


def search_movie(query):
    results = search.movies(query)

    movies = []
    for r in results[:5]:
        movies.append({
            "id": r.id,
            "title": r.title,
            "year": r.release_date[:4] if r.release_date else "Unknown",
            "poster_path": f"https://image.tmdb.org/t/p/w300{r.poster_path}" if r.poster_path else None,
            "type": "movie"
        })

    return movies


def search_tv(query):
    results = search.tv_shows(query)

    shows = []
    for r in results[:5]:
        shows.append({
            "id": r.id,
            "title": r.name,
            "year": r.first_air_date[:4] if r.first_air_date else "Unknown",
            "poster_path": f"https://image.tmdb.org/t/p/w300{r.poster_path}" if r.poster_path else None,
            "type": "tv"
        })

    return shows
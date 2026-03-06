import os
from tmdbv3api import TMDb, Search

# Load TMDb API key from environment
tmdb = TMDb()
tmdb.api_key = os.getenv("TMDB_API_KEY")

search = Search()

def search_movie(query):
    """
    Search TMDb for movies matching the query.
    Returns a list of dictionaries: {id, title, year, poster_path}
    """
    results = search.movies(query)
    movies = []
    for r in results:
        movie = {
            "id": r.id,
            "title": r.title,
            "year": r.release_date[:4] if r.release_date else "Unknown",
            "poster_path": f"https://image.tmdb.org/t/p/w200{r.poster_path}" if r.poster_path else None
        }
        movies.append(movie)
    return movies
import requests

YTS_API = "https://movies-api.accel.li/api/v2"


def search_yts(query: str) -> list:
    """
    Search YTS for movies by title.
    Returns a list of dicts: {id, title, year, rating, poster, torrents}
    """
    try:
        resp = requests.get(
            f"{YTS_API}/list_movies.json",
            params={"query_term": query, "limit": 8},
            timeout=10,
        )
        data = resp.json()

        if data.get("status") != "ok":
            return []

        movies = data.get("data", {}).get("movies") or []

        results = []
        for m in movies:
            torrents = [
                {
                    "quality": t["quality"],
                    "size": t["size"],
                    "magnet": _build_magnet(t["hash"], m["title_long"]),
                }
                for t in m.get("torrents", [])
            ]

            results.append(
                {
                    "id": m["id"],
                    "title": m["title"],
                    "year": m["year"],
                    "rating": m.get("rating", "N/A"),
                    "poster": m.get("medium_cover_image", ""),
                    "torrents": torrents,
                }
            )

        return results

    except Exception:
        return []


def _build_magnet(torrent_hash: str, title: str) -> str:
    trackers = [
        "udp://open.demonii.com:1337/announce",
        "udp://tracker.openbittorrent.com:80",
        "udp://tracker.coppersurfer.tk:6969",
        "udp://glotorrents.pw:6969/announce",
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://torrent.gresille.org:80/announce",
        "udp://p4p.arenabg.com:1337",
        "udp://tracker.leechers-paradise.org:6969",
    ]
    tracker_params = "&tr=".join(trackers)
    return f"magnet:?xt=urn:btih:{torrent_hash}&dn={title}&tr={tracker_params}"
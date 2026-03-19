import requests

YTS_API = "https://movies-api.accel.li/api/v2"

def search_yts(query: str) -> list:
    try:
        data = requests.get(f"{YTS_API}/list_movies.json", params={"query_term": query, "limit": 8}, timeout=10).json()
        if data.get("status") != "ok":
            return []
        results = []
        for m in (data.get("data", {}).get("movies") or []):
            torrents = [{"quality": t["quality"], "size": t["size"], "magnet": _magnet(t["hash"], m["title_long"])} for t in m.get("torrents", [])]
            results.append({"id": m["id"], "title": m["title"], "year": m["year"], "rating": m.get("rating", "N/A"), "runtime": m.get("runtime", 0), "poster": m.get("medium_cover_image", ""), "torrents": torrents})
        return results
    except Exception:
        return []

def _magnet(h, title):
    tr = "&tr=".join(["udp://open.demonii.com:1337/announce","udp://tracker.openbittorrent.com:80","udp://tracker.coppersurfer.tk:6969","udp://tracker.opentrackr.org:1337/announce","udp://p4p.arenabg.com:1337"])
    return f"magnet:?xt=urn:btih:{h}&dn={title}&tr={tr}"
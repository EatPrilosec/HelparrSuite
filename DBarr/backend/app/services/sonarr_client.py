from typing import Dict, Any, List, Optional
import httpx


class SonarrClient:
    @staticmethod
    async def test_connection(url: str, api_key: str) -> Dict[str, Any]:
        url = url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"

        headers = {"X-Api-Key": api_key}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{url}/api/v3/system/status", headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "message": f"Connected to Sonarr v{data.get('version', 'unknown')}",
                        "details": {"version": data.get("version"), "app_name": data.get("appName")}
                    }
                else:
                    return {
                        "success": False,
                        "message": f"Sonarr returned HTTP {response.status_code}: {response.text[:200]}"
                    }
            except Exception as e:
                return {"success": False, "message": f"Connection error: {str(e)}"}

    @staticmethod
    async def get_series(url: str, api_key: str) -> List[Dict[str, Any]]:
        url = url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"

        headers = {"X-Api-Key": api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{url}/api/v3/series", headers=headers)
            response.raise_for_status()
            series_list = response.json()
            
            parsed = []
            for s in series_list:
                # Extract poster url
                poster_url = None
                for img in s.get("images", []):
                    if img.get("coverType") == "poster":
                        remote_url = img.get("remoteUrl")
                        url_path = img.get("url")
                        poster_url = remote_url or (f"{url}{url_path}" if url_path else None)
                        break

                # Extract native language
                orig_lang = "English"
                lang_obj = s.get("originalLanguage")
                if isinstance(lang_obj, dict):
                    orig_lang = lang_obj.get("name", "English")
                elif isinstance(lang_obj, str) and lang_obj:
                    orig_lang = lang_obj

                # Count statistics
                stats = s.get("statistics", {})
                season_count = stats.get("seasonCount", len(s.get("seasons", [])))
                episode_count = stats.get("totalEpisodeCount", stats.get("episodeCount", 0))

                parsed.append({
                    "sonarr_series_id": s.get("id"),
                    "title": s.get("title"),
                    "sort_title": s.get("sortTitle"),
                    "clean_title": s.get("cleanTitle"),
                    "year": s.get("year"),
                    "status": s.get("status"),
                    "overview": s.get("overview"),
                    "poster_url": poster_url,
                    "original_language": orig_lang,
                    "season_count": season_count,
                    "episode_count": episode_count,
                    "monitored": s.get("monitored", True),
                    "tvdb_id": s.get("tvdbId"),
                    "tmdb_id": s.get("tmdbId"),
                    "imdb_id": s.get("imdbId"),
                    "path": s.get("path")
                })
            return parsed

    @staticmethod
    async def get_series_detail(url: str, api_key: str, series_id: int) -> Dict[str, Any]:
        url = url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"

        headers = {"X-Api-Key": api_key}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{url}/api/v3/series/{series_id}", headers=headers)
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def get_episodes(url: str, api_key: str, series_id: int) -> List[Dict[str, Any]]:
        url = url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"

        headers = {"X-Api-Key": api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{url}/api/v3/episode?seriesId={series_id}", headers=headers)
            response.raise_for_status()
            return response.json()

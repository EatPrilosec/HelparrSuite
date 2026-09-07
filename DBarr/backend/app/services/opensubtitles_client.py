from typing import Dict, Any, List, Optional
import httpx


class OpenSubtitlesClient:
    BASE_URL = "https://api.opensubtitles.com/api/v1"

    @staticmethod
    async def test_connection(api_key: str, user_agent: str = "DBarr v0.1") -> Dict[str, Any]:
        clean_key = (api_key or "").strip()
        if not clean_key:
            return {"success": False, "message": "OpenSubtitles API key is empty"}

        clean_ua = (user_agent or "").strip() or "DBarr v0.1"

        headers = {
            "Api-Key": clean_key,
            "User-Agent": clean_ua,
            "Accept": "application/json"
        }
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            try:
                # Query subtitles endpoint to validate Consumer Api-Key
                response = await client.get(
                    f"{OpenSubtitlesClient.BASE_URL}/subtitles",
                    headers=headers,
                    params={"query": "Matrix", "languages": "en"}
                )
                if response.status_code == 200:
                    data = response.json()
                    total = data.get("total_count", 0)
                    return {
                        "success": True,
                        "message": f"Connected to OpenSubtitles (API key validated, {total} results)",
                        "details": {"total_count": total}
                    }

                err_msg = f"HTTP {response.status_code}"
                try:
                    err_data = response.json()
                    if "message" in err_data:
                        err_msg = err_data["message"]
                    elif "errors" in err_data and isinstance(err_data["errors"], list):
                        err_msg = ", ".join(str(e) for e in err_data["errors"])
                except Exception:
                    pass

                if response.status_code in (401, 403):
                    return {"success": False, "message": f"OpenSubtitles API key invalid or unauthorized: {err_msg}"}
                else:
                    return {"success": False, "message": f"OpenSubtitles returned {err_msg}"}
            except Exception as e:
                return {"success": False, "message": f"OpenSubtitles connection error: {str(e)}"}

    @staticmethod
    async def search_subtitles(
        api_key: str,
        user_agent: str = "DBarr v0.1",
        imdb_id: Optional[str] = None,
        tmdb_id: Optional[int] = None,
        season_number: Optional[int] = None,
        episode_number: Optional[int] = None,
        languages: str = "en"
    ) -> List[Dict[str, Any]]:
        clean_key = (api_key or "").strip()
        if not clean_key:
            return []

        headers = {
            "Api-Key": clean_key,
            "User-Agent": (user_agent or "").strip() or "DBarr v0.1",
            "Accept": "application/json"
        }
        params = {"languages": languages}
        if imdb_id:
            clean_imdb = imdb_id.replace("tt", "")
            if clean_imdb.isdigit():
                params["imdb_id"] = clean_imdb
        if tmdb_id:
            params["tmdb_id"] = str(tmdb_id)
        if season_number is not None:
            params["season_number"] = str(season_number)
        if episode_number is not None:
            params["episode_number"] = str(episode_number)

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                response = await client.get(f"{OpenSubtitlesClient.BASE_URL}/subtitles", headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
            except Exception:
                pass
        return []

    @staticmethod
    async def download_subtitle_file(
        api_key: str,
        file_id: int,
        user_agent: str = "DBarr v0.1"
    ) -> Optional[str]:
        clean_key = (api_key or "").strip()
        if not clean_key:
            return None

        headers = {
            "Api-Key": clean_key,
            "User-Agent": (user_agent or "").strip() or "DBarr v0.1",
            "Accept": "application/json"
        }
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            try:
                # 1. Request temporary download link
                dl_res = await client.post(
                    f"{OpenSubtitlesClient.BASE_URL}/download",
                    headers=headers,
                    json={"file_id": file_id}
                )
                if dl_res.status_code == 200:
                    dl_data = dl_res.json()
                    link = dl_data.get("link")
                    if link:
                        content_res = await client.get(link)
                        if content_res.status_code == 200:
                            return content_res.text
            except Exception:
                pass
        return None

from typing import Dict, Any, List, Optional, Tuple
import logging
import httpx

logger = logging.getLogger(__name__)


class SubDLClient:
    BASE_URL = "https://api.subdl.com/api/v1"

    @staticmethod
    async def test_connection(api_key: str) -> Dict[str, Any]:
        if not api_key:
            return {"success": False, "message": "SubDL API key is empty"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{SubDLClient.BASE_URL}/me", params={"api_key": api_key})
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") is True or "data" in data or "email" in data:
                        return {"success": True, "message": "Connected to SubDL API successfully"}
                # Try subtitles search as fallback test
                test_res = await client.get(f"{SubDLClient.BASE_URL}/subtitles", params={"api_key": api_key, "film_name": "Breaking Bad"})
                if test_res.status_code == 200:
                    return {"success": True, "message": "Connected to SubDL API successfully"}
                return {"success": False, "message": f"SubDL API returned HTTP {response.status_code}"}
            except Exception as e:
                return {"success": False, "message": f"SubDL connection error: {str(e)}"}

    @staticmethod
    async def search_subtitles(
        api_key: str,
        imdb_id: Optional[str] = None,
        tmdb_id: Optional[int] = None,
        film_name: Optional[str] = None,
        season_number: Optional[int] = None,
        episode_number: Optional[int] = None,
        languages: str = "en"
    ) -> List[Dict[str, Any]]:
        clean_key = (api_key or "").strip()
        if not clean_key:
            return []

        attempts: List[Dict[str, Any]] = []

        # Attempt 1: imdb_id + season + episode
        if imdb_id:
            p1 = {"api_key": clean_key, "languages": languages, "imdb_id": imdb_id}
            if season_number is not None:
                p1["season_number"] = season_number
            if episode_number is not None:
                p1["episode_number"] = episode_number
            attempts.append(p1)

        # Attempt 2: film_name + season + episode
        if film_name:
            p2 = {"api_key": clean_key, "languages": languages, "film_name": film_name}
            if season_number is not None:
                p2["season_number"] = season_number
            if episode_number is not None:
                p2["episode_number"] = episode_number
            attempts.append(p2)

        # Attempt 3: tmdb_id + season + episode
        if tmdb_id:
            p3 = {"api_key": clean_key, "languages": languages, "tmdb_id": str(tmdb_id)}
            if season_number is not None:
                p3["season_number"] = season_number
            if episode_number is not None:
                p3["episode_number"] = episode_number
            attempts.append(p3)

        async with httpx.AsyncClient(timeout=15.0) as client:
            for params in attempts:
                try:
                    response = await client.get(f"{SubDLClient.BASE_URL}/subtitles", params=params)
                    if response.status_code == 200:
                        data = response.json()
                        subs = []
                        if data.get("status") is True and "subtitles" in data:
                            subs = data.get("subtitles", [])
                        elif "results" in data:
                            subs = data.get("results", [])
                        if subs:
                            return subs
                except Exception as e:
                    logger.debug(f"SubDL search error with params {params}: {e}")
        return []

    @staticmethod
    async def download_subtitle_content(url: str) -> Tuple[Optional[str], Optional[str]]:
        target_url = url.strip()
        if target_url.startswith("/"):
            target_url = f"https://dl.subdl.com{target_url}"

        async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
            try:
                response = await client.get(target_url)
                if response.status_code == 200:
                    raw_bytes = response.content
                    # SubDL commonly delivers ZIP archives containing .srt files
                    if raw_bytes.startswith(b"PK"):
                        import zipfile, io
                        try:
                            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                                srt_files = [f for f in zf.namelist() if f.lower().endswith((".srt", ".vtt", ".sub", ".txt"))]
                                if srt_files:
                                    return zf.read(srt_files[0]).decode("utf-8", errors="ignore"), None
                        except Exception as e:
                            logger.debug(f"SubDL zip extraction failed: {e}")
                    return response.text, None
                elif response.status_code == 429:
                    return None, "SubDL daily download quota reached (50/day limit)"
                else:
                    return None, f"SubDL download returned HTTP {response.status_code}"
            except Exception as e:
                return None, f"SubDL download connection error: {str(e)}"

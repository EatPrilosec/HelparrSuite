from typing import Dict, Any, List, Optional, Tuple
import logging
import httpx

logger = logging.getLogger(__name__)


class OpenSubtitlesClient:
    BASE_URL = "https://api.opensubtitles.com/api/v1"
    _cached_token: Optional[str] = None
    _token_expires_at: float = 0.0

    @staticmethod
    def _clean_id(val: Any) -> Optional[str]:
        if val is None:
            return None
        s = str(val).replace("tt", "").strip()
        return str(int(s)) if s.isdigit() else None

    @classmethod
    async def login(
        cls,
        api_key: str,
        username: str,
        password: str,
        user_agent: str = "DBarr v0.1"
    ) -> Dict[str, Any]:
        clean_key = (api_key or "").strip()
        clean_ua = (user_agent or "").strip() or "DBarr v0.1"
        if not clean_key or not username or not password:
            return {"success": False, "message": "API key, username, and password required"}

        headers = {
            "Api-Key": clean_key,
            "User-Agent": clean_ua,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            try:
                res = await client.post(
                    f"{cls.BASE_URL}/login",
                    headers=headers,
                    json={"username": username.strip(), "password": password.strip()}
                )
                if res.status_code == 200:
                    data = res.json()
                    token = data.get("token")
                    cls._cached_token = token
                    import time
                    cls._token_expires_at = time.time() + 43200  # 12 hours
                    user_info = data.get("user", {})
                    allowed = user_info.get("allowed_downloads", "unknown")
                    level = user_info.get("level", "User")
                    return {
                        "success": True,
                        "token": token,
                        "message": f"Logged in as {username} ({level}, {allowed} daily downloads)",
                        "details": user_info
                    }
                err_msg = f"HTTP {res.status_code}"
                try:
                    err_msg = res.json().get("message", err_msg)
                except Exception:
                    pass
                return {"success": False, "message": f"OpenSubtitles login failed: {err_msg}"}
            except Exception as e:
                return {"success": False, "message": f"OpenSubtitles login error: {str(e)}"}

    @classmethod
    async def get_token(
        cls,
        api_key: str,
        user_agent: str = "DBarr v0.1",
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Optional[str]:
        if not username or not password:
            return None
        import time
        if cls._cached_token and time.time() < cls._token_expires_at:
            return cls._cached_token
        res = await cls.login(api_key, username, password, user_agent)
        return res.get("token")

    @staticmethod
    async def test_connection(
        api_key: str,
        user_agent: str = "DBarr v0.1",
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Dict[str, Any]:
        clean_key = (api_key or "").strip()
        if not clean_key:
            return {"success": False, "message": "OpenSubtitles API key is empty"}

        clean_ua = (user_agent or "").strip() or "DBarr v0.1"
        headers = {
            "Api-Key": clean_key,
            "User-Agent": clean_ua,
            "Accept": "application/json"
        }

        # If user credentials are provided, test login first
        login_note = ""
        if username and password:
            login_res = await OpenSubtitlesClient.login(clean_key, username, password, clean_ua)
            if login_res.get("success"):
                login_note = f" - {login_res.get('message')}"
            else:
                return login_res

        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            try:
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
                        "message": f"Connected to OpenSubtitles (API key validated, {total} results){login_note}",
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

    @classmethod
    async def search_subtitles(
        cls,
        api_key: str,
        user_agent: str = "DBarr v0.1",
        parent_imdb_id: Optional[str] = None,
        parent_tmdb_id: Optional[int] = None,
        imdb_id: Optional[str] = None,
        tmdb_id: Optional[int] = None,
        query: Optional[str] = None,
        season_number: Optional[int] = None,
        episode_number: Optional[int] = None,
        languages: str = "en",
        token: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        clean_key = (api_key or "").strip()
        if not clean_key:
            return []

        clean_ua = (user_agent or "").strip() or "DBarr v0.1"
        headers = {
            "Api-Key": clean_key,
            "User-Agent": clean_ua,
            "Accept": "application/json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        clean_parent_imdb = cls._clean_id(parent_imdb_id or imdb_id)
        clean_parent_tmdb = str(parent_tmdb_id or tmdb_id) if (parent_tmdb_id or tmdb_id) else None

        # Build prioritized search attempts
        search_attempts: List[Dict[str, str]] = []

        # Attempt 1: parent_imdb_id + season + episode + requested language
        if clean_parent_imdb:
            p = {"parent_imdb_id": clean_parent_imdb, "languages": languages}
            if season_number is not None:
                p["season_number"] = str(season_number)
            if episode_number is not None:
                p["episode_number"] = str(episode_number)
            search_attempts.append(p)

        # Attempt 2: parent_tmdb_id + season + episode + requested language
        if clean_parent_tmdb:
            p = {"parent_tmdb_id": clean_parent_tmdb, "languages": languages}
            if season_number is not None:
                p["season_number"] = str(season_number)
            if episode_number is not None:
                p["episode_number"] = str(episode_number)
            search_attempts.append(p)

        # Attempt 3: query text + season + episode + requested language
        if query:
            p = {"query": query.strip(), "languages": languages}
            if season_number is not None:
                p["season_number"] = str(season_number)
            if episode_number is not None:
                p["episode_number"] = str(episode_number)
            search_attempts.append(p)

        # Attempt 4: Language fallback to 'en' if initial search requested a different language
        if languages != "en":
            if clean_parent_imdb:
                p = {"parent_imdb_id": clean_parent_imdb, "languages": "en"}
                if season_number is not None:
                    p["season_number"] = str(season_number)
                if episode_number is not None:
                    p["episode_number"] = str(episode_number)
                search_attempts.append(p)
            elif query:
                p = {"query": query.strip(), "languages": "en"}
                if season_number is not None:
                    p["season_number"] = str(season_number)
                if episode_number is not None:
                    p["episode_number"] = str(episode_number)
                search_attempts.append(p)

        # Attempt 5: Search without language filter as last resort
        if clean_parent_imdb:
            p = {"parent_imdb_id": clean_parent_imdb}
            if season_number is not None:
                p["season_number"] = str(season_number)
            if episode_number is not None:
                p["episode_number"] = str(episode_number)
            search_attempts.append(p)
        elif query:
            p = {"query": query.strip()}
            if season_number is not None:
                p["season_number"] = str(season_number)
            if episode_number is not None:
                p["episode_number"] = str(episode_number)
            search_attempts.append(p)

        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            for params in search_attempts:
                try:
                    response = await client.get(
                        f"{cls.BASE_URL}/subtitles",
                        headers=headers,
                        params=params
                    )
                    if response.status_code == 200:
                        data = response.json()
                        subtitles = data.get("data", [])
                        if subtitles:
                            return subtitles
                except Exception as e:
                    logger.debug(f"OpenSubtitles attempt failed with params {params}: {e}")

        return []

    @classmethod
    async def download_subtitle_file(
        cls,
        api_key: str,
        file_id: int,
        user_agent: str = "DBarr v0.1",
        token: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Downloads the subtitle content by file_id.
        Returns (content, error_message). If successful, content is str and error_message is None.
        If failed, content is None and error_message describes the cause (e.g. quota limit).
        """
        clean_key = (api_key or "").strip()
        if not clean_key:
            return None, "OpenSubtitles API key is empty"

        clean_ua = (user_agent or "").strip() or "DBarr v0.1"
        headers = {
            "Api-Key": clean_key,
            "User-Agent": clean_ua,
            "Accept": "application/json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            try:
                # 1. Request temporary download link
                dl_res = await client.post(
                    f"{cls.BASE_URL}/download",
                    headers=headers,
                    json={"file_id": file_id}
                )
                if dl_res.status_code == 200:
                    dl_data = dl_res.json()
                    link = dl_data.get("link")
                    if link:
                        content_res = await client.get(link)
                        if content_res.status_code == 200:
                            return content_res.text, None
                        return None, f"Failed to retrieve file from download link (HTTP {content_res.status_code})"
                    return None, "OpenSubtitles returned no download link"

                if dl_res.status_code == 406:
                    data = dl_res.json()
                    msg = data.get("message", "24h download quota reached")
                    reset_time = data.get("reset_time", "")
                    quota_msg = f"OpenSubtitles daily download quota reached ({msg.strip()})"
                    if reset_time:
                        quota_msg += f" (resets in {reset_time})"
                    return None, quota_msg

                if dl_res.status_code == 429:
                    return None, "OpenSubtitles rate limit exceeded (HTTP 429)"

                err_msg = f"OpenSubtitles download failed with HTTP {dl_res.status_code}"
                try:
                    data = dl_res.json()
                    if "message" in data:
                        err_msg = f"OpenSubtitles download failed: {data['message']}"
                except Exception:
                    pass
                return None, err_msg
            except Exception as e:
                return None, f"OpenSubtitles connection error during download: {str(e)}"

import json
import re
from typing import Dict, Any, List, Optional
import httpx


def clean_llm_text(content: str) -> str:
    """Strips thinking tags <think>...</think> and normalizes text."""
    if not content:
        return ""
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
    return cleaned


def extract_json_from_llm(content: str) -> Any:
    if not content:
        raise ValueError("Empty LLM response content")

    cleaned = clean_llm_text(content)

    # 1. Direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 2. Markdown json code fence
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    # 3. Outer braces { ... }
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace:last_brace + 1])
        except Exception:
            pass

    # 4. Outer brackets [ ... ]
    first_bracket = cleaned.find("[")
    last_bracket = cleaned.rfind("]")
    if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
        try:
            return json.loads(cleaned[first_bracket:last_bracket + 1])
        except Exception:
            pass

    raise ValueError(f"Could not parse valid JSON from LLM response: {cleaned[:200]}")


class OllamaClient:
    @staticmethod
    async def test_connection(base_url: str) -> Dict[str, Any]:
        url = base_url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    return {
                        "success": True,
                        "message": f"Connected to Ollama ({len(models)} models available)",
                        "available_models": models,
                        "details": {"model_count": len(models)}
                    }
                else:
                    return {"success": False, "message": f"Ollama returned HTTP status {response.status_code}"}
            except Exception as e:
                return {"success": False, "message": f"Cannot connect to Ollama at {url}: {str(e)}"}

    @staticmethod
    async def list_models(base_url: str) -> List[str]:
        url = base_url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{url}/api/tags")
                if response.status_code == 200:
                    return [m.get("name") for m in response.json().get("models", [])]
            except Exception:
                pass
        return []

    @staticmethod
    async def query_model_text(
        base_url: str,
        model: str,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        timeout: float = 60.0
    ) -> str:
        url = base_url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": user_prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return clean_llm_text(data.get("response", ""))

    @staticmethod
    async def query_model_json(
        base_url: str,
        model: str,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        timeout: float = 60.0
    ) -> Any:
        url = base_url.rstrip("/")
        if not url.startswith("http"):
            url = f"http://{url}"

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": user_prompt,
            "stream": False,
            "format": "json"
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            raw_text = data.get("response", "")
            return extract_json_from_llm(raw_text)

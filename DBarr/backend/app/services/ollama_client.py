import json
import logging
import re
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

SAFETY_REFUSAL_INDICATORS = [
    "i cannot fulfill",
    "i am unable to fulfill",
    "i cannot assist",
    "i'm unable to assist",
    "against my safety",
    "violates content policy",
    "violates safety guidelines",
    "as an ai assistant, i cannot",
    "as a helpful and harmless assistant",
    "i apologize, but i cannot",
    "i am sorry, but i cannot",
    "i cannot generate content that",
    "i cannot process explicit",
    "harmful or dangerous",
    "refuse to assist",
]


def clean_llm_text(content: str) -> str:
    """Strips thinking tags <think>...</think> and normalizes text."""
    if not content:
        return ""
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
    return cleaned


def is_safety_refusal(text: str) -> bool:
    if not text:
        return True
    lowered = text.lower()
    return any(ind in lowered for ind in SAFETY_REFUSAL_INDICATORS)


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
        timeout: float = 120.0,
        options: Optional[Dict[str, Any]] = None,
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
        payload["options"] = options or {"temperature": 0.1, "num_predict": 384}

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{url}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            raw_text = data.get("response", "")
            return extract_json_from_llm(raw_text)

    @staticmethod
    async def query_with_fallback_text(
        base_url: str,
        primary_model: str,
        fallback_models: List[str],
        user_prompt: str,
        system_prompt: Optional[str] = None,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        models_to_try = [primary_model] + [m for m in fallback_models if m and m != primary_model]
        last_error = None

        for model in models_to_try:
            try:
                text = await OllamaClient.query_model_text(
                    base_url=base_url,
                    model=model,
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    timeout=timeout,
                )
                if is_safety_refusal(text):
                    logger.warning(f"Model {model} triggered safety refusal/block. Falling back to next model...")
                    last_error = f"Safety block on {model}"
                    continue
                return {"success": True, "text": text, "model_used": model}
            except Exception as e:
                err_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
                logger.warning(f"Model {model} failed: {err_msg}. Falling back to next model...")
                last_error = err_msg
                continue

        raise RuntimeError(f"All Ollama models ({models_to_try}) failed or triggered safety blocks. Last error: {last_error}")

    @staticmethod
    async def query_with_fallback_json(
        base_url: str,
        primary_model: str,
        fallback_models: List[str],
        user_prompt: str,
        system_prompt: Optional[str] = None,
        timeout: float = 120.0,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        models_to_try = [primary_model] + [m for m in fallback_models if m and m != primary_model]
        last_error = None

        for model in models_to_try:
            try:
                parsed = await OllamaClient.query_model_json(
                    base_url=base_url,
                    model=model,
                    user_prompt=user_prompt + "\n\nCRITICAL: Reply ONLY with valid JSON conforming to the requested schema.",
                    system_prompt=system_prompt,
                    timeout=timeout,
                    options=options,
                )
                return {"success": True, "data": parsed, "model_used": model}
            except Exception as e:
                err_msg = f"{type(e).__name__}: {str(e)}" if str(e) else type(e).__name__
                logger.warning(f"Model {model} failed in JSON query: {err_msg}. Falling back...")
                last_error = err_msg
                continue

        raise RuntimeError(f"All Ollama models ({models_to_try}) failed or triggered safety blocks. Last error: {last_error}")

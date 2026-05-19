import os
import httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:e4b")


class OllamaError(Exception):
    pass


def generate(
    prompt: str,
    system: str | None = None,
    json_mode: bool = False,
    timeout: float = 300.0,
) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }
    if system:
        payload["system"] = system
    if json_mode:
        payload["format"] = "json"

    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=timeout,
        )
    except httpx.TimeoutException:
        raise OllamaError("Model timed out after 300s")
    except httpx.RequestError as e:
        raise OllamaError(f"Cannot reach Ollama: {e}")

    if resp.status_code != 200:
        raise OllamaError(f"Ollama returned {resp.status_code}: {resp.text}")

    return resp.json().get("response", "")

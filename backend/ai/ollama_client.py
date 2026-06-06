import os
import re
import time
import logging
import httpx

logger = logging.getLogger("smartdqc.ollama")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "hf.co/mradermacher/gemma-4-E4B-GGUF:Q6_K")
# Keep the model resident in memory between requests so the first click after
# an idle period doesn't pay a cold model-load (the root cause of the post-idle
# "failed to generate narrative" 500). "-1" = keep loaded indefinitely; can be
# overridden with a duration like "30m".
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
# Thinking ("reasoning") models like Qwen3 route their answer into a separate
# `thinking` field and leave `response` empty — especially with format="json" —
# which surfaced as "AI insight generation returned no output". Set
# OLLAMA_THINK=false to send `think: false` so the model writes its answer
# straight to `response`. Left model-agnostic: non-thinking models ignore it.
OLLAMA_THINK = os.getenv("OLLAMA_THINK", "true").strip().lower() != "false"
# How long warmup may spend waiting for Ollama + pulling the model on boot.
OLLAMA_PULL_TIMEOUT = float(os.getenv("OLLAMA_PULL_TIMEOUT", "1800"))


class OllamaError(Exception):
    pass


def _post(payload: dict, timeout: float) -> httpx.Response:
    return httpx.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=timeout,
    )


def _wait_until_up(timeout: float = 120.0) -> bool:
    """Poll /api/tags until the Ollama server answers (it boots alongside us)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(3)
    return False


def is_model_available() -> bool:
    """True if OLLAMA_MODEL (or its base tag) is already pulled."""
    try:
        r = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10.0)
        if r.status_code == 200:
            have = {m.get("name", "") for m in r.json().get("models", [])}
            base = OLLAMA_MODEL.split(":")[0]
            return any(n == OLLAMA_MODEL or n.split(":")[0] == base for n in have)
    except httpx.HTTPError:
        pass
    return False


def pull_model(timeout: float | None = None) -> bool:
    """Pull OLLAMA_MODEL into Ollama. Idempotent (no-op if already present) and
    safe to call while the entrypoint is pulling the same model — Ollama dedups
    concurrent pulls. Streamed so the long download doesn't look idle.

    Best-effort: returns True on success, False otherwise; never raises.
    """
    timeout = OLLAMA_PULL_TIMEOUT if timeout is None else timeout
    logger.info(
        "Ollama: pulling model '%s' (this can take a few minutes)…", OLLAMA_MODEL
    )
    try:
        with httpx.stream(
            "POST",
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": OLLAMA_MODEL},
            timeout=timeout,
        ) as resp:
            if resp.status_code != 200:
                logger.warning(
                    "Ollama pull returned %s: %s", resp.status_code, resp.read()[:200]
                )
                return False
            for _ in resp.iter_lines():
                pass  # drain progress stream until the pull completes
    except httpx.HTTPError as e:
        logger.warning("Ollama pull failed: %s", e)
        return False
    logger.info("Ollama: model '%s' pulled.", OLLAMA_MODEL)
    return True


def warmup(timeout: float = 120.0) -> bool:
    """Ensure the model is pulled and resident before the first real request.

    Runs at startup (in a background thread). The standalone image starts the
    API before the background model pull finishes, so we wait for Ollama, pull
    the model if it isn't there yet (the 404 "model not found" case), then send
    a 1-token generate to load it into memory.

    Best-effort: returns True on success, False otherwise; never raises.
    """
    if not _wait_until_up():
        logger.warning("Ollama did not become reachable; skipping warmup.")
        return False

    if not is_model_available():
        pull_model()

    try:
        resp = _post(
            {
                "model": OLLAMA_MODEL,
                "prompt": "ok",
                "stream": False,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {"num_predict": 1},
            },
            timeout=timeout,
        )
        if resp.status_code == 200:
            logger.info("Ollama model '%s' warmed up.", OLLAMA_MODEL)
            return True
        # Model still missing (e.g. tag just changed) — pull once and retry.
        if resp.status_code == 404 and pull_model():
            resp = _post(
                {
                    "model": OLLAMA_MODEL,
                    "prompt": "ok",
                    "stream": False,
                    "keep_alive": OLLAMA_KEEP_ALIVE,
                    "options": {"num_predict": 1},
                },
                timeout=timeout,
            )
            if resp.status_code == 200:
                logger.info("Ollama model '%s' warmed up after pull.", OLLAMA_MODEL)
                return True
        logger.warning(
            "Ollama warmup returned %s: %s", resp.status_code, resp.text[:200]
        )
    except httpx.HTTPError as e:
        logger.warning("Ollama warmup failed (model may load on first request): %s", e)
    return False


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
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }
    if system:
        payload["system"] = system
    if json_mode:
        payload["format"] = "json"
    if not OLLAMA_THINK:
        # Disable reasoning so the answer lands in `response`, not `thinking`.
        payload["think"] = False

    # Retry once on a transient connection/timeout blip (the model loading
    # within the 300s window succeeds on the first call; this only covers a
    # dropped connection). A genuine 404 "model not found" is surfaced as an
    # OllamaError so the caller can return a friendly "model still downloading"
    # message instead of hanging the request on a multi-minute pull.
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            resp = _post(payload, timeout=timeout)
        except httpx.TimeoutException:
            last_err = OllamaError("Model timed out after 300s")
        except httpx.RequestError as e:
            last_err = OllamaError(f"Cannot reach Ollama: {e}")
        else:
            if resp.status_code == 200:
                data = resp.json()
                raw = re.sub(
                    r"<think>.*?</think>", "",
                    data.get("response", "") or "", flags=re.DOTALL,
                ).strip()
                # Thinking models may still leak the answer into `thinking`
                # (e.g. format="json" with reasoning on). Salvage it so the
                # caller gets content instead of an empty-output fallback.
                if not raw:
                    thinking = (data.get("thinking") or "").strip()
                    if thinking:
                        logger.warning(
                            "Ollama '%s' returned empty response with %d chars of "
                            "thinking; using thinking content. Set OLLAMA_THINK=false "
                            "to disable reasoning.", OLLAMA_MODEL, len(thinking),
                        )
                        raw = thinking
                return raw
            if resp.status_code == 404:
                raise OllamaError(
                    f"Model '{OLLAMA_MODEL}' is not available yet — it may still "
                    f"be downloading. Try again shortly."
                )
            last_err = OllamaError(f"Ollama returned {resp.status_code}: {resp.text}")

        if attempt == 1:
            logger.warning(
                "Ollama generate attempt 1 failed (%s); retrying once.", last_err
            )

    raise last_err  # type: ignore[misc]

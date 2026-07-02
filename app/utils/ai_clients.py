"""
ai_clients.py — Lightweight Groq / Gemini cascade for BloodLink.

Priority:  Groq (llama-3.1-8b-instant)  →  Gemini (gemini-2.5-flash-lite)  →  baseline
Both clients mark themselves unavailable on quota / rate-limit errors so the
cascade falls through gracefully without retrying exhausted services.
"""

import logging
import os
import time

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Groq client
# ---------------------------------------------------------------------------

class GroqClient:
    """Thin wrapper around the official groq SDK."""

    MODEL = "llama-3.1-8b-instant"

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY", "").strip()
        self.available = False
        if not api_key:
            logger.warning("[AI] GROQ_API_KEY not set — Groq disabled.")
            return
        try:
            from groq import Groq  # type: ignore
            self._client = Groq(api_key=api_key)
            self.available = True
            logger.info("[AI] Groq client initialised (%s).", self.MODEL)
        except ImportError:
            logger.warning("[AI] groq package not installed — Groq disabled.")
        except Exception as exc:
            logger.warning("[AI] Groq init failed: %s", exc)

    def generate(self, prompt: str, max_tokens: int = 300, temperature: float = 0.4) -> str | None:
        if not self.available:
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as exc:
            msg = str(exc).lower()
            if any(tok in msg for tok in ("429", "rate", "quota", "limit")):
                self.available = False
                logger.warning("[AI] Groq quota/rate-limit hit — disabling for this run.")
            else:
                logger.error("[AI] Groq error: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

class GeminiClient:
    """Thin wrapper around google-generativeai SDK."""

    MODEL = "gemini-2.5-flash-lite"

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.available = False
        if not api_key:
            logger.warning("[AI] GEMINI_API_KEY not set — Gemini disabled.")
            return
        try:
            from google import genai  # type: ignore
            self._client = genai.Client(api_key=api_key)
            self.available = True
            logger.info("[AI] Gemini client initialised (%s).", self.MODEL)
        except ImportError:
            logger.warning("[AI] google-genai package not installed — Gemini disabled.")
        except Exception as exc:
            logger.warning("[AI] Gemini init failed: %s", exc)

    def generate(self, prompt: str, max_tokens: int = 300, temperature: float = 0.4) -> str | None:
        if not self.available:
            return None
        try:
            resp = self._client.models.generate_content(
                model=self.MODEL,
                contents=prompt,
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            return resp.text.strip()
        except Exception as exc:
            msg = str(exc).lower()
            if any(tok in msg for tok in ("429", "rate", "quota", "limit", "resource_exhausted")):
                self.available = False
                logger.warning("[AI] Gemini quota/rate-limit hit — disabling for this run.")
            else:
                logger.error("[AI] Gemini error: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Cascade helper
# ---------------------------------------------------------------------------

class AICascade:
    """
    Try Groq first, fall back to Gemini, then return None so callers can
    apply their own baseline heuristic.
    """

    def __init__(self):
        self.groq = GroqClient()
        self.gemini = GeminiClient()

    def generate(self, prompt: str, max_tokens: int = 300, temperature: float = 0.4) -> str | None:
        import hashlib
        import json
        import os
        from flask import current_app

        # Fallback cache path if not in app context
        try:
            cache_dir = os.path.join(current_app.instance_path, "cache")
        except Exception:
            cache_dir = "instance/cache"

        try:
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "ai_cache.json")
        except Exception:
            cache_file = None

        prompt_hash = hashlib.md5(prompt.encode("utf-8")).hexdigest()
        cache_data = {}

        if cache_file and os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
            except Exception:
                pass

        if prompt_hash in cache_data:
            logger.debug("[AI] Cache hit.")
            return cache_data[prompt_hash]

        result = self.groq.generate(prompt, max_tokens=max_tokens, temperature=temperature)
        if result:
            logger.debug("[AI] Response from Groq.")
        else:
            result = self.gemini.generate(prompt, max_tokens=max_tokens, temperature=temperature)
            if result:
                logger.debug("[AI] Response from Gemini.")

        if result:
            if cache_file:
                cache_data[prompt_hash] = result
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(cache_data, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.error("Failed to write to AI cache: %s", e)
            return result

        logger.warning("[AI] Both Groq and Gemini unavailable — caller should use baseline.")
        return None


# Module-level singleton so we pay initialisation cost only once per worker.
_cascade: AICascade | None = None


def get_ai_cascade() -> AICascade:
    global _cascade
    if _cascade is None:
        _cascade = AICascade()
    return _cascade

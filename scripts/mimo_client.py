#!/usr/bin/env python3
"""
Minimal MiMo API client for the ICTAI project.

Reads credentials from environment variables:
  XIAOMI_MIMO_BASE_URL, XIAOMI_MIMO_API_KEY, MIMO_MODEL, MIMO_SLEEP_SECONDS

Features:
- OpenAI-compatible chat/completions
- Sleep between calls (default 0.5s)
- Retry with backoff on 429/rate-limit
- Token usage logging
- Never prints API keys
"""

import os
import time
import json
import logging
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("Install openai: uv pip install openai")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; env vars can be set externally

logger = logging.getLogger("mimo_client")


def get_client() -> "OpenAI":
    """Create an OpenAI client configured for MiMo."""
    base_url = os.environ.get("XIAOMI_MIMO_BASE_URL")
    api_key = os.environ.get("XIAOMI_MIMO_API_KEY")
    if not base_url or not api_key:
        raise RuntimeError(
            "Set XIAOMI_MIMO_BASE_URL and XIAOMI_MIMO_API_KEY in .env or environment"
        )
    return OpenAI(base_url=base_url, api_key=api_key)


def get_model() -> str:
    return os.environ.get("MIMO_MODEL", "mimo-v2.5-pro")


def get_sleep_seconds() -> float:
    return float(os.environ.get("MIMO_SLEEP_SECONDS", "0.5"))


def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    max_retries: int = 5,
    sleep_seconds: Optional[float] = None,
) -> dict:
    """
    Call MiMo chat/completions with retry and rate-limit handling.

    Returns dict with keys: content, usage, model, finish_reason
    """
    client = get_client()
    model = model or get_model()
    sleep_sec = sleep_seconds if sleep_seconds is not None else get_sleep_seconds()

    for attempt in range(max_retries):
        try:
            t0 = time.time()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            elapsed = time.time() - t0

            choice = response.choices[0]
            usage = response.usage

            result = {
                "content": choice.message.content,
                "finish_reason": choice.finish_reason,
                "model": response.model,
                "input_tokens": usage.prompt_tokens if usage else None,
                "output_tokens": usage.completion_tokens if usage else None,
                "total_tokens": usage.total_tokens if usage else None,
                "elapsed_seconds": round(elapsed, 2),
            }

            logger.info(
                "MiMo call: model=%s in=%s out=%s elapsed=%.1fs",
                result["model"],
                result["input_tokens"],
                result["output_tokens"],
                elapsed,
            )

            # Sleep after successful call
            time.sleep(sleep_sec)
            return result

        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = "429" in err_str or "rate" in err_str or "limit" in err_str
            if is_rate_limit:
                wait = min(2 ** attempt * 2, 60)
                logger.warning("Rate limited (attempt %d/%d), waiting %ds: %s",
                               attempt + 1, max_retries, wait, e)
                time.sleep(wait)
                continue
            elif attempt < max_retries - 1:
                wait = min(2 ** attempt, 30)
                logger.warning("API error (attempt %d/%d), waiting %ds: %s",
                               attempt + 1, max_retries, wait, e)
                time.sleep(wait)
                continue
            else:
                raise

    raise RuntimeError(f"Failed after {max_retries} attempts")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("MiMo client loaded. Use chat_completion() for API calls.")
    print(f"Model: {get_model()}")
    print(f"Base URL: {os.environ.get('XIAOMI_MIMO_BASE_URL', 'NOT SET')}")
    print(f"Sleep: {get_sleep_seconds()}s")

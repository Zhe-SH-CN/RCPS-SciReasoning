#!/usr/bin/env python3
"""
OpenAI-compatible client for cross-model experiments.

Supports SJTU ZhiYuan provider. Reads credentials from environment variables.
Never prints API keys.

Usage:
  # Chat completion
  python scripts/22_openai_compatible_client.py chat --provider sjtu --prompt "Hello"

  # List models
  python scripts/22_openai_compatible_client.py models --provider sjtu

Environment variables:
  SJTU_API_KEY        - API key (required)
  SJTU_BASE_URL       - Base URL (default: https://models.sjtu.edu.cn/api/v1)
  SJTU_MODEL_ID       - Model ID (required for chat)
  SJTU_SLEEP_SECONDS  - Sleep between calls (default: 0.5)
"""

import os
import sys
import time
import json
import argparse
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("Install openai: uv pip install openai")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("openai_compatible_client")

CALL_TIMEOUT = 300  # seconds per API call


def get_sjtu_client() -> "OpenAI":
    """Create an OpenAI client configured for SJTU ZhiYuan."""
    api_key = os.environ.get("SJTU_API_KEY")
    base_url = os.environ.get("SJTU_BASE_URL", "https://models.sjtu.edu.cn/api/v1")

    if not api_key:
        raise RuntimeError("Set SJTU_API_KEY in .env or environment")

    return OpenAI(base_url=base_url, api_key=api_key, timeout=120.0)


def get_sjtu_model() -> str:
    """Get the SJTU model ID."""
    model = os.environ.get("SJTU_MODEL_ID")
    if not model:
        raise RuntimeError("Set SJTU_MODEL_ID in .env or environment")
    return model


def get_sleep_seconds() -> float:
    """Get sleep seconds between calls."""
    return float(os.environ.get("SJTU_SLEEP_SECONDS", "0.5"))


def list_models(provider: str = "sjtu") -> list[dict]:
    """List available models from the provider."""
    if provider == "sjtu":
        client = get_sjtu_client()
        response = client.models.list()
        models = []
        for model in response.data:
            models.append({
                "id": model.id,
                "object": model.object,
                "created": model.created,
                "owned_by": model.owned_by,
            })
        return models
    else:
        raise ValueError(f"Unknown provider: {provider}")


def chat_completion(
    messages: list[dict],
    model: Optional[str] = None,
    provider: str = "sjtu",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    max_retries: int = 5,
    sleep_seconds: Optional[float] = None,
) -> dict:
    """
    Call chat/completions with retry and rate-limit handling.

    Returns dict with keys: content, model, input_tokens, output_tokens, total_tokens, finish_reason, elapsed_seconds
    """
    if provider == "sjtu":
        client = get_sjtu_client()
        model = model or get_sjtu_model()
    else:
        raise ValueError(f"Unknown provider: {provider}")

    sleep_sec = sleep_seconds if sleep_seconds is not None else get_sleep_seconds()

    def _do_call():
        """Actual API call (runs in thread for timeout)."""
        return client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    for attempt in range(max_retries):
        try:
            t0 = time.time()
            # Use thread-based timeout to prevent hung connections
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_do_call)
                response = future.result(timeout=CALL_TIMEOUT)
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
                "API call: model=%s in=%s out=%s elapsed=%.1fs",
                result["model"],
                result["input_tokens"],
                result["output_tokens"],
                elapsed,
            )

            # Sleep after successful call
            time.sleep(sleep_sec)
            return result

        except (FuturesTimeout, TimeoutError) as e:
            logger.warning("API timeout (attempt %d/%d), waited %ds: %s",
                           attempt + 1, max_retries, CALL_TIMEOUT, e)
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise RuntimeError(f"API timed out after {max_retries} attempts")

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


def safe_model_slug(model_id: str) -> str:
    """Create a safe model slug for filenames."""
    return model_id.lower().replace("/", "-").replace("_", "-").replace(".", "")


def main():
    parser = argparse.ArgumentParser(description="OpenAI-compatible client for cross-model experiments")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Models command
    models_parser = subparsers.add_parser("models", help="List available models")
    models_parser.add_argument("--provider", default="sjtu", choices=["sjtu"], help="Provider")
    models_parser.add_argument("--output", help="Output JSON file")

    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Send a chat completion request")
    chat_parser.add_argument("--provider", default="sjtu", choices=["sjtu"], help="Provider")
    chat_parser.add_argument("--model", help="Model ID (overrides env)")
    chat_parser.add_argument("--prompt", required=True, help="User prompt")
    chat_parser.add_argument("--system", help="System prompt")
    chat_parser.add_argument("--temperature", type=float, default=0.7, help="Temperature")
    chat_parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens")
    chat_parser.add_argument("--sleep-seconds", type=float, help="Sleep between calls")

    # Info command
    info_parser = subparsers.add_parser("info", help="Show client configuration")
    info_parser.add_argument("--provider", default="sjtu", choices=["sjtu"], help="Provider")

    args = parser.parse_args()

    if args.command == "models":
        models = list_models(args.provider)
        print(f"Found {len(models)} models:")
        for m in models:
            print(f"  {m['id']}")

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump({"provider": args.provider, "models": models}, f, indent=2)
            print(f"Saved to {args.output}")

    elif args.command == "chat":
        messages = []
        if args.system:
            messages.append({"role": "system", "content": args.system})
        messages.append({"role": "user", "content": args.prompt})

        result = chat_completion(
            messages=messages,
            model=args.model,
            provider=args.provider,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            sleep_seconds=args.sleep_seconds,
        )

        print(f"Model: {result['model']}")
        print(f"Content: {result['content'][:500]}")
        print(f"Tokens: {result['input_tokens']}+{result['output_tokens']}={result['total_tokens']}")
        print(f"Finish reason: {result['finish_reason']}")
        print(f"Elapsed: {result['elapsed_seconds']}s")

    elif args.command == "info":
        if args.provider == "sjtu":
            base_url = os.environ.get("SJTU_BASE_URL", "https://models.sjtu.edu.cn/api/v1")
            model_id = os.environ.get("SJTU_MODEL_ID", "NOT SET")
            sleep_sec = os.environ.get("SJTU_SLEEP_SECONDS", "0.5")
            api_key_set = bool(os.environ.get("SJTU_API_KEY"))

            print(f"Provider: SJTU ZhiYuan")
            print(f"Base URL: {base_url}")
            print(f"Model ID: {model_id}")
            print(f"Sleep seconds: {sleep_sec}")
            print(f"API key set: {api_key_set}")
        else:
            print(f"Unknown provider: {args.provider}")

    else:
        parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

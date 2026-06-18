#!/usr/bin/env python3
"""
MiMo API smoke test.

Sends one minimal chat completion request and writes results to
results/setup/mimo_smoke_test.json.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from mimo_client import chat_completion, get_model, get_sleep_seconds


def main():
    output_dir = PROJECT_ROOT / "results" / "setup"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "mimo_smoke_test.json"

    print("MiMo Smoke Test")
    print("=" * 40)
    print(f"Model: {get_model()}")
    print(f"Sleep: {get_sleep_seconds()}s")
    print()

    messages = [
        {"role": "user", "content": "Say 'Hello, MiMo is working.' in exactly 5 words."}
    ]

    try:
        result = chat_completion(messages, temperature=0.0, max_tokens=50)
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "success",
            "model": result["model"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "total_tokens": result["total_tokens"],
            "elapsed_seconds": result["elapsed_seconds"],
            "response_preview": result["content"][:200],
            "finish_reason": result["finish_reason"],
        }
        print(f"SUCCESS: {result['content'][:100]}")
        print(f"Tokens: {result['input_tokens']} in / {result['output_tokens']} out")
        print(f"Time: {result['elapsed_seconds']}s")

    except Exception as e:
        report = {
            "timestamp": datetime.now().isoformat(),
            "status": "failed",
            "error": str(e)[:500],
        }
        print(f"FAILED: {e}")

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nResult saved to: {output_path}")
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())

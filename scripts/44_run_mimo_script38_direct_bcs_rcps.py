#!/usr/bin/env python3
"""Launch MiMo Direct/BCS/RCPS under the Script38 fixed cached-context route.

This is an execution wrapper only. It calls existing scripts 38/39/40 and does
not implement a new evaluator or scorer.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RESULT_DIR = ROOT / "results" / "experiments" / "20260617_script38_mimo_direct_bcs_rcps"
LOG_DIR = ROOT / "logs" / "20260617_script38_mimo_direct_bcs_rcps"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def redacted(cmd: list[str]) -> list[str]:
    safe = []
    skip_value = False
    for item in cmd:
        if skip_value:
            safe.append("<REDACTED>")
            skip_value = False
            continue
        safe.append(item)
        if item == "--api-key":
            skip_value = True
    return safe


TRANSIENT_PATTERNS = (
    "429",
    "rate limit",
    "rate_limit",
    "too many requests",
    "timeout",
    "timed out",
    "temporarily unavailable",
    "connection reset",
    "connection aborted",
)


def is_transient_failure(log_path: Path | None) -> bool:
    if log_path is None or not log_path.exists():
        return False
    text = log_path.read_text(errors="ignore").lower()
    return any(pattern in text for pattern in TRANSIENT_PATTERNS)


def run(cmd: list[str], log_path: Path | None = None, dry_run: bool = False) -> int:
    print("\n" + " ".join(redacted(cmd)))
    if dry_run:
        return 0
    if log_path is None:
        return subprocess.run(cmd, cwd=ROOT).returncode
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as log:
        log.write("\n" + "=" * 80 + "\n")
        log.write("COMMAND: " + " ".join(redacted(cmd)) + "\n")
        log.write("=" * 80 + "\n")
        log.flush()
        proc = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    print(f"log: {log_path}")
    return proc.returncode


def run_with_retry(
    method: str,
    cmd: list[str],
    log_path: Path,
    dry_run: bool,
    max_retries: int | None,
    retry_sleep_seconds: float,
) -> int:
    attempt = 0
    while True:
        if attempt:
            limit = "infinite" if max_retries is None else str(max_retries)
            print(
                f"{method}: retry {attempt}/{limit} after transient failure; "
                f"sleeping {retry_sleep_seconds:.1f}s before resume"
            )
            if not dry_run:
                time.sleep(retry_sleep_seconds)
        code = run(cmd, log_path, dry_run=dry_run)
        if code == 0:
            return 0
        if not is_transient_failure(log_path):
            return code
        if max_retries is not None and attempt >= max_retries:
            return code
        attempt += 1


def add_request_timeout(cmd: list[str], timeout: float | None) -> list[str]:
    if timeout is None:
        return cmd
    return cmd + ["--request-timeout", str(timeout)]


def run_job(
    method: str,
    out: Path,
    log: Path,
    cmd: list[str],
    model: str,
    dry_run: bool,
    max_retries: int | None,
    retry_sleep_seconds: float,
) -> tuple[str, int]:
    code = run_with_retry(
        method=method,
        cmd=cmd,
        log_path=log,
        dry_run=dry_run,
        max_retries=max_retries,
        retry_sleep_seconds=retry_sleep_seconds,
    )
    if code != 0:
        print(f"{method} failed with exit code {code}.")
        return method, code
    audit_cmd = [
        sys.executable, "scripts/40_audit_script38_outputs.py",
        str(out),
        "--log", str(log),
        "--expect-total", "77",
        "--expect-model", model,
        "--expect-method", method,
    ]
    if method != "direct":
        audit_cmd.insert(3, "--require-method-protocol")
    code = run(audit_cmd, dry_run=dry_run)
    if code != 0:
        print(f"{method} audit failed with exit code {code}.")
    return method, code


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MiMo Direct/BCS/RCPS with script38/39")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running API jobs")
    parser.add_argument("--skip-direct", action="store_true")
    parser.add_argument("--skip-bcs", action="store_true")
    parser.add_argument("--skip-rcps", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--request-timeout", type=float, default=None, help="Optional per-request HTTP timeout override; omitted by default")
    parser.add_argument("--max-retries", type=int, default=None, help="Transient retry cap; default is infinite")
    parser.add_argument("--retry-sleep-seconds", type=float, default=10.0)
    parser.add_argument("--sequential", action="store_true", help="Run jobs sequentially instead of in parallel")
    parser.add_argument("--num-candidates", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--anchor-slots", type=int, default=6)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")

    model = args.model or os.getenv("MIMO_MODEL") or os.getenv("XIAOMI_MIMO_MODEL") or "mimo-v2.5-pro"
    base_url = args.base_url or os.getenv("XIAOMI_MIMO_BASE_URL") or os.getenv("MIMO_BASE_URL")
    api_key = args.api_key or os.getenv("XIAOMI_MIMO_API_KEY") or os.getenv("MIMO_API_KEY")
    if not base_url:
        raise SystemExit("missing MiMo base URL: pass --base-url or set XIAOMI_MIMO_BASE_URL")
    if not api_key:
        raise SystemExit("missing MiMo API key: pass --api-key or set XIAOMI_MIMO_API_KEY")

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = "mimo_v25_pro"

    jobs = []
    if not args.skip_direct:
        out = RESULT_DIR / f"direct_{slug}_77t_{stamp}.json"
        log = LOG_DIR / f"direct_{slug}_77t_{stamp}.log"
        cmd = [
            sys.executable, "scripts/38_scireasoning_official_cache_exa.py",
            "--model", model,
            "--base-url", base_url,
            "--api-key", api_key,
            "--sleep-seconds", str(args.sleep_seconds),
            "--resume",
            "--output", str(out),
        ]
        jobs.append((
            "direct",
            out,
            log,
            add_request_timeout(cmd, args.request_timeout),
        ))
    if not args.skip_bcs:
        out = RESULT_DIR / f"bcs_{slug}_77t_{stamp}.json"
        log = LOG_DIR / f"bcs_{slug}_77t_{stamp}.log"
        cmd = [
            sys.executable, "scripts/39_scireasoning_official_cache_methods.py",
            "--method", "bcs",
            "--model", model,
            "--base-url", base_url,
            "--api-key", api_key,
            "--sleep-seconds", str(args.sleep_seconds),
            "--num-candidates", str(args.num_candidates),
            "--batch-size", str(args.batch_size),
            "--resume",
            "--output", str(out),
        ]
        jobs.append((
            "bcs",
            out,
            log,
            add_request_timeout(cmd, args.request_timeout),
        ))
    if not args.skip_rcps:
        out = RESULT_DIR / f"rcps_{slug}_77t_{stamp}.json"
        log = LOG_DIR / f"rcps_{slug}_77t_{stamp}.log"
        cmd = [
            sys.executable, "scripts/39_scireasoning_official_cache_methods.py",
            "--method", "rcps",
            "--model", model,
            "--base-url", base_url,
            "--api-key", api_key,
            "--sleep-seconds", str(args.sleep_seconds),
            "--num-candidates", str(args.num_candidates),
            "--batch-size", str(args.batch_size),
            "--anchor-slots", str(args.anchor_slots),
            "--resume",
            "--output", str(out),
        ]
        jobs.append((
            "rcps",
            out,
            log,
            add_request_timeout(cmd, args.request_timeout),
        ))

    print("\nMonitoring logs:")
    for method, _out, log, _cmd in jobs:
        print(f"  {method}: {log}")

    if args.sequential or len(jobs) <= 1:
        for method, out, log, cmd in jobs:
            _method, code = run_job(
                method, out, log, cmd, model, args.dry_run, args.max_retries, args.retry_sleep_seconds
            )
            if code != 0:
                print(f"{method} failed; stopping before later jobs.")
                return code
    else:
        failures = []
        with ThreadPoolExecutor(max_workers=len(jobs)) as executor:
            future_to_method = {
                executor.submit(
                    run_job,
                    method,
                    out,
                    log,
                    cmd,
                    model,
                    args.dry_run,
                    args.max_retries,
                    args.retry_sleep_seconds,
                ): method
                for method, out, log, cmd in jobs
            }
            for future in as_completed(future_to_method):
                method, code = future.result()
                if code != 0:
                    failures.append((method, code))
        if failures:
            print("Failures:")
            for method, code in failures:
                print(f"  {method}: exit code {code}")
            return 1

    print("MiMo Direct/BCS/RCPS execution completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

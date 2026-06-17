#!/usr/bin/env python3
"""
Single-entry executor for Plan/40_CLAUDE_SCRIPT38_GEMINI_METHODS.md.

This script does not implement scoring. It orchestrates scripts 38/39/40/41:
- no-API checks;
- Flash Direct full77 with audit;
- BCS/RCPS smoke with audit;
- full BCS/RCPS for completed Gemini Direct baselines.

It maps GEMINI_* environment variables to the OPENAI-compatible variables used
by scripts 38/39 without putting API keys on the command line.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

SCRIPT38 = ROOT / "scripts" / "38_scireasoning_official_cache_exa.py"
SCRIPT39 = ROOT / "scripts" / "39_scireasoning_official_cache_methods.py"
SCRIPT40 = ROOT / "scripts" / "40_audit_script38_outputs.py"
SCRIPT41 = ROOT / "scripts" / "41_static_audit_script38_methods.py"

DIRECT_DIR = ROOT / "results" / "experiments" / "20260616_script38_gemini_baselines"
DIRECT_LOG_DIR = ROOT / "logs" / "20260616_script38_gemini_baselines"
SMOKE_DIR = ROOT / "results" / "experiments" / "20260616_script38_methods_smoke"
SMOKE_LOG_DIR = ROOT / "logs" / "20260616_script38_methods_smoke"
FULL_DIR = ROOT / "results" / "experiments" / "20260616_script38_methods_full77"
FULL_LOG_DIR = ROOT / "logs" / "20260616_script38_methods_full77"

EXISTING_LOW_DIRECT = (
    ROOT / "results" / "experiments" / "20260616_script38_mimo_gemini_full77" / "gemini_cache_exa_77t.json"
)
EXISTING_LOW_DIRECT_LOG = (
    ROOT / "logs" / "20260616_script38_mimo_gemini_full77" / "gemini_cache_exa_77t.log"
)
EXISTING_PRO_DIRECT = (
    ROOT / "results" / "experiments" / "20260616_script38_mimo_gemini_full77" / "gemini_pro_agent_cache_exa_77t.json"
)
EXISTING_PRO_DIRECT_LOG = (
    ROOT / "logs" / "20260616_script38_mimo_gemini_full77" / "gemini_pro_agent_cache_exa_77t.log"
)
FLASH_DIRECT = DIRECT_DIR / "gemini_3_flash_agent_cache_exa_77t.json"
FLASH_DIRECT_LOG = DIRECT_LOG_DIR / "gemini_3_flash_agent_cache_exa_77t.log"
REPORT_PATH = FULL_DIR / "plan40_execution_report.json"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def model_names() -> dict[str, str]:
    return {
        "low": os.getenv("GEMINI_LOW_MODEL", "gemini-3.1-pro-low"),
        "pro_agent": os.getenv("GEMINI_PRO_AGENT_MODEL", "gemini-pro-agent"),
        "flash": os.getenv("GEMINI_FLASH_AGENT_MODEL", "gemini-3-flash-agent"),
    }


def child_env(require_key: bool) -> dict[str, str]:
    env = os.environ.copy()
    api_key = env.get("GEMINI_API_KEY") or env.get("OPENAI_API_KEY") or ""
    base_url = env.get("GEMINI_BASE_URL") or env.get("OPENAI_BASE_URL") or ""
    if require_key and not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY or OPENAI_API_KEY")
    if require_key and not base_url:
        raise RuntimeError("Missing GEMINI_BASE_URL or OPENAI_BASE_URL")
    if api_key:
        env["OPENAI_API_KEY"] = api_key
    if base_url:
        env["OPENAI_BASE_URL"] = base_url
    return env


def ensure_dirs() -> None:
    for path in [DIRECT_DIR, DIRECT_LOG_DIR, SMOKE_DIR, SMOKE_LOG_DIR, FULL_DIR, FULL_LOG_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def display_cmd(cmd: list[str]) -> str:
    rel = []
    for item in cmd:
        try:
            rel.append(str(Path(item).relative_to(ROOT)))
        except (ValueError, TypeError):
            rel.append(item)
    return " ".join(rel)


def run(cmd: list[str], *, env: dict[str, str], log_path: Path | None = None, allow_fail: bool = False) -> int:
    print(f"\n$ {display_cmd(cmd)}")
    if log_path is None:
        completed = subprocess.run(cmd, cwd=ROOT, env=env)
    else:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w") as log:
            completed = subprocess.run(cmd, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        print(f"  log: {log_path.relative_to(ROOT)}")
    if completed.returncode != 0 and not allow_fail:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {display_cmd(cmd)}")
    return completed.returncode


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def complete_77(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = load_json(path)
    except Exception:
        return False
    return data.get("summary", {}).get("total_papers") == 77


def audit_direct(path: Path, log: Path, model: str, total: int) -> int:
    return run(
        [
            PYTHON,
            str(SCRIPT40),
            str(path),
            "--log",
            str(log),
            "--expect-total",
            str(total),
            "--expect-model",
            model,
            "--expect-method",
            "direct",
        ],
        env=child_env(require_key=False),
        allow_fail=True,
    )


def audit_method(path: Path, log: Path, model: str, method: str, total: int) -> int:
    return run(
        [
            PYTHON,
            str(SCRIPT40),
            str(path),
            "--log",
            str(log),
            "--require-method-protocol",
            "--expect-total",
            str(total),
            "--expect-model",
            model,
            "--expect-method",
            method,
        ],
        env=child_env(require_key=False),
        allow_fail=True,
    )


def audit_existing_directs(models: dict[str, str]) -> list[dict]:
    rows = []
    for slug, path, log, model in [
        ("gemini_low", EXISTING_LOW_DIRECT, EXISTING_LOW_DIRECT_LOG, models["low"]),
        ("gemini_pro_agent", EXISTING_PRO_DIRECT, EXISTING_PRO_DIRECT_LOG, models["pro_agent"]),
    ]:
        audit_rc = audit_direct(path, log, model, 77) if path.exists() else 1
        rows.append(
            {
                "stage": "existing_direct_audit",
                "model": model,
                "slug": slug,
                "path": str(path.relative_to(ROOT)),
                "log": str(log.relative_to(ROOT)),
                "audit_exit": audit_rc,
                "status": "pass" if audit_rc == 0 else "fail",
            }
        )
    return rows


def run_no_api_checks(models: dict[str, str]) -> list[dict]:
    env = child_env(require_key=False)
    rows = []
    compile_cmd = [
        PYTHON,
        "-m",
        "py_compile",
        str(SCRIPT38),
        str(SCRIPT39),
        str(SCRIPT40),
        str(SCRIPT41),
        str(Path(__file__).resolve()),
    ]
    run(compile_cmd, env=env)
    rows.append({"stage": "no_api", "name": "py_compile", "status": "pass"})

    run([PYTHON, str(SCRIPT41)], env=env)
    rows.append({"stage": "no_api", "name": "static_audit", "status": "pass"})

    base_url = os.getenv("GEMINI_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://example.invalid/v1"
    run(
        [
            PYTHON,
            str(SCRIPT38),
            "--dry-run",
            "--smoke",
            "1",
            "--model",
            models["flash"],
            "--base-url",
            base_url,
            "--request-timeout",
            "240",
        ],
        env=env,
    )
    rows.append({"stage": "no_api", "name": "flash_direct_dry_run", "status": "pass"})

    for method in ["bcs", "rcps"]:
        run(
            [
                PYTHON,
                str(SCRIPT39),
                "--method",
                method,
                "--dry-run",
                "--smoke",
                "3",
                "--model",
                models["low"],
                "--base-url",
                base_url,
            ],
            env=env,
        )
        rows.append({"stage": "no_api", "name": f"{method}_dry_run", "status": "pass"})
    return rows


def run_with_one_retry(cmd: list[str], *, env: dict[str, str], log_path: Path) -> int:
    first = run(cmd, env=env, log_path=log_path, allow_fail=True)
    if first == 0:
        return 0
    print("  first attempt failed; retrying once with the same --resume command")
    return run(cmd, env=env, log_path=log_path, allow_fail=True)


def run_flash_direct(models: dict[str, str]) -> dict:
    env = child_env(require_key=True)
    base_url = env["OPENAI_BASE_URL"]
    cmd = [
        PYTHON,
        str(SCRIPT38),
        "--model",
        models["flash"],
        "--base-url",
        base_url,
        "--sleep-seconds",
        "1",
        "--request-timeout",
        "240",
        "--resume",
        "--output",
        str(FLASH_DIRECT),
    ]
    rc = run_with_one_retry(cmd, env=env, log_path=FLASH_DIRECT_LOG)
    audit_rc = audit_direct(FLASH_DIRECT, FLASH_DIRECT_LOG, models["flash"], 77) if FLASH_DIRECT.exists() else 1
    return {
        "stage": "flash_direct",
        "path": str(FLASH_DIRECT.relative_to(ROOT)),
        "log": str(FLASH_DIRECT_LOG.relative_to(ROOT)),
        "command_exit": rc,
        "audit_exit": audit_rc,
        "complete_77": complete_77(FLASH_DIRECT),
        "status": "pass" if rc == 0 and audit_rc == 0 and complete_77(FLASH_DIRECT) else "fail",
    }


def run_method_smoke(models: dict[str, str]) -> list[dict]:
    env = child_env(require_key=True)
    base_url = env["OPENAI_BASE_URL"]
    rows = []
    for method, extra in [
        ("bcs", []),
        ("rcps", ["--anchor-slots", "6"]),
    ]:
        out = SMOKE_DIR / f"{method}_gemini_low_3t.json"
        log = SMOKE_LOG_DIR / f"{method}_gemini_low_3t.log"
        cmd = [
            PYTHON,
            str(SCRIPT39),
            "--method",
            method,
            "--smoke",
            "3",
            "--model",
            models["low"],
            "--base-url",
            base_url,
            "--sleep-seconds",
            "1",
            "--request-timeout",
            "240",
            "--num-candidates",
            "30",
            "--batch-size",
            "10",
            "--resume",
            "--output",
            str(out),
            *extra,
        ]
        rc = run_with_one_retry(cmd, env=env, log_path=log)
        audit_rc = audit_method(out, log, models["low"], method, 3) if out.exists() else 1
        rows.append(
            {
                "stage": "method_smoke",
                "method": method,
                "path": str(out.relative_to(ROOT)),
                "log": str(log.relative_to(ROOT)),
                "command_exit": rc,
                "audit_exit": audit_rc,
                "status": "pass" if rc == 0 and audit_rc == 0 else "fail",
            }
        )
    return rows


def method_models(models: dict[str, str], include_flash: bool) -> list[tuple[str, str]]:
    selected = [("gemini_low", models["low"]), ("gemini_pro_agent", models["pro_agent"])]
    if include_flash and complete_77(FLASH_DIRECT):
        selected.append(("gemini_3_flash_agent", models["flash"]))
    return selected


def run_full_methods_for_pairs(pairs: list[tuple[str, str]]) -> list[dict]:
    env = child_env(require_key=True)
    base_url = env["OPENAI_BASE_URL"]
    rows = []
    for slug, model in pairs:
        for method, extra in [
            ("bcs", []),
            ("rcps", ["--anchor-slots", "6"]),
        ]:
            out = FULL_DIR / f"{method}_{slug}_77t.json"
            log = FULL_LOG_DIR / f"{method}_{slug}_77t.log"
            cmd = [
                PYTHON,
                str(SCRIPT39),
                "--method",
                method,
                "--model",
                model,
                "--base-url",
                base_url,
                "--sleep-seconds",
                "1",
                "--request-timeout",
                "240",
                "--num-candidates",
                "30",
                "--batch-size",
                "10",
                "--resume",
                "--output",
                str(out),
                *extra,
            ]
            rc = run_with_one_retry(cmd, env=env, log_path=log)
            audit_rc = audit_method(out, log, model, method, 77) if out.exists() else 1
            rows.append(
                {
                    "stage": "method_full77",
                    "model": model,
                    "method": method,
                    "path": str(out.relative_to(ROOT)),
                    "log": str(log.relative_to(ROOT)),
                    "command_exit": rc,
                    "audit_exit": audit_rc,
                    "status": "pass" if rc == 0 and audit_rc == 0 else "fail",
                }
            )
    return rows


def run_full_methods(models: dict[str, str], *, include_flash: bool) -> list[dict]:
    return run_full_methods_for_pairs(method_models(models, include_flash=include_flash))


def run_parallel_long_jobs(models: dict[str, str]) -> list[dict]:
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            "flash_direct": executor.submit(run_flash_direct, models),
            "method_full77_existing": executor.submit(run_full_methods, models, include_flash=False),
        }
        for name, future in futures.items():
            try:
                result = future.result()
            except Exception as exc:
                rows.append({"stage": name, "status": "error", "error": str(exc)})
                continue
            if isinstance(result, list):
                rows.extend(result)
            else:
                rows.append(result)

    flash_ok = any(row.get("stage") == "flash_direct" and row.get("status") == "pass" for row in rows)
    existing_rows = [row for row in rows if row.get("stage") == "method_full77"]
    existing_errors = any(row.get("stage") == "method_full77_existing" for row in rows)
    existing_methods_ok = bool(existing_rows) and not existing_errors and all(
        row.get("status") == "pass" for row in existing_rows
    )
    if flash_ok and existing_methods_ok:
        rows.extend(run_full_methods_for_pairs([("gemini_3_flash_agent", models["flash"])]))
    return rows


def write_report(rows: list[dict]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    failed = [row for row in rows if row.get("status") not in {"pass", "skipped"}]
    completed_json = [
        row.get("path")
        for row in rows
        if row.get("status") == "pass"
        and row.get("path")
        and row.get("stage") in {"flash_direct", "method_smoke", "method_full77", "existing_direct_audit"}
    ]
    report = {
        "timestamp": datetime.now().isoformat(),
        "plan": "Plan/40_CLAUDE_SCRIPT38_GEMINI_METHODS.md",
        "summary": {
            "overall_status": "pass" if not failed else "fail",
            "row_count": len(rows),
            "failed_count": len(failed),
            "failed_stages": [row.get("stage", "unknown") for row in failed],
            "completed_json": completed_json,
            "codex_review_required": True,
        },
        "rows": rows,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2))
    print(f"\nExecution report: {REPORT_PATH.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Plan40 Gemini Script38/39 experiments")
    parser.add_argument("--dry-run-only", action="store_true", help="Run only no-API checks")
    parser.add_argument("--stop-after-smoke", action="store_true", help="Stop after BCS/RCPS smoke audits")
    parser.add_argument("--sequential", action="store_true", help="Run Flash Direct before full methods instead of parallel long jobs")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    ensure_dirs()
    models = model_names()

    rows: list[dict] = []
    rows.extend(run_no_api_checks(models))
    baseline_rows = audit_existing_directs(models)
    rows.extend(baseline_rows)
    if any(row["status"] != "pass" for row in baseline_rows):
        write_report(rows)
        return 1
    if args.dry_run_only:
        write_report(rows)
        return 0

    smoke_rows = run_method_smoke(models)
    rows.extend(smoke_rows)
    if any(row["status"] != "pass" for row in smoke_rows):
        write_report(rows)
        return 1
    if args.stop_after_smoke:
        write_report(rows)
        return 0

    if args.sequential:
        rows.append(run_flash_direct(models))
        rows.extend(run_full_methods(models, include_flash=True))
    else:
        rows.extend(run_parallel_long_jobs(models))
    write_report(rows)
    return 0 if all(row.get("status") == "pass" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())

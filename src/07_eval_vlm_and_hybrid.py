"""Exp-05B: Evaluate Pure VLM vs. Hybrid (Track-1 Vector/Rule + Track-2 VLM) on Benchmark v1.

Reads GEMINI_API_KEY from environment (or optional local .env file; never hardcoded).
Supports:
- Pure VLM baseline (image + caption + main_text_claim only)
- Hybrid Audit (Track-1 deterministic evidence + VLM visual/semantic verification)
- Automatic rate-limit throttling & per-case JSONL caching for safe resume.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
BENCH_DIR = BASE_DIR / "data" / "benchmark_v1"
RULE_REPORT = BASE_DIR / "data" / "benchmark_v1_rule_baseline.json"
CACHE_PATH = BASE_DIR / "data" / "vlm_eval_cache.jsonl"
OUT_PATH = BASE_DIR / "data" / "benchmark_v1_vlm_hybrid_results.json"

DEFAULT_MODEL = "gemini-3-flash-preview"


def load_api_key() -> str:
    """Load GEMINI_API_KEY from env or track3-ai4science/.env."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def call_gemini_vision(
    api_key: str,
    model: str,
    png_path: Path,
    prompt: str,
    max_retries: int = 6,
) -> dict[str, Any]:
    """Call Gemini generateContent REST API with an image + structured JSON output."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    img_b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/png", "data": img_b64}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=90,
            )
        except requests.exceptions.RequestException as exc:
            wait_s = 10 * (attempt + 1)
            print(f"  [network/timeout: {type(exc).__name__}] sleeping {wait_s}s...")
            time.sleep(wait_s)
            continue
        if resp.status_code in (429, 503):
            wait_s = 30 * (attempt + 1)
            print(f"  [{resp.status_code} transient] sleeping {wait_s}s...")
            time.sleep(wait_s)
            continue
        if not resp.ok:
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)

    raise RuntimeError("Exceeded max retries due to rate limiting / transient errors.")


def build_pure_vlm_prompt(meta: dict[str, Any]) -> str:
    return (
        "You are a scientific integrity auditor. Inspect the attached figure and compare it "
        "against the caption and main text claim below.\n"
        "Check for: (1) sample size n mismatch vs plotted points, (2) significance star vs p-value conflict, "
        "(3) truncated Y-axis on bar charts exaggerating differences, (4) missing error bar definition (SD/SEM/CI) "
        "or concealed distribution, (5) effect direction inversion between plot and text.\n\n"
        f"Caption: {meta['caption']}\n"
        f"Main text claim: {meta['main_text_claim']}\n\n"
        'Respond strictly in JSON: {"is_inconsistent": true/false, "reasons": ["..."]}'
    )


def build_hybrid_prompt(meta: dict[str, Any], track1_findings: list[str]) -> str:
    evidence_str = "\n".join(f"- {f}" for f in track1_findings) if track1_findings else "- None detected by vector/text rules."
    return (
        "You are a scientific integrity auditor combining automated PDF vector/text evidence with visual inspection.\n"
        "Deterministic Track-1 Findings:\n"
        f"{evidence_str}\n\n"
        "Now inspect the figure image and compare it with the text below. Pay special attention to:\n"
        "- Direction of comparison claims vs visual bar/box heights (even if Track-1 missed complex phrasing).\n"
        "- Visual Y-axis truncation or missing scatter points/error-bar definitions on rasterized figures.\n"
        "- Do NOT dismiss verified Track-1 conflicts unless clearly a false positive.\n\n"
        f"Caption: {meta['caption']}\n"
        f"Main text claim: {meta['main_text_claim']}\n\n"
        'Respond strictly in JSON: {"is_inconsistent": true/false, "reasons": ["..."]}'
    )


def load_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                cache[f"{rec['mode']}::{rec['case_id']}"] = rec
    return cache


def append_cache(cache_path: Path, rec: dict[str, Any]) -> None:
    with cache_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def compute_metrics(preds: list[tuple[bool, bool, str, bool]]) -> dict[str, Any]:
    """Compute metrics from list of (gt_inconsistent, pred_inconsistent, category, is_raster)."""
    tp = fp = tn = fn = 0
    by_cat: dict[str, list[bool]] = defaultdict(list)
    by_fmt: dict[str, list[bool]] = defaultdict(list)

    for gt, pred, cat, is_raster in preds:
        ok = gt == pred
        if gt and pred:
            tp += 1
        elif not gt and pred:
            fp += 1
        elif not gt and not pred:
            tn += 1
        else:
            fn += 1
        by_cat[cat].append(ok)
        by_fmt["raster_pdf" if is_raster else "vector_pdf"].append(ok)

    total = len(preds)
    acc = (tp + tn) / total if total else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {
        "total": total,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "by_category": {
            c: f"{sum(v)}/{len(v)} ({sum(v)/len(v)*100:.1f}%)" for c, v in sorted(by_cat.items())
        },
        "by_pdf_format": {
            k: f"{sum(v)}/{len(v)} ({sum(v)/len(v)*100:.1f}%)" for k, v in sorted(by_fmt.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--sleep", type=float, default=4.5, help="Seconds between API calls (free-tier safe)")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for quick test (0 = all 60)")
    parser.add_argument("--smoke", action="store_true", help="Run 1 sample per category (C0_00..C5_00)")
    parser.add_argument("--dry-run", action="store_true", help="Verify files and key presence without calling API")
    args = parser.parse_args()

    api_key = load_api_key()
    rule_data = json.loads(RULE_REPORT.read_text(encoding="utf-8"))
    rule_map = {r["case_id"]: r for r in rule_data["records"]}
    json_files = sorted(BENCH_DIR.glob("*.json"))
    if args.smoke:
        json_files = [p for p in json_files if p.stem.endswith("_00")]
    elif args.limit > 0:
        json_files = json_files[: args.limit]

    if args.dry_run:
        print(f"Dry run OK: {len(json_files)} cases ready. GEMINI_API_KEY set = {bool(api_key)}.")
        return

    if not api_key:
        raise SystemExit(
            "ERROR: GEMINI_API_KEY not found.\n"
            'Set it in PowerShell: $env:GEMINI_API_KEY="YOUR_KEY"\n'
            f"Or put GEMINI_API_KEY=... in {BASE_DIR / '.env'}"
        )

    safe_model = args.model.replace("/", "_")
    cache_path = BASE_DIR / "data" / f"vlm_eval_cache_{safe_model}.jsonl"
    cache = load_cache(cache_path)
    pure_preds, hybrid_preds = [], []

    for idx, jp in enumerate(json_files, 1):
        meta = json.loads(jp.read_text(encoding="utf-8"))
        cid = meta["case_id"]
        png_path = BENCH_DIR / meta["files"]["png"]
        gt_inc = not meta["is_consistent"]
        t1_findings = rule_map[cid]["findings"]

        # 1. Pure VLM
        k_pure = f"pure_vlm::{cid}"
        if k_pure not in cache:
            print(f"[{idx}/{len(json_files)}] Calling Pure VLM ({args.model}) on {cid}...")
            out = call_gemini_vision(api_key, args.model, png_path, build_pure_vlm_prompt(meta))
            rec = {"mode": "pure_vlm", "case_id": cid, "output": out}
            append_cache(cache_path, rec)
            cache[k_pure] = rec
            time.sleep(args.sleep)
        pure_inc = bool(cache[k_pure]["output"].get("is_inconsistent", False))
        pure_preds.append((gt_inc, pure_inc, meta["category"], meta.get("is_raster_pdf", False)))

        # 2. Hybrid (Track-1 + Track-2 VLM)
        # Fast-path: if Track-1 already fired (Precision=1.000), no VLM call needed
        if t1_findings:
            hyb_inc = True
        else:
            k_hyb = f"hybrid::{cid}"
            if k_hyb not in cache:
                print(f"[{idx}/{len(json_files)}] Calling Hybrid VLM ({args.model}) on {cid}...")
                out = call_gemini_vision(api_key, args.model, png_path, build_hybrid_prompt(meta, t1_findings))
                rec = {"mode": "hybrid", "case_id": cid, "output": out}
                append_cache(cache_path, rec)
                cache[k_hyb] = rec
                time.sleep(args.sleep)
            hyb_inc = bool(cache[k_hyb]["output"].get("is_inconsistent", False))
        hybrid_preds.append((gt_inc, hyb_inc, meta["category"], meta.get("is_raster_pdf", False)))

    report = {
        "model": args.model,
        "track1_rule_only": rule_data["summary"],
        "track2_pure_vlm": compute_metrics(pure_preds),
        "hybrid_track1_plus_vlm": compute_metrics(hybrid_preds),
    }
    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== Exp-05B Comparison ===")
    print("Track-1 Only :", rule_data["summary"]["accuracy"], "F1:", rule_data["summary"]["f1"])
    print("Pure VLM     :", report["track2_pure_vlm"]["accuracy"], "F1:", report["track2_pure_vlm"]["f1"])
    print("Hybrid Audit :", report["hybrid_track1_plus_vlm"]["accuracy"], "F1:", report["hybrid_track1_plus_vlm"]["f1"])
    print(f"Saved report to: {OUT_PATH}")


if __name__ == "__main__":
    main()

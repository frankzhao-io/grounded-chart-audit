"""Exp-13: Evaluate Local Open-Source VLM (qwen2.5vl:7b via Ollama) on Benchmark v1 (N=60).

Runs the exact same Pure VLM and Grounded Hybrid prompts as Exp-05B / Exp-06
against local Ollama qwen2.5vl:7b on RTX 3080, caches every call to JSONL,
records exact per-image latency, and compares side-by-side with Gemini 3.5 Flash-Lite.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path
from typing import Any

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
BENCH_DIR = BASE_DIR / "data" / "benchmark_v1"
RULE_REPORT = BASE_DIR / "data" / "benchmark_v1_rule_baseline.json"
GEMINI_REPORT = BASE_DIR / "data" / "benchmark_v1_grounded_hybrid_results.json"

PURE_CACHE = BASE_DIR / "data" / "vlm_eval_cache_qwen2.5vl-7b.jsonl"
HYB_CACHE = BASE_DIR / "data" / "vlm_grounded_hybrid_cache_qwen2.5vl-7b.jsonl"
OUT_PATH = BASE_DIR / "data" / "benchmark_v1_local_vlm_results.json"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL = os.environ.get("OLLAMA_VLM_MODEL", "qwen2.5vl:7b")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, BASE_DIR / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


eval7 = _load("eval7", "src/07_eval_vlm_and_hybrid.py")
hyb8 = _load("hyb8", "src/08_eval_grounded_hybrid.py")
loc13 = _load("loc13", "src/13_track2_local_vlm_audit.py")


def call_ollama_vision(png_path: Path, prompt: str, timeout: int = 120) -> tuple[dict[str, Any], float]:
    """Query local Ollama VLM with JSON output and return (parsed_json, elapsed_sec)."""
    img_b64, _ = loc13.encode_image_b64(png_path)
    payload = {
        "model": MODEL,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0},
        "messages": [
            {"role": "user", "content": prompt, "images": [img_b64]},
        ],
    }
    t0 = time.perf_counter()
    resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    resp.raise_for_status()
    elapsed = time.perf_counter() - t0
    raw = resp.json().get("message", {}).get("content", "")
    try:
        parsed = loc13.parse_json_response(raw)
    except Exception as exc:
        parsed = {"is_inconsistent": False, "reasons": [f"parse_error: {exc}"], "raw": raw}
    return parsed, round(elapsed, 2)


def main() -> None:
    rule_data = json.loads(RULE_REPORT.read_text(encoding="utf-8"))
    rule_map = {r["case_id"]: r for r in rule_data["records"]}

    pure_cache = eval7.load_cache(PURE_CACHE)
    hyb_cache = eval7.load_cache(HYB_CACHE)

    json_files = sorted(BENCH_DIR.glob("*.json"))
    pure_preds, grounded_preds = [], []
    pure_times, hyb_times = [], []

    for idx, jp in enumerate(json_files, 1):
        meta = json.loads(jp.read_text(encoding="utf-8"))
        cid = meta["case_id"]
        png_path = BENCH_DIR / meta["files"]["png"]
        pdf_path = BENCH_DIR / meta["files"]["pdf"]
        gt_inc = not meta["is_consistent"]
        t1_findings = rule_map[cid]["findings"]

        # 1. Pure VLM
        pk = f"pure_vlm::{cid}"
        if pk not in pure_cache:
            out, sec = call_ollama_vision(png_path, eval7.build_pure_vlm_prompt(meta))
            rec = {"mode": "pure_vlm", "case_id": cid, "elapsed_sec": sec, "output": out}
            eval7.append_cache(PURE_CACHE, rec)
            pure_cache[pk] = rec
            print(f"[{idx}/{len(json_files)}] Pure VLM {cid}: inc={out.get('is_inconsistent')} ({sec}s)")
        pure_times.append(pure_cache[pk].get("elapsed_sec", 0.0))
        pure_inc = bool(pure_cache[pk]["output"].get("is_inconsistent", False))
        pure_preds.append((gt_inc, pure_inc, meta["category"], meta.get("is_raster_pdf", False)))

        # 2. Grounded Hybrid
        if t1_findings:
            gh_inc = True
        else:
            hk = f"grounded_hybrid::{cid}"
            if hk not in hyb_cache:
                pos_facts = hyb8.extract_positive_facts(pdf_path, meta)
                out, sec = call_ollama_vision(png_path, hyb8.build_grounded_hybrid_prompt(meta, pos_facts))
                rec = {
                    "mode": "grounded_hybrid",
                    "case_id": cid,
                    "verified_facts": pos_facts,
                    "elapsed_sec": sec,
                    "output": out,
                }
                eval7.append_cache(HYB_CACHE, rec)
                hyb_cache[hk] = rec
                print(f"[{idx}/{len(json_files)}] Grounded Hybrid {cid}: inc={out.get('is_inconsistent')} ({sec}s)")
            hyb_times.append(hyb_cache[hk].get("elapsed_sec", 0.0))
            gh_inc = bool(hyb_cache[hk]["output"].get("is_inconsistent", False))

        grounded_preds.append((gt_inc, gh_inc, meta["category"], meta.get("is_raster_pdf", False)))

    report = {
        "model": MODEL,
        "benchmark_n": len(json_files),
        "timing": {
            "pure_vlm_calls": len(pure_times),
            "pure_vlm_total_sec": round(sum(pure_times), 2),
            "pure_vlm_avg_sec": round(sum(pure_times) / len(pure_times), 2) if pure_times else 0.0,
            "grounded_hybrid_vlm_calls": len(hyb_times),
            "grounded_hybrid_total_sec": round(sum(hyb_times), 2),
            "grounded_hybrid_avg_sec": round(sum(hyb_times) / len(hyb_times), 2) if hyb_times else 0.0,
        },
        "track2_pure_vlm": eval7.compute_metrics(pure_preds),
        "grounded_hybrid": eval7.compute_metrics(grounded_preds),
    }
    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n=== Local {MODEL} Benchmark v1 Results (N={len(json_files)}) ===")
    for label, key in [("Pure VLM", "track2_pure_vlm"), ("Grounded Hybrid", "grounded_hybrid")]:
        m = report[key]
        print(f"{label:16s} | Acc={m['accuracy']:.4f} | Prec={m['precision']:.4f} | Rec={m['recall']:.4f} | F1={m['f1']:.4f}")
    print(f"Timing: Pure VLM={report['timing']['pure_vlm_total_sec']}s ({report['timing']['pure_vlm_avg_sec']}s/img), "
          f"Hybrid VLM calls={report['timing']['grounded_hybrid_vlm_calls']} -> {report['timing']['grounded_hybrid_total_sec']}s")

    if GEMINI_REPORT.exists():
        gem = json.loads(GEMINI_REPORT.read_text(encoding="utf-8"))
        print(f"\n=== Side-by-Side vs {gem['model']} ===")
        for label, key in [("Pure VLM", "track2_pure_vlm"), ("Grounded Hybrid", "grounded_hybrid")]:
            g, l = gem[key], report[key]
            print(f"{label:16s} | Gemini F1={g['f1']:.4f} (Acc={g['accuracy']:.4f}) vs Local F1={l['f1']:.4f} (Acc={l['accuracy']:.4f})")


if __name__ == "__main__":
    main()

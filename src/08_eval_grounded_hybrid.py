"""Exp-06: Bidirectional Grounded Hybrid Auditor (Track-1 Positive+Negative Facts + Track-2 VLM).

Reuses cached Pure VLM results from Exp-05B and evaluates Bidirectional Grounded Hybrid
on Benchmark v1 (N=60). Only calls VLM on cases where Track-1 found no hard error (28 cases),
passing Track-1's verified geometric facts as false-positive vetoes.
"""

from __future__ import annotations

import importlib.util
import json
import re
import time
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
BENCH_DIR = BASE_DIR / "data" / "benchmark_v1"
RULE_REPORT = BASE_DIR / "data" / "benchmark_v1_rule_baseline.json"
CACHE_PATH = BASE_DIR / "data" / "vlm_grounded_hybrid_cache_gemini-3.5-flash-lite.jsonl"
PURE_CACHE_PATH = BASE_DIR / "data" / "vlm_eval_cache_gemini-3.5-flash-lite.jsonl"
OUT_PATH = BASE_DIR / "data" / "benchmark_v1_grounded_hybrid_results.json"

# Import helpers from 04 and 07
spec4 = importlib.util.spec_from_file_location("vec4", BASE_DIR / "src" / "04_vector_geometry_auditor.py")
vec4 = importlib.util.module_from_spec(spec4)
assert spec4 and spec4.loader
spec4.loader.exec_module(vec4)

spec7 = importlib.util.spec_from_file_location("eval7", BASE_DIR / "src" / "07_eval_vlm_and_hybrid.py")
eval7 = importlib.util.module_from_spec(spec7)
assert spec7 and spec7.loader
spec7.loader.exec_module(eval7)


def extract_positive_facts(pdf_path: Path, meta: dict[str, Any]) -> list[str]:
    """Extract deterministic positive verification facts from vector PDF + prose."""
    vec = vec4.extract_vector_elements(pdf_path)
    combined_prose = f"{meta['caption']}\n{meta['main_text_claim']}"
    facts: list[str] = []

    # 1. Exact vector dot count verification
    n_match = vec4.N_PER_GROUP_RE.search(combined_prose)
    if n_match and vec["bars"] and vec["total_dots"] > 0:
        claimed_n = int(n_match.group(1))
        if all(b["dot_count"] == claimed_n for b in vec["bars"]):
            facts.append(
                f"VERIFIED_SAMPLE_SIZE: Exact PDF vector count found {claimed_n} points per group, "
                f"matching claimed n={claimed_n}. Do NOT flag sample_size_mismatch."
            )

    # 2. Y-axis zero baseline verification
    if vec["y_ticks"] and min(vec["y_ticks"]) == 0.0:
        facts.append("VERIFIED_Y_AXIS: Vector Y-axis ticks start at 0.0. Do NOT flag truncated Y-axis.")

    # 3. Error bar definition verification
    if vec4.SD_SEM_RE.search(combined_prose):
        facts.append("VERIFIED_ERROR_BAR_DEF: Error bar definition (SD/SEM/CI) is explicitly stated in prose.")

    # 4. Star vs p-value consistency verification
    stars = vec4.STAR_RE.findall(vec["full_text"])
    p_matches = vec4.PVAL_RE.findall(combined_prose)
    if stars and p_matches:
        max_stars = max(stars, key=len)
        bound = vec4.STAR_THRESHOLDS.get(max_stars)
        if bound is not None and all(float(v) < bound for _, v in p_matches):
            facts.append(
                f"VERIFIED_SIGNIFICANCE: PDF star '{max_stars}' (p<{bound}) is consistent with prose p-values."
            )

    return facts


def build_grounded_hybrid_prompt(meta: dict[str, Any], positive_facts: list[str]) -> str:
    facts_str = "\n".join(f"- {f}" for f in positive_facts) if positive_facts else "- None (figure may be rasterized)."
    return (
        "You are a scientific integrity auditor. Deterministic PDF vector/text verification has already "
        "confirmed the following ground-truth facts:\n"
        f"{facts_str}\n\n"
        "STRICT RULE: You MUST respect all VERIFIED_* facts above and MUST NOT contradict them "
        "(in particular, never override VERIFIED_SAMPLE_SIZE by visually guessing overlapping scatter dots).\n"
        "Your job is to inspect the figure image and text for any REMAINING unverified issues:\n"
        "1. Effect direction inversion (e.g., prose claims Group B > Group A, but bars/boxes show Group A > Group B).\n"
        "2. Visual/statistical conflicts on rasterized figures where vector facts were unavailable "
        "(missing dots, truncated Y-axis, star vs p-value conflict, missing SD/SEM definition).\n\n"
        f"Caption: {meta['caption']}\n"
        f"Main text claim: {meta['main_text_claim']}\n\n"
        'Respond strictly in JSON: {"is_inconsistent": true/false, "reasons": ["..."]}'
    )


def main() -> None:
    api_key = eval7.load_api_key()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not found.")

    model = "gemini-3.5-flash-lite"
    rule_data = json.loads(RULE_REPORT.read_text(encoding="utf-8"))
    rule_map = {r["case_id"]: r for r in rule_data["records"]}
    pure_cache = eval7.load_cache(PURE_CACHE_PATH)
    hyb_cache = eval7.load_cache(CACHE_PATH)

    json_files = sorted(BENCH_DIR.glob("*.json"))
    pure_preds, grounded_preds = [], []

    for idx, jp in enumerate(json_files, 1):
        meta = json.loads(jp.read_text(encoding="utf-8"))
        cid = meta["case_id"]
        png_path = BENCH_DIR / meta["files"]["png"]
        pdf_path = BENCH_DIR / meta["files"]["pdf"]
        gt_inc = not meta["is_consistent"]
        t1_findings = rule_map[cid]["findings"]

        pure_inc = bool(pure_cache[f"pure_vlm::{cid}"]["output"].get("is_inconsistent", False))
        pure_preds.append((gt_inc, pure_inc, meta["category"], meta.get("is_raster_pdf", False)))

        if t1_findings:
            gh_inc = True
        else:
            k = f"grounded_hybrid::{cid}"
            if k not in hyb_cache:
                pos_facts = extract_positive_facts(pdf_path, meta)
                print(f"[{idx}/{len(json_files)}] Calling Grounded Hybrid ({len(pos_facts)} verified facts) on {cid}...")
                out = eval7.call_gemini_vision(
                    api_key, model, png_path, build_grounded_hybrid_prompt(meta, pos_facts)
                )
                rec = {"mode": "grounded_hybrid", "case_id": cid, "verified_facts": pos_facts, "output": out}
                eval7.append_cache(CACHE_PATH, rec)
                hyb_cache[k] = rec
                time.sleep(4.0)
            gh_inc = bool(hyb_cache[k]["output"].get("is_inconsistent", False))

        grounded_preds.append((gt_inc, gh_inc, meta["category"], meta.get("is_raster_pdf", False)))

    report = {
        "model": model,
        "track1_rule_only": rule_data["summary"],
        "track2_pure_vlm": eval7.compute_metrics(pure_preds),
        "grounded_hybrid": eval7.compute_metrics(grounded_preds),
    }
    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Exp-06 Bidirectional Grounded Hybrid Results (N=60) ===")
    for name, key in [
        ("Track-1 Only   ", "track1_rule_only"),
        ("Pure VLM       ", "track2_pure_vlm"),
        ("Grounded Hybrid", "grounded_hybrid"),
    ]:
        m = report[key]
        c0 = m["by_category"]["C0_consistent"]
        c0_str = f"{c0['correct']}/{c0['total']}" if isinstance(c0, dict) else c0
        print(f"{name}: Acc={m['accuracy']:.4f} | Prec={m['precision']:.4f} | Rec={m['recall']:.4f} | F1={m['f1']:.4f} | C0={c0_str}")
    print(f"Saved report to: {OUT_PATH}")


if __name__ == "__main__":
    main()

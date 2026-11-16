"""Exp-09: Run Grounded Hybrid Auditor on 23 real arXiv figure-text pairs.

For each extracted pair in data/real_paper_pairs/real_pairs_manifest.json:
1. Run Track-1 deterministic prose/caption checks (e.g., error bar mention without SD/SEM/CI,
   p-value anomalies, significance star mismatches).
2. Run Track-2 VLM (gemini-3.5-flash-lite) with Grounded prompt to inspect the real figure
   image alongside its caption and referencing main-text paragraphs.
3. Cache results per item in data/real_paper_audit_cache.jsonl and output
   data/real_paper_audit_results.json for independent subagent verification.
"""

from __future__ import annotations

import importlib.util
import json
import re
import time
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
PAIR_DIR = BASE_DIR / "data" / "real_paper_pairs"
MANIFEST_PATH = PAIR_DIR / "real_pairs_manifest.json"
CACHE_PATH = BASE_DIR / "data" / "real_paper_audit_cache.jsonl"
OUT_PATH = BASE_DIR / "data" / "real_paper_audit_results.json"

spec7 = importlib.util.spec_from_file_location("eval7", BASE_DIR / "src" / "07_eval_vlm_and_hybrid.py")
eval7 = importlib.util.module_from_spec(spec7)
assert spec7 and spec7.loader
spec7.loader.exec_module(eval7)

SD_SEM_RE = re.compile(
    r"(?:\b(?:SDs?|SEMs?|standard deviations?|standard errors?|(?:95%\s*)?CIs?|confidence intervals?|IQRs?|interquartile(?:\s+range)?)\b|(?<!\w)(?:s\.d\.|s\.e\.m?\.|(?:95%\s*)?c\.i\.|i\.q\.r\.)(?!\w))",
    re.I,
)
ERR_MENTION_RE = re.compile(r"\b(?:error\s*bars?|shaded\s*(?:area|region|band)|±)\b", re.I)
PVAL_RE = re.compile(r"\bp\s*([<=>≤≥])\s*(0?\.\d+)", re.I)


def track1_real_checks(pair: dict[str, Any]) -> list[str]:
    """Deterministic checks on real paper caption + referencing paragraphs."""
    caption = pair["caption"]
    refs = "\n".join(pair.get("referencing_paragraphs", []))
    combined = f"{caption}\n{refs}"
    findings: list[str] = []

    if ERR_MENTION_RE.search(caption) and not SD_SEM_RE.search(combined):
        findings.append("missing_error_bar_definition (error bars/band mentioned without SD/SEM/CI/IQR)")

    for op, val_str in PVAL_RE.findall(combined):
        v = float(val_str)
        if op == "=" and v == 0.0:
            findings.append(f"exact_p_zero (p={val_str})")
        elif v > 1.0:
            findings.append(f"invalid_p_gt_1 (p{op}{val_str})")

    return findings


def build_real_audit_prompt(pair: dict[str, Any], t1_findings: list[str]) -> str:
    refs_text = "\n\n".join(pair.get("referencing_paragraphs", [])[:3]) or "(No referencing paragraph extracted)"
    t1_str = "\n".join(f"- {f}" for f in t1_findings) if t1_findings else "- None detected by prose rules."
    return (
        "You are an expert scientific integrity auditor reviewing a real published preprint figure.\n"
        "Automated Track-1 prose findings:\n"
        f"{t1_str}\n\n"
        "Carefully inspect the attached figure image, its caption, and the referencing main-text paragraphs.\n"
        "Check for:\n"
        "1. Quantitative or directional contradictions between the figure and the caption/text.\n"
        "2. Misleading visual practices (e.g., truncated bar Y-axis, undefined error bars if error bars are plotted, "
        "mismatch between figure panel labels and text).\n"
        "3. Be conservative and precise: only flag an issue if you have clear visual or textual evidence. "
        "Do NOT guess scatter counts on dense real plots.\n\n"
        f"Caption: {pair['caption']}\n\n"
        f"Referencing paragraphs:\n{refs_text}\n\n"
        'Respond strictly in JSON: {"has_issue": true/false, "severity": "none"|"minor"|"major", "issues": ["..."], "summary": "..."}'
    )


def main() -> None:
    api_key = eval7.load_api_key()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not found.")

    model = "gemini-3.5-flash-lite"
    pairs = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cache = eval7.load_cache(CACHE_PATH)

    results = []
    for idx, pair in enumerate(pairs, 1):
        cid = f"{pair['paper_id']}__fig{pair['figure_num']}"
        img_path = PAIR_DIR / pair["image_file"]
        t1_findings = track1_real_checks(pair)

        k = f"real_audit::{cid}"
        if k not in cache:
            print(f"[{idx}/{len(pairs)}] Auditing {cid}...")
            out = eval7.call_gemini_vision(api_key, model, img_path, build_real_audit_prompt(pair, t1_findings))
            rec = {"mode": "real_audit", "case_id": cid, "track1_findings": t1_findings, "output": out}
            eval7.append_cache(CACHE_PATH, rec)
            cache[k] = rec
            time.sleep(4.2)

        vlm_out = cache[k]["output"]
        results.append({
            "case_id": cid,
            "paper_id": pair["paper_id"],
            "figure_num": pair["figure_num"],
            "page": pair["page"],
            "image_file": pair["image_file"],
            "track1_findings": t1_findings,
            "vlm_has_issue": bool(vlm_out.get("has_issue", False)),
            "vlm_severity": vlm_out.get("severity", "none"),
            "vlm_issues": vlm_out.get("issues", []),
            "vlm_summary": vlm_out.get("summary", ""),
        })

    hard_t1 = [f for f in results if any(not msg.startswith("missing_error_bar_definition") for msg in f["track1_findings"])]
    flagged = sum(1 for r in results if r["vlm_has_issue"] or any(not msg.startswith("missing_error_bar_definition") for msg in r["track1_findings"]))
    OUT_PATH.write_text(json.dumps({"total_pairs": len(results), "flagged_count": flagged, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nAudited {len(results)} real paper pairs. Flagged: {flagged}/{len(results)}")
    print(f"Saved results to: {OUT_PATH}")


if __name__ == "__main__":
    main()

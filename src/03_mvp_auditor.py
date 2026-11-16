"""MVP Track-1 Auditor (PDF text/tick/star extractor + rule-based consistency checks).

Runs on:
1) Synthetic MVP benchmark cases (C0-C5) in data/mvp_samples/
2) High-stat real arXiv paper (2611.12855v1.pdf) in data/real_papers/

Demonstrates what deterministic PDF/text rules can catch vs. where Track-2 VLM
semantic/raster reasoning is required.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pypdf


BASE_DIR = Path(__file__).resolve().parents[1]
MVP_DIR = BASE_DIR / "data" / "mvp_samples"
REAL_DIR = BASE_DIR / "data" / "real_papers"

STAR_THRESHOLDS = {
    "*": 0.05,
    "**": 0.01,
    "***": 0.001,
    "****": 0.0001,
}

PVAL_RE = re.compile(r"\bp\s*([<=>≤≥])\s*(0?\.\d+)", re.I)
N_RE = re.compile(r"\bn\s*=\s*(\d+)", re.I)
SD_SEM_RE = re.compile(r"\b(?:SD|SEM|s\.d\.|s\.e\.m\.|standard deviation|standard error|95%\s*CI)\b", re.I)
STAR_RE = re.compile(r"(?<!\*)\*{1,4}(?!\*)")
NUMERIC_TICK_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def extract_pdf_text_and_tokens(pdf_path: Path) -> tuple[str, list[str]]:
    """Extract full text and individual non-empty lines/tokens from a PDF."""
    reader = pypdf.PdfReader(str(pdf_path))
    pages_text = [p.extract_text() or "" for p in reader.pages]
    joined = "\n".join(pages_text)
    tokens = [t.strip() for t in re.split(r"\s+", joined) if t.strip()]
    return joined, tokens


def extract_numeric_y_ticks(pdf_text: str) -> list[float]:
    """Heuristic extraction of numeric axis tick labels from vector PDF text."""
    vals: list[float] = []
    for line in pdf_text.splitlines():
        s = line.strip()
        if NUMERIC_TICK_RE.match(s):
            try:
                vals.append(float(s))
            except ValueError:
                pass
    return vals


def audit_mvp_case(json_path: Path) -> dict[str, Any]:
    """Run Track-1 rule audit on one MVP case."""
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    pdf_path = MVP_DIR / meta["files"]["pdf"]
    pdf_text, _ = extract_pdf_text_and_tokens(pdf_path)

    combined_prose = f"{meta['caption']}\n{meta['main_text_claim']}"
    findings: list[str] = []

    # Rule 1: Truncated Y-axis check on bar/comparison figures
    y_ticks = extract_numeric_y_ticks(pdf_text)
    if y_ticks:
        min_tick = min(y_ticks)
        if min_tick > 0 and ("bar" in json_path.stem or "truncated" in json_path.stem or min_tick >= 0.5):
            findings.append(f"truncated_yaxis_suspected (min_tick={min_tick})")

    # Rule 2: Significance star (in PDF) vs. reported p-value (in prose)
    stars_in_pdf = STAR_RE.findall(pdf_text)
    p_matches = PVAL_RE.findall(combined_prose)
    if stars_in_pdf and p_matches:
        max_stars = max(stars_in_pdf, key=len)
        star_bound = STAR_THRESHOLDS.get(max_stars)
        for op, val_str in p_matches:
            pval = float(val_str)
            if star_bound is not None and op in ("=", ">", "≥") and pval >= star_bound:
                findings.append(
                    f"star_pvalue_conflict (pdf_star='{max_stars}' implies p<{star_bound}, prose says p{op}{pval})"
                )

    # Rule 3: Error bar definition check (if error-bar/mean mentioned, SD/SEM/CI should be defined)
    if re.search(r"error bar|±", combined_prose, re.I) and not SD_SEM_RE.search(combined_prose):
        findings.append("missing_error_bar_definition (SD/SEM/CI not specified)")

    # Note what Track-1 alone cannot reliably verify without geometry/VLM
    predicted_inconsistent = len(findings) > 0
    return {
        "case_id": meta["case_id"],
        "ground_truth_inconsistent": not meta["is_consistent"],
        "track1_predicted_inconsistent": predicted_inconsistent,
        "correct": predicted_inconsistent == (not meta["is_consistent"]),
        "findings": findings,
        "y_ticks_extracted": y_ticks,
        "stars_extracted": stars_in_pdf,
    }


def audit_real_paper_prose(pdf_path: Path) -> dict[str, Any]:
    """Quick prose-level statistical audit on a real arXiv PDF."""
    text, _ = extract_pdf_text_and_tokens(pdf_path)
    p_matches = PVAL_RE.findall(text)
    n_matches = N_RE.findall(text)
    sd_sem_matches = SD_SEM_RE.findall(text)

    # Check for suspicious exact p=0.000 or p > 1.0
    anomalies = []
    for op, val_str in p_matches:
        v = float(val_str)
        if op == "=" and v == 0.0:
            anomalies.append(f"exact_p_zero (p={val_str})")
        elif v > 1.0:
            anomalies.append(f"invalid_p_gt_1 (p{op}{val_str})")

    return {
        "pdf": pdf_path.name,
        "p_value_mentions": len(p_matches),
        "sample_size_n_mentions": len(n_matches),
        "sd_sem_ci_mentions": len(sd_sem_matches),
        "prose_anomalies": anomalies[:10],
    }


def main() -> None:
    print("=== Track-1 Rule Auditor on MVP Samples (C0-C5) ===")
    results = []
    for jp in sorted(MVP_DIR.glob("C*.json")):
        res = audit_mvp_case(jp)
        results.append(res)
        status = "PASS" if res["correct"] else "MISS (needs Track-2 VLM / geometry)"
        print(f"- {res['case_id']}: {status}")
        if res["findings"]:
            for f in res["findings"]:
                print(f"    -> {f}")

    correct_cnt = sum(1 for r in results if r["correct"])
    print(f"\nTrack-1 Accuracy on MVP C0-C5: {correct_cnt}/{len(results)}")

    real_pdf = REAL_DIR / "2611.12855v1.pdf"
    if real_pdf.exists():
        print("\n=== Quick Real-Paper Prose Audit (2611.12855v1.pdf) ===")
        real_res = audit_real_paper_prose(real_pdf)
        print(json.dumps(real_res, indent=2, ensure_ascii=False))

    out_path = BASE_DIR / "data" / "mvp_audit_results.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved audit results to: {out_path}")


if __name__ == "__main__":
    main()

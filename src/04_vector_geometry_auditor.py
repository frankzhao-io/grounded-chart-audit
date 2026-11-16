"""Track-1 + Vector Geometry Auditor using PyMuPDF (fitz).

Extends 03_mvp_auditor.py with vector-level extraction from PDF drawings:
1. Bar geometry extraction (x-center, height) paired with x-axis labels
   to detect effect-direction inversions (C5).
2. Scatter dot counting per bar x-region compared against claimed per-group
   sample size n (C1).
3. Preserves all text/tick rules (C2 star vs p-value, C3 truncated Y-axis,
   C4 missing SD/SEM definition).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


BASE_DIR = Path(__file__).resolve().parents[1]
MVP_DIR = BASE_DIR / "data" / "mvp_samples"

STAR_THRESHOLDS = {"*": 0.05, "**": 0.01, "***": 0.001, "****": 0.0001}
PVAL_RE = re.compile(r"\bp\s*([<=>≤≥])\s*(0?\.\d+)", re.I)
N_PER_GROUP_RE = re.compile(r"\bn\s*=\s*(\d+)\s*(?:per\s+group|biological\s+replicates\s+per\s+group)?", re.I)
SD_SEM_RE = re.compile(r"\b(?:SD|SEM|s\.d\.|s\.e\.m\.|standard deviation|standard error|95%\s*CI)\b", re.I)
STAR_RE = re.compile(r"(?<!\*)\*{1,4}(?!\*)")
NUMERIC_TICK_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def extract_vector_elements(pdf_path: Path) -> dict[str, Any]:
    """Extract text words, numeric Y-ticks, bar rectangles, and scatter dots."""
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    full_text = page.get_text("text")
    words = page.get_text("words")  # (x0, y0, x1, y1, word, block, line, word_no)

    drawings = page.get_drawings()
    page_rect = page.rect

    # Identify bars: filled non-white/non-black rectangles with substantial width & height
    bars: list[dict[str, Any]] = []
    dots: list[dict[str, float]] = []

    for d in drawings:
        fill = d.get("fill")
        if fill is None:
            continue
        r = d["rect"]
        # Skip page/axes background rectangles
        if r.width > page_rect.width * 0.7 or r.height > page_rect.height * 0.7:
            continue
        is_white = all(c > 0.98 for c in fill)
        is_black = all(c < 0.02 for c in fill)
        if is_white or is_black:
            continue

        if r.width >= 18.0 and r.height >= 10.0:
            bars.append({
                "x0": r.x0,
                "x1": r.x1,
                "xc": (r.x0 + r.x1) / 2.0,
                "y0": r.y0,
                "y1": r.y1,
                "height": r.height,
            })
        elif 1.5 <= r.width <= 12.0 and 1.5 <= r.height <= 12.0 and abs(r.width - r.height) < 3.0:
            dots.append({
                "xc": (r.x0 + r.x1) / 2.0,
                "yc": (r.y0 + r.y1) / 2.0,
            })

    bars.sort(key=lambda b: b["xc"])

    # Pair each bar with x-axis tick label(s) below the bar bottom (y1)
    for b in bars:
        label_words = [
            w for w in words
            if (b["x0"] - 15.0) <= ((w[0] + w[2]) / 2.0) <= (b["x1"] + 15.0)
            and b["y1"] - 2.0 <= w[1] <= b["y1"] + 25.0
        ]
        label_words.sort(key=lambda w: w[0])
        b["label"] = " ".join(w[4] for w in label_words).strip()
        b["dot_count"] = sum(
            1 for dt in dots if (b["x0"] - 10.0) <= dt["xc"] <= (b["x1"] + 10.0)
        )

    y_ticks: list[float] = []
    for line in full_text.splitlines():
        s = line.strip()
        if NUMERIC_TICK_RE.match(s):
            try:
                y_ticks.append(float(s))
            except ValueError:
                pass

    return {
        "full_text": full_text,
        "y_ticks": y_ticks,
        "bars": bars,
        "total_dots": len(dots),
    }


def audit_case(json_path: Path) -> dict[str, Any]:
    """Run combined Track-1 + Vector Geometry audit on one MVP case."""
    meta = json.loads(json_path.read_text(encoding="utf-8"))
    pdf_path = MVP_DIR / meta["files"]["pdf"]
    vec = extract_vector_elements(pdf_path)

    combined_prose = f"{meta['caption']}\n{meta['main_text_claim']}"
    findings: list[str] = []

    # 1. Truncated Y-axis check
    if vec["y_ticks"]:
        min_tick = min(vec["y_ticks"])
        if min_tick > 0 and (len(vec["bars"]) > 0 or min_tick >= 0.5):
            findings.append(f"truncated_yaxis_suspected (min_tick={min_tick})")

    # 2. Significance star vs. prose p-value
    stars = STAR_RE.findall(vec["full_text"])
    p_matches = PVAL_RE.findall(combined_prose)
    if stars and p_matches:
        max_stars = max(stars, key=len)
        star_bound = STAR_THRESHOLDS.get(max_stars)
        for op, val_str in p_matches:
            pval = float(val_str)
            if star_bound is not None and op in ("=", ">", "≥") and pval >= star_bound:
                findings.append(
                    f"star_pvalue_conflict (pdf_star='{max_stars}' implies p<{star_bound}, prose says p{op}{pval})"
                )

    # 3. Missing error-bar definition (SD/SEM/CI)
    if re.search(r"error bar|±", combined_prose, re.I) and not SD_SEM_RE.search(combined_prose):
        findings.append("missing_error_bar_definition (SD/SEM/CI not specified)")

    # 4. Vector scatter-point count vs. claimed n (C1)
    n_match = N_PER_GROUP_RE.search(combined_prose)
    if n_match and vec["bars"] and vec["total_dots"] > 0:
        claimed_n = int(n_match.group(1))
        for b in vec["bars"]:
            if b["dot_count"] > 0 and b["dot_count"] != claimed_n:
                findings.append(
                    f"sample_size_mismatch (bar='{b['label']}' has {b['dot_count']} vector dots, prose claims n={claimed_n})"
                )
                break

    # 5. Bar height direction vs. prose comparison claim (C5)
    comp_match = re.search(
        r"\b(Group\s+[A-Z]|Model\s+[A-Z]|Baseline|Proposed|Vehicle|Drug\s+X|Control|Treatment|Ours)\b"
        r"[^.]{0,50}?\b(higher|greater|larger|exceeded|outperformed)\b"
        r"[^.]{0,30}?\bthan\b[^.]{0,20}?"
        r"\b(Group\s+[A-Z]|Model\s+[A-Z]|Baseline|Proposed|Vehicle|Drug\s+X|Control|Treatment|Ours)\b",
        combined_prose,
        re.I,
    )
    if comp_match and len(vec["bars"]) >= 2:
        higher_lbl = comp_match.group(1).lower()
        lower_lbl = comp_match.group(3).lower()
        bar_map = {b["label"].lower(): b["height"] for b in vec["bars"] if b["label"]}
        if higher_lbl in bar_map and lower_lbl in bar_map:
            if bar_map[higher_lbl] <= bar_map[lower_lbl]:
                findings.append(
                    f"direction_inversion (prose claims '{comp_match.group(1)}' > '{comp_match.group(3)}', "
                    f"but bar heights are {bar_map[higher_lbl]:.1f} vs {bar_map[lower_lbl]:.1f})"
                )

    pred_inconsistent = len(findings) > 0
    return {
        "case_id": meta["case_id"],
        "ground_truth_inconsistent": not meta["is_consistent"],
        "predicted_inconsistent": pred_inconsistent,
        "correct": pred_inconsistent == (not meta["is_consistent"]),
        "findings": findings,
        "bars": vec["bars"],
        "total_dots": vec["total_dots"],
    }


def main() -> None:
    print("=== Track-1 + Vector Geometry Auditor on MVP Samples (C0-C5) ===")
    results = []
    for jp in sorted(MVP_DIR.glob("C*.json")):
        res = audit_case(jp)
        results.append(res)
        status = "PASS" if res["correct"] else "FAIL"
        print(f"- {res['case_id']}: {status}")
        for f in res["findings"]:
            print(f"    -> {f}")

    correct_cnt = sum(1 for r in results if r["correct"])
    print(f"\nCombined Vector+Rule Accuracy on MVP C0-C5: {correct_cnt}/{len(results)}")

    out_path = BASE_DIR / "data" / "mvp_vector_audit_results.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved results to: {out_path}")


if __name__ == "__main__":
    main()

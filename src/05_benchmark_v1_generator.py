"""Benchmark v1 Generator (60 diverse chart-text consistency cases).

Generates 60 cases across 6 categories (10 each for C0-C5) with:
- Diverse group names, sample sizes, chart styles, and natural-language phrasings.
- A realistic mix of pure-vector PDFs (~75%) and raster-embedded PDFs (~25%),
  mirroring real-world arXiv PDF distributions observed in Exp-02.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fitz
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "benchmark_v1"

GROUP_PAIRS = [
    ("Control", "Treatment"),
    ("Vehicle", "Drug X"),
    ("Baseline", "Proposed"),
    ("Wild-Type", "Mutant"),
    ("Placebo", "Active"),
]

PALETTES = [
    ("#6c757d", "#2a9d8f"),
    ("#8d99ae", "#e76f51"),
    ("#adb5bd", "#457b9d"),
    ("#7f8c8d", "#c0392b"),
    ("#95a5a6", "#2980b9"),
]


def _save_case(
    fig: plt.Figure,
    case_id: str,
    metadata: dict[str, Any],
    rasterize_pdf: bool = False,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUT_DIR / f"{case_id}.png"
    pdf_path = OUT_DIR / f"{case_id}.pdf"
    json_path = OUT_DIR / f"{case_id}.json"

    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    if rasterize_pdf:
        # Embed raster PNG inside a PDF (mimics real papers that insert PNG figures)
        img_doc = fitz.open()
        pix = fitz.Pixmap(str(png_path))
        page = img_doc.new_page(width=pix.width * 0.5, height=pix.height * 0.5)
        page.insert_image(page.rect, filename=str(png_path))
        img_doc.save(str(pdf_path))
        img_doc.close()
    else:
        fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)

    metadata["is_raster_pdf"] = rasterize_pdf
    metadata["files"] = {"pdf": pdf_path.name, "png": png_path.name}
    json_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _style_ax(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def gen_c0(idx: int, rng: np.random.Generator) -> None:
    g1_name, g2_name = GROUP_PAIRS[idx % len(GROUP_PAIRS)]
    c1, c2 = PALETTES[idx % len(PALETTES)]
    n = int(rng.integers(6, 13))
    v1 = rng.normal(5.0, 0.7, size=n)
    v2 = rng.normal(7.5, 0.8, size=n)
    p_choices = [("*", 0.028), ("**", 0.0041), ("***", 0.0003)]
    star, pval = p_choices[idx % len(p_choices)]
    raster = (idx % 4 == 3)

    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    _style_ax(ax)
    if idx % 2 == 0:
        ax.bar([0, 1], [v1.mean(), v2.mean()], yerr=[v1.std(ddof=1), v2.std(ddof=1)],
               capsize=4, color=[c1, c2], alpha=0.75, width=0.55)
    else:
        ax.boxplot([v1, v2], positions=[0, 1], widths=0.45, patch_artist=True,
                   boxprops=dict(facecolor=c1, alpha=0.35))
    for i, vals in enumerate([v1, v2]):
        ax.scatter(np.full(n, i) + rng.uniform(-0.08, 0.08, n), vals, color="#222222", s=16, zorder=3)

    top_y = max(v1.max(), v2.max()) + 0.8
    ax.plot([0, 0, 1, 1], [top_y, top_y + 0.25, top_y + 0.25, top_y], color="black", lw=1.0)
    ax.text(0.5, top_y + 0.3, star, ha="center", va="bottom", fontsize=10)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([g1_name, g2_name])
    ax.set_ylabel("Response (a.u.)")
    ax.set_ylim(0, top_y + 1.5)

    _save_case(
        fig,
        f"C0_{idx:02d}",
        {
            "case_id": f"C0_{idx:02d}",
            "category": "C0_consistent",
            "is_consistent": True,
            "caption": f"Figure {idx+1}. {g2_name} vs {g1_name} (n = {n} per group; mean ± SD; {star}p = {pval}).",
            "main_text_claim": f"Across n = {n} replicates per group, {g2_name} outperformed {g1_name} (p = {pval}).",
        },
        rasterize_pdf=raster,
    )


def gen_c1(idx: int, rng: np.random.Generator) -> None:
    g1_name, g2_name = GROUP_PAIRS[idx % len(GROUP_PAIRS)]
    c1, c2 = PALETTES[idx % len(PALETTES)]
    plotted_n = int(rng.integers(5, 9))
    claimed_n = plotted_n + int(rng.integers(3, 8))
    raster = (idx % 3 == 2)  # ~30% rasterized

    v1 = rng.normal(4.5, 0.7, size=plotted_n)
    v2 = rng.normal(6.8, 0.8, size=plotted_n)
    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    _style_ax(ax)
    ax.bar([0, 1], [v1.mean(), v2.mean()], yerr=[v1.std(ddof=1), v2.std(ddof=1)],
           capsize=4, color=[c1, c2], alpha=0.75, width=0.55)
    for i, vals in enumerate([v1, v2]):
        ax.scatter(np.full(plotted_n, i) + rng.uniform(-0.08, 0.08, plotted_n), vals, color="#1d3557", s=18, zorder=3)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([g1_name, g2_name])
    ax.set_ylabel("Viability (%)")
    ax.set_ylim(0, 10.5)

    _save_case(
        fig,
        f"C1_{idx:02d}",
        {
            "case_id": f"C1_{idx:02d}",
            "category": "C1_sample_size_mismatch",
            "is_consistent": False,
            "caption": f"Figure {idx+1}. Comparison of {g1_name} and {g2_name} (n = {claimed_n} per group; mean ± SD).",
            "main_text_claim": f"Each cohort included {claimed_n} independent biological replicates (n = {claimed_n}).",
            "ground_truth": {"claimed_n": claimed_n, "plotted_n": plotted_n},
        },
        rasterize_pdf=raster,
    )


def gen_c2(idx: int, rng: np.random.Generator) -> None:
    g1_name, g2_name = GROUP_PAIRS[idx % len(GROUP_PAIRS)]
    c1, c2 = PALETTES[idx % len(PALETTES)]
    raster = (idx % 4 == 3)
    # Conflict pairs: figure star stronger than prose p-value
    conflicts = [("***", 0.041), ("***", 0.023), ("**", 0.039), ("***", 0.015), ("**", 0.048)]
    star, pval = conflicts[idx % len(conflicts)]
    phrasings = [
        f"The difference reached statistical significance (p = {pval}).",
        f"A significant gain was observed with a significance level of {pval}.",
        f"Pairwise comparison yielded p = {pval} between {g1_name} and {g2_name}.",
    ]

    v1 = rng.normal(9.5, 1.2, size=8)
    v2 = rng.normal(12.0, 1.3, size=8)
    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    _style_ax(ax)
    ax.bar([0, 1], [v1.mean(), v2.mean()], yerr=[v1.std(ddof=1), v2.std(ddof=1)],
           capsize=4, color=[c1, c2], alpha=0.8, width=0.55)
    top_y = max(v1.mean() + v1.std(ddof=1), v2.mean() + v2.std(ddof=1)) + 0.6
    ax.plot([0, 0, 1, 1], [top_y, top_y + 0.3, top_y + 0.3, top_y], color="black", lw=1.0)
    ax.text(0.5, top_y + 0.35, star, ha="center", va="bottom", fontsize=11)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([g1_name, g2_name])
    ax.set_ylabel("Score (a.u.)")
    ax.set_ylim(0, top_y + 2.0)

    _save_case(
        fig,
        f"C2_{idx:02d}",
        {
            "case_id": f"C2_{idx:02d}",
            "category": "C2_star_pvalue_conflict",
            "is_consistent": False,
            "caption": f"Figure {idx+1}. {g2_name} vs {g1_name} (mean ± SD; {star}).",
            "main_text_claim": phrasings[idx % len(phrasings)],
            "ground_truth": {"star": star, "prose_p": pval},
        },
        rasterize_pdf=raster,
    )


def gen_c3(idx: int, rng: np.random.Generator) -> None:
    g1_name, g2_name = GROUP_PAIRS[idx % len(GROUP_PAIRS)]
    c1, c2 = PALETTES[idx % len(PALETTES)]
    raster = (idx % 4 == 3)
    base = float(rng.choice([0.75, 0.80, 72.0, 85.0]))
    delta = 0.03 if base < 1.0 else 2.5
    ymin = base - (0.02 if base < 1.0 else 2.0)
    ymax = base + delta + (0.015 if base < 1.0 else 1.5)

    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    _style_ax(ax)
    ax.bar([0, 1], [base, base + delta], color=[c1, c2], width=0.52)
    ax.set_ylim(ymin, ymax)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([g1_name, g2_name])
    ax.set_ylabel("AUROC" if base < 1.0 else "Accuracy (%)")

    _save_case(
        fig,
        f"C3_{idx:02d}",
        {
            "case_id": f"C3_{idx:02d}",
            "category": "C3_truncated_yaxis",
            "is_consistent": False,
            "caption": f"Figure {idx+1}. Performance comparison showing substantial improvement of {g2_name}.",
            "main_text_claim": f"{g2_name} achieved {base+delta:.2f} vs {base:.2f} for {g1_name}.",
            "ground_truth": {"y_min": ymin, "y_max": ymax},
        },
        rasterize_pdf=raster,
    )


def gen_c4(idx: int, rng: np.random.Generator) -> None:
    g1_name, g2_name = GROUP_PAIRS[idx % len(GROUP_PAIRS)]
    c1, c2 = PALETTES[idx % len(PALETTES)]
    raster = (idx % 4 == 3)
    a = rng.normal(5.0, 0.5, size=12)
    b = np.concatenate([rng.normal(2.2, 0.3, size=6), rng.normal(7.8, 0.3, size=6)])

    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    _style_ax(ax)
    ax.bar([0, 1], [a.mean(), b.mean()], yerr=[a.std(ddof=1) / np.sqrt(12), b.std(ddof=1) / np.sqrt(12)],
           capsize=4, color=[c1, c2], width=0.55)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([g1_name, g2_name])
    ax.set_ylabel("Biomarker (ng/mL)")
    ax.set_ylim(0, 8.2)

    captions = [
        f"Figure {idx+1}. Biomarker levels across {g1_name} and {g2_name} (bars indicate group averages with error bars).",
        f"Figure {idx+1}. Summary of {g1_name} vs {g2_name} expression (error bars represent variability).",
    ]
    _save_case(
        fig,
        f"C4_{idx:02d}",
        {
            "case_id": f"C4_{idx:02d}",
            "category": "C4_concealed_distribution",
            "is_consistent": False,
            "caption": captions[idx % len(captions)],
            "main_text_claim": f"Both {g1_name} and {g2_name} showed unimodal distributions centered near 5.0 ng/mL.",
            "ground_truth": {"missing_err_def": True, "bimodal": True},
        },
        rasterize_pdf=raster,
    )


def gen_c5(idx: int, rng: np.random.Generator) -> None:
    g1_name, g2_name = GROUP_PAIRS[idx % len(GROUP_PAIRS)]
    c1, c2 = PALETTES[idx % len(PALETTES)]
    raster = (idx % 4 == 3)

    # Plotted: g1_name is HIGHER than g2_name
    v1 = rng.normal(8.8, 0.6, size=10)
    v2 = rng.normal(5.1, 0.6, size=10)

    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    _style_ax(ax)
    ax.bar([0, 1], [v1.mean(), v2.mean()], yerr=[v1.std(ddof=1), v2.std(ddof=1)],
           capsize=4, color=[c1, c2], alpha=0.8, width=0.55)
    ax.set_xticks([0, 1])
    ax.set_xticklabels([g1_name, g2_name])
    ax.set_ylabel("Error Rate (%)")
    ax.set_ylim(0, 11.5)

    # Diverse semantic phrasings claiming g2 > g1 (or g1 < g2)
    inverted_claims = [
        f"{g2_name} exhibited substantially higher values than {g1_name} across all runs.",
        f"{g1_name} remained consistently lower relative to {g2_name} throughout evaluation.",
        f"Switching to {g2_name} led to a marked increase over {g1_name}.",
        f"Compared with {g2_name}, {g1_name} showed a 40% reduction in the measured metric.",
    ]

    _save_case(
        fig,
        f"C5_{idx:02d}",
        {
            "case_id": f"C5_{idx:02d}",
            "category": "C5_direction_inversion",
            "is_consistent": False,
            "caption": f"Figure {idx+1}. Metric comparison between {g1_name} and {g2_name} (mean ± SD).",
            "main_text_claim": inverted_claims[idx % len(inverted_claims)],
            "ground_truth": {"plotted_higher": g1_name, "claimed_higher": g2_name},
        },
        rasterize_pdf=raster,
    )


def main() -> None:
    rng = np.random.default_rng(2026)
    for i in range(10):
        gen_c0(i, rng)
        gen_c1(i, rng)
        gen_c2(i, rng)
        gen_c3(i, rng)
        gen_c4(i, rng)
        gen_c5(i, rng)
    total = len(list(OUT_DIR.glob("*.json")))
    print(f"Generated {total} Benchmark v1 cases in: {OUT_DIR}")


if __name__ == "__main__":
    main()

"""MVP controllable benchmark generator for Chart-Text Statistical Consistency.

Generates paired scientific figures (vector PDF + 300 dpi PNG) and accompanying
text/caption JSON records covering five discrepancy categories (C1-C5) plus one
consistent control case (C0).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "mvp_samples"


def _save_case(
    fig: plt.Figure,
    case_id: str,
    metadata: dict[str, Any],
) -> None:
    """Save figure as PDF + PNG and write paired JSON metadata."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = OUT_DIR / f"{case_id}.pdf"
    png_path = OUT_DIR / f"{case_id}.png"
    json_path = OUT_DIR / f"{case_id}.json"

    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

    metadata["files"] = {"pdf": pdf_path.name, "png": png_path.name}
    json_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _style_ax(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def generate_c0_consistent(rng: np.random.Generator) -> None:
    """C0: Consistent control case (n=10, p=0.0021 matches '**', SD stated)."""
    ctrl = rng.normal(5.0, 0.8, size=10)
    treat = rng.normal(7.2, 0.9, size=10)

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    _style_ax(ax)
    means = [ctrl.mean(), treat.mean()]
    sds = [ctrl.std(ddof=1), treat.std(ddof=1)]

    ax.bar([0, 1], means, yerr=sds, capsize=4, color=["#6c757d", "#2a9d8f"], alpha=0.75, width=0.55)
    for i, vals in enumerate([ctrl, treat]):
        jitter = rng.uniform(-0.08, 0.08, size=len(vals))
        ax.scatter(np.full(len(vals), i) + jitter, vals, color="#264653", s=18, zorder=3)

    ax.plot([0, 0, 1, 1], [8.8, 9.0, 9.0, 8.8], color="black", lw=1.0)
    ax.text(0.5, 9.1, "**", ha="center", va="bottom", fontsize=11)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Control", "Treatment"])
    ax.set_ylabel("Expression Level (a.u.)")
    ax.set_ylim(0, 10.2)

    _save_case(
        fig,
        "C0_consistent_control",
        {
            "case_id": "C0_consistent_control",
            "discrepancy_type": "none",
            "is_consistent": True,
            "caption": "Figure 1. Treatment increases expression (n = 10 per group; mean ± SD; **p = 0.0021, two-sided t-test).",
            "main_text_claim": "Across n = 10 biological replicates per group, treatment elevated expression from 5.0 to 7.2 a.u. (p = 0.0021).",
            "ground_truth": {"n_control": 10, "n_treatment": 10, "star": "**", "p_value": 0.0021, "y_min": 0.0},
        },
    )


def generate_c1_n_mismatch(rng: np.random.Generator) -> None:
    """C1: Sample size mismatch (text claims n=12, plot shows 7 points)."""
    ctrl = rng.normal(4.8, 0.7, size=7)
    treat = rng.normal(6.9, 0.8, size=7)

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    _style_ax(ax)
    ax.bar([0, 1], [ctrl.mean(), treat.mean()], yerr=[ctrl.std(ddof=1), treat.std(ddof=1)],
           capsize=4, color=["#8d99ae", "#e76f51"], alpha=0.7, width=0.55)
    for i, vals in enumerate([ctrl, treat]):
        ax.scatter(np.full(len(vals), i) + rng.uniform(-0.08, 0.08, len(vals)), vals, color="#1d3557", s=20, zorder=3)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Vehicle", "Drug X"])
    ax.set_ylabel("Cell Viability (%)")
    ax.set_ylim(0, 10)

    _save_case(
        fig,
        "C1_sample_size_mismatch",
        {
            "case_id": "C1_sample_size_mismatch",
            "discrepancy_type": "sample_size_mismatch",
            "is_consistent": False,
            "caption": "Figure 2. Drug X effect on viability (n = 12 per group; mean ± SD).",
            "main_text_claim": "Twelve independent samples (n = 12) were analyzed in each group.",
            "ground_truth": {"claimed_n": 12, "plotted_points_per_group": 7},
        },
    )


def generate_c2_star_pvalue_conflict(rng: np.random.Generator) -> None:
    """C2: Significance star '***' (p<0.001) conflicts with text p=0.042."""
    g1 = rng.normal(10.0, 1.5, size=8)
    g2 = rng.normal(12.2, 1.6, size=8)

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    _style_ax(ax)
    ax.bar([0, 1], [g1.mean(), g2.mean()], yerr=[g1.std(ddof=1), g2.std(ddof=1)],
           capsize=4, color=["#adb5bd", "#457b9d"], alpha=0.8, width=0.55)
    ax.plot([0, 0, 1, 1], [15.2, 15.6, 15.6, 15.2], color="black", lw=1.0)
    ax.text(0.5, 15.7, "***", ha="center", va="bottom", fontsize=11)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Baseline", "Proposed"])
    ax.set_ylabel("Response Score")
    ax.set_ylim(0, 18)

    _save_case(
        fig,
        "C2_star_pvalue_conflict",
        {
            "case_id": "C2_star_pvalue_conflict",
            "discrepancy_type": "significance_star_pvalue_conflict",
            "is_consistent": False,
            "caption": "Figure 3. Score comparison between Baseline and Proposed (mean ± SD; ***p < 0.001).",
            "main_text_claim": "The proposed method achieved a marginally significant gain over baseline (p = 0.042).",
            "ground_truth": {"figure_star": "*** (<0.001)", "text_p_value": 0.042},
        },
    )


def generate_c3_truncated_axis() -> None:
    """C3: Truncated Y-axis (starts at 0.78) exaggerates a tiny 0.03 AUROC difference."""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    _style_ax(ax)
    ax.bar([0, 1], [0.80, 0.83], color=["#999999", "#d62828"], width=0.5)
    ax.set_ylim(0.78, 0.84)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Model A", "Ours"])
    ax.set_ylabel("AUROC")

    _save_case(
        fig,
        "C3_truncated_yaxis",
        {
            "case_id": "C3_truncated_yaxis",
            "discrepancy_type": "truncated_bar_yaxis",
            "is_consistent": False,
            "caption": "Figure 4. AUROC comparison showing dramatic improvement of Ours over Model A.",
            "main_text_claim": "Our model achieves an AUROC of 0.83 compared to 0.80 for Model A.",
            "ground_truth": {"y_min": 0.78, "y_max": 0.84, "visual_ratio": 2.5, "actual_ratio": 1.0375},
        },
    )


def generate_c4_concealed_distribution(rng: np.random.Generator) -> None:
    """C4: Bimodal distribution hidden behind bar+error bar without SD/SEM label."""
    a = rng.normal(5.0, 0.5, size=12)
    b = np.concatenate([rng.normal(2.0, 0.3, size=6), rng.normal(8.0, 0.3, size=6)])

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    _style_ax(ax)
    ax.bar([0, 1], [a.mean(), b.mean()], yerr=[a.std(ddof=1) / np.sqrt(12), b.std(ddof=1) / np.sqrt(12)],
           capsize=4, color=["#6c757d", "#e9c46a"], width=0.55)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Group A", "Group B"])
    ax.set_ylabel("Biomarker (ng/mL)")
    ax.set_ylim(0, 8)

    _save_case(
        fig,
        "C4_concealed_distribution",
        {
            "case_id": "C4_concealed_distribution",
            "discrepancy_type": "concealed_bimodal_and_missing_err_def",
            "is_consistent": False,
            "caption": "Figure 5. Biomarker levels in Group A and Group B (bars show mean with error bars).",
            "main_text_claim": "Group A and Group B exhibited identical biomarker distributions around 5.0 ng/mL.",
            "ground_truth": {"error_bar_definition_missing": True, "group_b_bimodal": True},
        },
    )


def generate_c5_direction_inversion(rng: np.random.Generator) -> None:
    """C5: Main text claims Group B > Group A, while plotted data shows Group A > Group B."""
    a = rng.normal(8.5, 0.6, size=10)
    b = rng.normal(5.2, 0.6, size=10)

    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    _style_ax(ax)
    ax.bar([0, 1], [a.mean(), b.mean()], yerr=[a.std(ddof=1), b.std(ddof=1)],
           capsize=4, color=["#2a9d8f", "#e76f51"], alpha=0.8, width=0.55)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Group A", "Group B"])
    ax.set_ylabel("Latency (ms)")
    ax.set_ylim(0, 11)

    _save_case(
        fig,
        "C5_direction_inversion",
        {
            "case_id": "C5_direction_inversion",
            "discrepancy_type": "effect_direction_inversion",
            "is_consistent": False,
            "caption": "Figure 6. Latency comparison between Group A and Group B (mean ± SD).",
            "main_text_claim": "Group B exhibited substantially higher latency than Group A across all runs.",
            "ground_truth": {"mean_A": round(float(a.mean()), 2), "mean_B": round(float(b.mean()), 2)},
        },
    )


def main() -> None:
    rng = np.random.default_rng(42)
    generate_c0_consistent(rng)
    generate_c1_n_mismatch(rng)
    generate_c2_star_pvalue_conflict(rng)
    generate_c3_truncated_axis()
    generate_c4_concealed_distribution(rng)
    generate_c5_direction_inversion(rng)
    print(f"Generated 6 MVP benchmark cases in: {OUT_DIR}")


if __name__ == "__main__":
    main()

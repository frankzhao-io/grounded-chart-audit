"""Generate publication-grade summary figures from Exp-05A/05B/06 results.

Produces figures/fig1_ablation_comparison.pdf and .png:
- Panel A: Overall Accuracy, F1, and C0 False-Positive-Free Rate across 4 methods
- Panel B: Per-category accuracy (C0-C5) comparing Track-1, Pure VLM, and Grounded Hybrid
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]
RES_PATH = BASE_DIR / "data" / "benchmark_v1_grounded_hybrid_results.json"
V1_HYB_PATH = BASE_DIR / "data" / "benchmark_v1_vlm_hybrid_results.json"
FIG_DIR = BASE_DIR / "figures"


def _parse_acc(val) -> float:
    if isinstance(val, dict):
        return float(val["accuracy"]) * 100.0
    # e.g. "10/10 (100.0%)"
    num, den = val.split()[0].split("/")
    return int(num) / int(den) * 100.0


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    res = json.loads(RES_PATH.read_text(encoding="utf-8"))
    v1_hyb = json.loads(V1_HYB_PATH.read_text(encoding="utf-8"))

    t1 = res["track1_rule_only"]
    pv = res["track2_pure_vlm"]
    hv1 = v1_hyb["hybrid_track1_plus_vlm"]
    gh = res["grounded_hybrid"]

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 8.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 2.9), dpi=300)

    # Panel A: Overall Accuracy, F1*100, and C0 Specificity (%)
    methods = ["Track-1\nOnly", "Pure\nVLM", "Hybrid\nv1", "Grounded\nHybrid"]
    accs = [m["accuracy"] * 100 for m in (t1, pv, hv1, gh)]
    f1s = [m["f1"] * 100 for m in (t1, pv, hv1, gh)]
    c0_specs = [_parse_acc(m["by_category"]["C0_consistent"]) for m in (t1, pv, hv1, gh)]

    x = np.arange(len(methods))
    w = 0.25
    ax1.bar(x - w, accs, width=w, label="Accuracy (%)", color="#457b9d")
    ax1.bar(x, f1s, width=w, label="F1 Score (%)", color="#2a9d8f")
    ax1.bar(x + w, c0_specs, width=w, label="C0 Specificity (%)", color="#e76f51")

    for xs, vals in [(x - w, accs), (x, f1s), (x + w, c0_specs)]:
        for xi, vi in zip(xs, vals):
            ax1.text(xi, vi + 1.5, f"{vi:.0f}", ha="center", va="bottom", fontsize=6.5)

    ax1.set_xticks(x)
    ax1.set_xticklabels(methods)
    ax1.set_ylim(0, 114)
    ax1.set_ylabel("Score (%)")
    ax1.set_title("a  Overall & Control Specificity (N=60)", loc="left", fontweight="bold", fontsize=9)
    ax1.legend(frameon=False, fontsize=7, loc="lower right")

    # Panel B: Per-category Accuracy
    cats = [
        ("C0_consistent", "C0\nControl"),
        ("C1_sample_size_mismatch", "C1\nn Mismatch"),
        ("C2_star_pvalue_conflict", "C2\nStar vs p"),
        ("C3_truncated_yaxis", "C3\nTrunc. Y"),
        ("C4_concealed_distribution", "C4\nConcealed"),
        ("C5_direction_inversion", "C5\nInversion"),
    ]
    x2 = np.arange(len(cats))
    w2 = 0.26
    t1_c = [_parse_acc(t1["by_category"][k]) for k, _ in cats]
    pv_c = [_parse_acc(pv["by_category"][k]) for k, _ in cats]
    gh_c = [_parse_acc(gh["by_category"][k]) for k, _ in cats]

    ax2.bar(x2 - w2, t1_c, width=w2, label="Track-1 Only", color="#8d99ae")
    ax2.bar(x2, pv_c, width=w2, label="Pure VLM", color="#e9c46a")
    ax2.bar(x2 + w2, gh_c, width=w2, label="Grounded Hybrid", color="#2a9d8f")

    ax2.set_xticks(x2)
    ax2.set_xticklabels([lbl for _, lbl in cats], fontsize=7)
    ax2.set_ylim(0, 114)
    ax2.set_ylabel("Category Accuracy (%)")
    ax2.set_title("b  Per-Category Breakdown", loc="left", fontweight="bold", fontsize=9)
    ax2.legend(frameon=False, fontsize=7, loc="lower right")

    fig.tight_layout(w_pad=2.0)
    pdf_out = FIG_DIR / "fig1_ablation_comparison.pdf"
    png_out = FIG_DIR / "fig1_ablation_comparison.png"
    fig.savefig(pdf_out, bbox_inches="tight")
    fig.savefig(png_out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {pdf_out} and {png_out}")


if __name__ == "__main__":
    main()

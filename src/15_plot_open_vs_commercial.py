"""Generate publication-grade Figure 2 comparing Open-Source Local 7B VLM vs. Gemini Flash-Lite.

Produces figures/fig2_open_vs_commercial.pdf and .png:
- Panel A: Pure VLM vs. Grounded Hybrid (Accuracy, F1, C0 Specificity) for Qwen2.5-VL-7B vs. Gemini 3.5 Flash-Lite
- Panel B: Grounded Hybrid accuracy split by Vector PDF (N=47) vs. Raster PDF (N=13)
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


BASE_DIR = Path(__file__).resolve().parents[1]
LOCAL_RES = BASE_DIR / "data" / "benchmark_v1_local_vlm_results.json"
GEMINI_RES = BASE_DIR / "data" / "benchmark_v1_grounded_hybrid_results.json"
FIG_DIR = BASE_DIR / "figures"


def _parse_acc(val) -> float:
    if isinstance(val, dict):
        return float(val["accuracy"]) * 100.0
    num, den = val.split()[0].split("/")
    return int(num) / int(den) * 100.0


def main() -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    loc = json.loads(LOCAL_RES.read_text(encoding="utf-8"))
    gem = json.loads(GEMINI_RES.read_text(encoding="utf-8"))

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 8.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 3.0), dpi=300, gridspec_kw={"width_ratios": [1.35, 1.0]})

    # Panel A: Overall Accuracy, F1*100, and C0 Specificity (%)
    configs = [
        ("Qwen2.5-VL-7B\nPure", loc["track2_pure_vlm"]),
        ("Gemini Flash-Lite\nPure", gem["track2_pure_vlm"]),
        ("Qwen2.5-VL-7B\nHybrid", loc["grounded_hybrid"]),
        ("Gemini Flash-Lite\nHybrid", gem["grounded_hybrid"]),
    ]
    labels = [c[0] for c in configs]
    accs = [c[1]["accuracy"] * 100 for c in configs]
    f1s = [c[1]["f1"] * 100 for c in configs]
    c0s = [_parse_acc(c[1]["by_category"]["C0_consistent"]) for c in configs]

    x = np.arange(len(configs))
    w = 0.25
    ax1.bar(x - w, accs, width=w, label="Accuracy (%)", color="#457b9d")
    ax1.bar(x, f1s, width=w, label="F1 Score (%)", color="#2a9d8f")
    ax1.bar(x + w, c0s, width=w, label="C0 Specificity (%)", color="#e76f51")

    for xs, vals in [(x - w, accs), (x, f1s), (x + w, c0s)]:
        for xi, vi in zip(xs, vals):
            ax1.text(xi, vi + 1.5, f"{vi:.0f}", ha="center", va="bottom", fontsize=6.5)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=7.5)
    ax1.set_ylim(0, 118)
    ax1.set_ylabel("Score (%)")
    ax1.set_title("a  Open-Source 7B vs. Commercial VLM (N=60)", loc="left", fontweight="bold", fontsize=9)
    ax1.legend(frameon=False, fontsize=7, loc="upper left", ncol=3)

    # Panel B: Vector PDF vs Raster PDF in Grounded Hybrid mode
    formats = ["Vector PDF\n(N=47)", "Raster PDF\n(N=13)"]
    loc_fmt = [
        _parse_acc(loc["grounded_hybrid"]["by_pdf_format"]["vector_pdf"]),
        _parse_acc(loc["grounded_hybrid"]["by_pdf_format"]["raster_pdf"]),
    ]
    gem_fmt = [
        _parse_acc(gem["grounded_hybrid"]["by_pdf_format"]["vector_pdf"]),
        _parse_acc(gem["grounded_hybrid"]["by_pdf_format"]["raster_pdf"]),
    ]
    x2 = np.arange(len(formats))
    w2 = 0.30
    b1 = ax2.bar(x2 - w2 / 2, loc_fmt, width=w2, label="Qwen2.5-VL-7B Hybrid", color="#264653")
    b2 = ax2.bar(x2 + w2 / 2, gem_fmt, width=w2, label="Gemini Flash-Lite Hybrid", color="#2a9d8f")

    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width() / 2, h + 1.5, f"{h:.1f}%", ha="center", va="bottom", fontsize=7)

    ax2.set_xticks(x2)
    ax2.set_xticklabels(formats, fontsize=8)
    ax2.set_ylim(0, 118)
    ax2.set_ylabel("Grounded Hybrid Accuracy (%)")
    ax2.set_title("b  Vector vs. Raster PDF Parity", loc="left", fontweight="bold", fontsize=9)
    ax2.legend(frameon=False, fontsize=7, loc="upper right")

    fig.tight_layout(w_pad=2.0)
    pdf_out = FIG_DIR / "fig2_open_vs_commercial.pdf"
    png_out = FIG_DIR / "fig2_open_vs_commercial.png"
    fig.savefig(pdf_out, bbox_inches="tight")
    fig.savefig(png_out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {pdf_out} and {png_out}")


if __name__ == "__main__":
    main()

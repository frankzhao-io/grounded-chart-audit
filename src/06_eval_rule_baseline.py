"""Evaluate Track-1 + Vector Geometry Auditor across the 60-case Benchmark v1.

Computes overall Accuracy, Precision, Recall, F1, per-category accuracy (C0-C5),
and Vector PDF vs. Raster-embedded PDF breakdown.
"""

from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
BENCH_DIR = BASE_DIR / "data" / "benchmark_v1"

# Load 04_vector_geometry_auditor dynamically
spec = importlib.util.spec_from_file_location(
    "vec_auditor", BASE_DIR / "src" / "04_vector_geometry_auditor.py"
)
vec_auditor = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(vec_auditor)


def main() -> None:
    # Point auditor's MVP_DIR to benchmark_v1
    vec_auditor.MVP_DIR = BENCH_DIR

    json_files = sorted(BENCH_DIR.glob("*.json"))
    if not json_files:
        raise RuntimeError(f"No benchmark files found in {BENCH_DIR}")

    records = []
    tp = fp = tn = fn = 0
    by_cat: dict[str, list[bool]] = defaultdict(list)
    by_format: dict[str, list[bool]] = defaultdict(list)

    for jp in json_files:
        meta = json.loads(jp.read_text(encoding="utf-8"))
        res = vec_auditor.audit_case(jp)
        gt_inc = not meta["is_consistent"]
        pred_inc = res["predicted_inconsistent"]
        ok = res["correct"]

        if gt_inc and pred_inc:
            tp += 1
        elif not gt_inc and pred_inc:
            fp += 1
        elif not gt_inc and not pred_inc:
            tn += 1
        else:
            fn += 1

        by_cat[meta["category"]].append(ok)
        fmt_key = "raster_pdf" if meta.get("is_raster_pdf") else "vector_pdf"
        by_format[fmt_key].append(ok)
        records.append({**res, "category": meta["category"], "is_raster_pdf": meta.get("is_raster_pdf", False)})

    total = len(records)
    acc = (tp + tn) / total
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    summary = {
        "total_cases": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "by_category": {
            cat: {"correct": sum(vals), "total": len(vals), "accuracy": round(sum(vals) / len(vals), 4)}
            for cat, vals in sorted(by_cat.items())
        },
        "by_pdf_format": {
            fmt: {"correct": sum(vals), "total": len(vals), "accuracy": round(sum(vals) / len(vals), 4)}
            for fmt, vals in sorted(by_format.items())
        },
    }

    print("=== Benchmark v1 (N=60) Track-1+Vector Baseline ===")
    print(f"Accuracy={acc:.3f} | Precision={prec:.3f} | Recall={rec:.3f} | F1={f1:.3f}")
    print("\nBy Category:")
    for cat, stats in summary["by_category"].items():
        print(f"  {cat:28s}: {stats['correct']:2d}/{stats['total']} ({stats['accuracy']*100:5.1f}%)")
    print("\nBy PDF Format:")
    for fmt, stats in summary["by_pdf_format"].items():
        print(f"  {fmt:12s}: {stats['correct']:2d}/{stats['total']} ({stats['accuracy']*100:5.1f}%)")

    out_path = BASE_DIR / "data" / "benchmark_v1_rule_baseline.json"
    out_path.write_text(json.dumps({"summary": summary, "records": records}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved full evaluation report to: {out_path}")


if __name__ == "__main__":
    main()

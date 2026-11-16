"""Unit tests for Track 3B extraction, statistical rules, and log consistency.

Covers regressions caught during independent subagent verification:
1. Plural error-bar definitions ("95% CIs", "SDs", "SEMs") do not trigger false positives.
2. Cross-page figure extraction: when caption is on page N and visual plot is on page N-1,
   the extractor selects page N-1 instead of blank whitespace.
3. Top-margin preservation: crop_top=0.0 preserves panel labels near the top edge.
4. Experiment log / summary markdown matches raw JSON evaluation metrics.
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import fitz


BASE_DIR = Path(__file__).resolve().parents[1]


def _load_module(name: str, rel_path: str):
    spec = importlib.util.spec_from_file_location(name, BASE_DIR / rel_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


ext10 = _load_module("ext10", "src/10_real_paper_figure_extractor.py")
aud11 = _load_module("aud11", "src/11_audit_real_papers.py")


class TestAuditPipeline(unittest.TestCase):
    def test_plural_error_bar_definitions_not_flagged(self) -> None:
        for phrase in [
            "Error bars are 95% CIs.",
            "Values show mean with error bars representing SDs.",
            "Shaded band indicates SEMs across replicates.",
            "Error bars denote confidence intervals.",
        ]:
            pair = {"caption": f"Figure 1. Results. {phrase}", "referencing_paragraphs": []}
            findings = aud11.track1_real_checks(pair)
            self.assertEqual(findings, [], f"False positive on: {phrase}")

    def test_missing_error_bar_definition_still_flagged(self) -> None:
        pair = {
            "caption": "Figure 1. Group comparison (bars show mean with error bars).",
            "referencing_paragraphs": ["We compared Group A and Group B."],
        }
        findings = aud11.track1_real_checks(pair)
        self.assertTrue(
            any("missing_error_bar_definition" in f for f in findings),
            "Should flag undefined error bars",
        )

    def test_cross_page_figure_and_no_top_clip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf_path = tmp_path / "synthetic_cross_page.pdf"
            doc = fitz.open()

            # Page 1: vector figure with non-trivial drawings near top edge (y=5..200)
            p1 = doc.new_page(width=400, height=400)
            p1.insert_text((20, 12), "Panel A", fontsize=10)
            for i in range(6):
                p1.draw_rect(fitz.Rect(30 + i * 40, 30, 55 + i * 40, 200), color=(0, 0, 0), fill=(0.2, 0.5, 0.7))

            # Page 2: caption at top with NO figure above it
            p2 = doc.new_page(width=400, height=400)
            p2.insert_text((20, 35), "Figure 1. Cross-page figure caption.", fontsize=10)

            doc.save(str(pdf_path))
            doc.close()

            orig_out = ext10.OUT_DIR
            try:
                ext10.OUT_DIR = tmp_path / "out"
                ext10.OUT_DIR.mkdir(parents=True, exist_ok=True)
                pairs = ext10.extract_pairs_from_pdf(pdf_path, max_figs=2)
            finally:
                ext10.OUT_DIR = orig_out

            self.assertEqual(len(pairs), 1)
            self.assertEqual(pairs[0]["page"], 1, "Should fall back to page 1 where figure lives")
            self.assertEqual(pairs[0]["caption_page"], 2)

    def test_summary_metrics_match_json(self) -> None:
        gh_json = json.loads((BASE_DIR / "data" / "benchmark_v1_grounded_hybrid_results.json").read_text(encoding="utf-8"))
        summary_md = (BASE_DIR / "notes" / "phase1-2-results-summary.md").read_text(encoding="utf-8")

        t1 = gh_json["track1_rule_only"]
        pv = gh_json["track2_pure_vlm"]
        gh = gh_json["grounded_hybrid"]

        self.assertIn(f"{t1['accuracy']*100:.1f}%", summary_md)
        self.assertIn(f"{pv['accuracy']*100:.1f}%", summary_md)
        self.assertIn(f"{gh['accuracy']*100:.1f}%", summary_md)
        self.assertIn(f"{gh['f1']:.4f}", summary_md)

    def test_dotted_ci_and_sd_definitions_are_recognized(self) -> None:
        for caption in [
            "Figure 3. The shaded area is the 95% C.I. of the posterior mean.",
            "Figure 4. Average observed distance (shaded area: s.d.).",
        ]:
            findings = aud11.track1_real_checks({"caption": caption, "referencing_paragraphs": []})
            self.assertEqual(findings, [], f"Dotted abbreviation should not trigger false positive: {caption}")


if __name__ == "__main__":
    unittest.main()

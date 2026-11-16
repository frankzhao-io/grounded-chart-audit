"""Exp-15: End-to-End Two-Stage Audit on 60 Open-Access bioRxiv Biomedical Preprints.

Fetches 60 recent experimental biology preprints from api.biorxiv.org
(cell biology, neuroscience, immunology, cancer biology, pharmacology, etc.),
downloads valid PDFs, extracts figure-caption-prose pairs, runs zero-cost Track-1
deterministic triage, and sends all flagged candidates to local Ollama qwen2.5vl:7b
for Track-2 visual-text verification.
"""

from __future__ import annotations

import importlib.util
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
PDF_DIR = BASE_DIR / "data" / "biorxiv_pdfs"
PAIR_DIR = BASE_DIR / "data" / "biorxiv_pairs"
OUT_JSON = BASE_DIR / "data" / "biorxiv_biomed_audit.json"

TARGET_CATEGORIES = {
    "cell biology",
    "immunology",
    "neuroscience",
    "cancer biology",
    "pharmacology and toxicology",
    "molecular biology",
    "microbiology",
    "pathology",
    "physiology",
}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; track3-ai4science-research/0.1)"}


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, BASE_DIR / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


ext10 = _load("ext10", "src/10_real_paper_figure_extractor.py")
aud11 = _load("aud11", "src/11_audit_real_papers.py")
loc13 = _load("loc13", "src/13_track2_local_vlm_audit.py")


def fetch_biorxiv_papers(target_count: int = 60) -> list[dict[str, str]]:
    """Fetch recent experimental biology preprints from bioRxiv API."""
    papers: list[dict[str, str]] = []
    seen: set[str] = set()
    cursor = 0

    while len(papers) < target_count and cursor < 1500:
        url = f"https://api.biorxiv.org/details/biorxiv/2026-10-01/2026-10-31/{cursor}/json"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        collection = resp.json().get("collection", [])
        if not collection:
            break

        for item in collection:
            cat = (item.get("category") or "").strip().lower()
            doi = item.get("doi", "").strip()
            ver = item.get("version", "1")
            if cat in TARGET_CATEGORIES and doi and doi not in seen:
                seen.add(doi)
                safe_id = doi.replace("/", "_") + f"v{ver}"
                papers.append({
                    "paper_id": safe_id,
                    "doi": doi,
                    "category": cat,
                    "title": item.get("title", ""),
                    "date": item.get("date", ""),
                    "pdf_url": f"https://www.biorxiv.org/content/{doi}v{ver}.full.pdf",
                })
                if len(papers) >= target_count:
                    break
        cursor += len(collection)

    return papers


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    PAIR_DIR.mkdir(parents=True, exist_ok=True)
    ext10.OUT_DIR = PAIR_DIR

    papers = fetch_biorxiv_papers(target_count=60)
    print(f"Fetched {len(papers)} bioRxiv experimental biology metadata entries.")

    downloaded = 0
    parsed_papers = 0
    total_pairs = 0
    flagged_cases: list[dict[str, Any]] = []

    for idx, p in enumerate(papers, 1):
        pid = p["paper_id"]
        pdf_path = PDF_DIR / f"{pid}.pdf"
        if not pdf_path.exists():
            try:
                r = requests.get(p["pdf_url"], headers=HEADERS, timeout=45)
                r.raise_for_status()
                if not r.content.startswith(b"%PDF"):
                    print(f"[{idx}/{len(papers)}] Skip {pid} (not a PDF)")
                    continue
                pdf_path.write_bytes(r.content)
                time.sleep(0.3)
            except Exception as exc:
                print(f"[{idx}/{len(papers)}] Skip {pid} ({type(exc).__name__})")
                continue
        downloaded += 1

        try:
            pairs = ext10.extract_pairs_from_pdf(pdf_path, max_figs=6)
        except Exception as exc:
            print(f"[{idx}/{len(papers)}] Parse error {pid} ({type(exc).__name__})")
            continue

        parsed_papers += 1
        total_pairs += len(pairs)
        paper_flags = 0

        for pair in pairs:
            findings = aud11.track1_real_checks(pair)
            if not findings:
                continue
            paper_flags += 1
            img_path = PAIR_DIR / pair["image_file"]
            vlm_audit = loc13.audit_case_ollama(
                image_path=img_path,
                caption=pair["caption"],
                track1_findings=findings,
            )
            verdict = vlm_audit["vlm_result"].get("track1_verdict", "parse_error")
            print(f"  -> FLAG {pid} Fig {pair['figure_num']}: {findings} | VLM={verdict} ({vlm_audit['elapsed_sec']}s)")
            flagged_cases.append({
                "paper_id": pid,
                "doi": p["doi"],
                "category": p["category"],
                "title": p["title"],
                "figure_num": pair["figure_num"],
                "image_file": pair["image_file"],
                "track1_findings": findings,
                "caption": pair["caption"],
                "vlm_audit": vlm_audit,
            })

        print(f"[{idx}/{len(papers)}] {pid} ({p['category']}): {len(pairs)} figs, {paper_flags} flagged")

    verdict_counts = Counter(
        c["vlm_audit"]["vlm_result"].get("track1_verdict", "parse_error")
        for c in flagged_cases
    )

    report = {
        "source": "bioRxiv Open Access",
        "vlm_model": loc13.DEFAULT_MODEL,
        "papers_targeted": len(papers),
        "papers_downloaded": downloaded,
        "papers_parsed": parsed_papers,
        "total_figure_pairs": total_pairs,
        "track1_flagged_count": len(flagged_cases),
        "verdict_counts": dict(verdict_counts),
        "flagged_cases": flagged_cases,
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n=== Exp-15 Complete ===")
    print(f"Papers: {parsed_papers}/{len(papers)} parsed | Total figure pairs: {total_pairs}")
    print(f"Track-1 flagged: {len(flagged_cases)} | Track-2 verdicts: {dict(verdict_counts)}")
    print(f"Saved report to: {OUT_JSON}")


if __name__ == "__main__":
    main()

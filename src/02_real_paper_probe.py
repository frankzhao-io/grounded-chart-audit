"""Probe real open-access papers from arXiv to inspect figure/stat characteristics.

Downloads a small sample of recent quantitative papers, extracts text and image
counts via pypdf, and scans for statistical mentions (p-values, sample sizes n,
SD/SEM definitions, Figure captions) to ground our 3B audit design.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pypdf
import requests


OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "real_papers"
ARXIV_API = "http://export.arxiv.org/api/query"

STAT_PATTERNS = {
    "p_values": re.compile(r"\bp\s*[<=>≤≥]\s*0?\.\d+", re.I),
    "sample_size_n": re.compile(r"\bn\s*=\s*\d+", re.I),
    "sd_or_sem": re.compile(r"\b(?:SD|SEM|s\.d\.|s\.e\.m\.|standard deviation|standard error)\b", re.I),
    "figure_refs": re.compile(r"\b(?:Figure|Fig\.)\s*\d+", re.I),
}


def fetch_arxiv_papers(query: str = "cat:q-bio.QM AND (p-value OR benchmark)", max_results: int = 5) -> list[dict]:
    """Fetch paper metadata from arXiv Atom API."""
    resp = requests.get(
        ARXIV_API,
        params={"search_query": query, "start": 0, "max_results": max_results, "sortBy": "submittedDate", "sortOrder": "descending"},
        timeout=30,
    )
    resp.raise_for_status()
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)
    papers = []
    for entry in root.findall("atom:entry", ns):
        arxiv_url = entry.findtext("atom:id", "", ns)
        arxiv_id = arxiv_url.rsplit("/", 1)[-1].replace("/", "_")
        title = " ".join(entry.findtext("atom:title", "", ns).split())
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        papers.append({"arxiv_id": arxiv_id, "title": title, "pdf_url": pdf_url})
    return papers


def inspect_pdf(pdf_path: Path) -> dict:
    """Inspect page count, embedded raster images, and statistical mentions."""
    reader = pypdf.PdfReader(str(pdf_path))
    full_text = []
    image_count = 0
    for page in reader.pages:
        full_text.append(page.extract_text() or "")
        try:
            image_count += len(page.images)
        except Exception:
            pass
    joined = "\n".join(full_text)
    stats = {}
    for key, pat in STAT_PATTERNS.items():
        matches = pat.findall(joined)
        stats[key] = {"count": len(matches), "samples": matches[:5]}
    return {
        "pages": len(reader.pages),
        "embedded_raster_images": image_count,
        "text_chars": len(joined),
        "stats_found": stats,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    papers = fetch_arxiv_papers(max_results=5)
    summary = []
    for paper in papers:
        pdf_path = OUT_DIR / f"{paper['arxiv_id']}.pdf"
        if not pdf_path.exists():
            print(f"Downloading {paper['arxiv_id']}...")
            r = requests.get(paper["pdf_url"], timeout=60, headers={"User-Agent": "track3-ai4science-probe/0.1"})
            r.raise_for_status()
            pdf_path.write_bytes(r.content)
        info = inspect_pdf(pdf_path)
        record = {**paper, **info}
        summary.append(record)
        print(
            f"[{paper['arxiv_id']}] pages={info['pages']}, "
            f"raster_imgs={info['embedded_raster_images']}, "
            f"p_vals={info['stats_found']['p_values']['count']}, "
            f"n_mentions={info['stats_found']['sample_size_n']['count']}, "
            f"sd_sem={info['stats_found']['sd_or_sem']['count']}"
        )

    out_json = OUT_DIR / "probe_summary.json"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved probe summary to: {out_json}")


if __name__ == "__main__":
    main()

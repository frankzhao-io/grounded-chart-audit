"""Exp-11: Large-scale zero-cost Track-1 triage across 25 recent arXiv quantitative papers.

Fetches 25 recent arXiv papers (q-bio.QM + stat.AP), extracts figure-caption-prose
pairs using 10_real_paper_figure_extractor, and runs Track-1 deterministic checks
from 11_audit_real_papers to surface real-world candidate anomalies at zero VLM cost.
"""

from __future__ import annotations

import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parents[1]
PDF_DIR = BASE_DIR / "data" / "real_papers_scale"
PAIR_DIR = BASE_DIR / "data" / "real_paper_pairs_scale"
OUT_JSON = BASE_DIR / "data" / "real_paper_scale_triage.json"

ARXIV_API = "http://export.arxiv.org/api/query"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, BASE_DIR / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


ext10 = _load("ext10", "src/10_real_paper_figure_extractor.py")
aud11 = _load("aud11", "src/11_audit_real_papers.py")


import time


def fetch_papers(max_results: int = 25) -> list[dict]:
    query = "(cat:q-bio.QM OR cat:stat.AP) AND (p-value OR error bar OR confidence interval)"
    headers = {"User-Agent": "track3-ai4science-research/0.1 (mailto:research@example.org)"}
    for attempt in range(2):
        try:
            resp = requests.get(
                ARXIV_API,
                params={
                    "search_query": query,
                    "start": 0,
                    "max_results": max_results,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 429:
                time.sleep(3)
                continue
            if resp.ok:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                root = ET.fromstring(resp.text)
                papers = []
                for entry in root.findall("atom:entry", ns):
                    arxiv_url = entry.findtext("atom:id", "", ns)
                    arxiv_id = arxiv_url.rsplit("/", 1)[-1].replace("/", "_")
                    title = " ".join(entry.findtext("atom:title", "", ns).split())
                    papers.append({
                        "arxiv_id": arxiv_id,
                        "title": title,
                        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                    })
                return papers
        except requests.exceptions.RequestException as exc:
            print(f"arXiv API error ({type(exc).__name__}); retrying/falling back...")
            time.sleep(2)

    # Fallback 1: OpenAlex open-access papers with direct PDF URLs
    print("arXiv API unavailable; falling back to OpenAlex open-access papers...")
    papers = []
    seen_ids = set()
    try:
        oa_resp = requests.get(
            "https://api.openalex.org/works",
            params={
                "search": "error bar p-value statistical",
                "filter": "is_oa:true,type:article",
                "per-page": 50,
            },
            headers=headers,
            timeout=30,
        )
        oa_resp.raise_for_status()
        for w in oa_resp.json().get("results", []):
            oa_url = (w.get("primary_location") or {}).get("pdf_url") or (w.get("open_access") or {}).get("oa_url")
            if oa_url and oa_url.lower().endswith(".pdf"):
                wid = w["id"].rsplit("/", 1)[-1]
                if wid not in seen_ids:
                    seen_ids.add(wid)
                    papers.append({"arxiv_id": wid, "title": w.get("title", ""), "pdf_url": oa_url})
                    if len(papers) >= max_results:
                        break
    except Exception as exc:
        print(f"OpenAlex fallback failed: {exc}")

    # Fallback 2: Europe PMC open-access PDFs
    if len(papers) < max_results:
        print(f"Fetching remaining papers from Europe PMC (have {len(papers)}/{max_results})...")
        try:
            epmc_resp = requests.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                params={
                    "query": 'OPEN_ACCESS:Y AND ("error bars" OR "confidence interval") AND "p-value"',
                    "format": "json",
                    "pageSize": max_results * 2,
                },
                headers=headers,
                timeout=30,
            )
            epmc_resp.raise_for_status()
            for r in epmc_resp.json().get("resultList", {}).get("result", []):
                pmcid = r.get("pmcid")
                if pmcid and pmcid not in seen_ids:
                    seen_ids.add(pmcid)
                    papers.append({
                        "arxiv_id": pmcid,
                        "title": r.get("title", ""),
                        "pdf_url": f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf",
                    })
                    if len(papers) >= max_results:
                        break
        except Exception as exc:
            print(f"Europe PMC fallback failed: {exc}")
    return papers


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    PAIR_DIR.mkdir(parents=True, exist_ok=True)

    papers = fetch_papers(max_results=25)
    print(f"Fetched {len(papers)} arXiv metadata entries.")

    ext10.OUT_DIR = PAIR_DIR
    all_pairs = []
    flagged_pairs = []

    for idx, p in enumerate(papers, 1):
        pdf_path = PDF_DIR / f"{p['arxiv_id']}.pdf"
        if not pdf_path.exists():
            try:
                r = requests.get(p["pdf_url"], timeout=45, headers={"User-Agent": "track3-ai4science/0.1"})
                r.raise_for_status()
                pdf_path.write_bytes(r.content)
            except Exception as exc:
                print(f"[{idx}/{len(papers)}] Skip {p['arxiv_id']} ({type(exc).__name__})")
                continue

        try:
            pairs = ext10.extract_pairs_from_pdf(pdf_path, max_figs=6)
        except Exception as exc:
            print(f"[{idx}/{len(papers)}] Parse error {p['arxiv_id']} ({type(exc).__name__})")
            continue

        for pair in pairs:
            findings = aud11.track1_real_checks(pair)
            pair["track1_findings"] = findings
            all_pairs.append(pair)
            if findings:
                flagged_pairs.append(pair)

        print(f"[{idx}/{len(papers)}] {p['arxiv_id']}: {len(pairs)} figs extracted")

    summary = {
        "papers_targeted": len(papers),
        "total_figure_pairs": len(all_pairs),
        "track1_flagged_count": len(flagged_pairs),
        "flagged_cases": [
            {
                "paper_id": f["paper_id"],
                "figure_num": f["figure_num"],
                "image_file": f["image_file"],
                "findings": f["track1_findings"],
                "caption": f["caption"],
            }
            for f in flagged_pairs
        ],
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTriage Complete: {len(all_pairs)} pairs scanned, {len(flagged_pairs)} flagged by Track-1.")
    print(f"Saved triage report to: {OUT_JSON}")


if __name__ == "__main__":
    main()

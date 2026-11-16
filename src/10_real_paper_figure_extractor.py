"""Phase 3 Step 1: Extract Figure + Caption + Referencing Prose pairs from real PDFs.

Scans real arXiv PDFs in data/real_papers/ using PyMuPDF (fitz):
- Locates Figure caption blocks (e.g., "Figure 1.", "Fig. 2:")
- Renders the corresponding figure page (or cropped region above the caption) as PNG
- Extracts all main-text paragraphs referencing that Figure number
- Saves structured JSON + PNG pairs into data/real_paper_pairs/
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import fitz


BASE_DIR = Path(__file__).resolve().parents[1]
REAL_DIR = BASE_DIR / "data" / "real_papers"
OUT_DIR = BASE_DIR / "data" / "real_paper_pairs"

CAPTION_START_RE = re.compile(r"^(?:Figure|Fig\.?)\s*(\d+)\s*[:.]", re.I)


def _has_visual_content_above(page: fitz.Page, y_limit: float) -> bool:
    """Return True if the page region [0, y_limit] has embedded images or non-trivial drawings."""
    if y_limit <= 40.0:
        return False
    # Check embedded images overlapping [0, y_limit]
    for img in page.get_images(full=True):
        xref = img[0]
        for rect in page.get_image_rects(xref):
            if rect.y0 < y_limit and rect.height > 20.0:
                return True
    # Check vector drawings (exclude tiny hairlines / page backgrounds)
    page_w, page_h = page.rect.width, page.rect.height
    non_trivial = 0
    for d in page.get_drawings():
        r = d["rect"]
        if r.width > page_w * 0.9 and r.height > page_h * 0.9:
            continue
        if r.y0 < y_limit and (r.width > 5.0 or r.height > 5.0):
            non_trivial += 1
            if non_trivial >= 5:
                return True
    return False


def extract_pairs_from_pdf(pdf_path: Path, max_figs: int = 8) -> list[dict]:
    doc = fitz.open(str(pdf_path))
    paper_id = pdf_path.stem

    # Collect all text blocks across all pages for cross-referencing
    all_blocks: list[tuple[int, str]] = []
    for pno, page in enumerate(doc):
        for b in page.get_text("blocks"):
            txt = " ".join(b[4].split())
            if txt:
                all_blocks.append((pno, txt))

    pairs: list[dict] = []
    seen_nums: set[str] = set()

    for pno, page in enumerate(doc):
        blocks = page.get_text("blocks")
        for b in blocks:
            x0, y0, x1, y1, raw_txt = b[0], b[1], b[2], b[3], b[4]
            txt = " ".join(raw_txt.split())
            m = CAPTION_START_RE.match(txt)
            if not m:
                continue
            fig_num = m.group(1)
            if fig_num in seen_nums:
                continue
            seen_nums.add(fig_num)

            page_rect = page.rect
            fig_page_no = pno

            # If caption is near top or region above caption has no figure content, check previous page
            if not _has_visual_content_above(page, y0) and pno > 0 and _has_visual_content_above(doc[pno - 1], doc[pno - 1].rect.height):
                fig_page_no = pno - 1
                fig_page = doc[fig_page_no]
                clip = fitz.Rect(0, 0.0, fig_page.rect.width, fig_page.rect.height)
                pix = fig_page.get_pixmap(clip=clip, dpi=180)
            else:
                crop_bottom = min(page_rect.height, y1 + 10.0) if y0 > page_rect.height * 0.25 else page_rect.height
                clip = fitz.Rect(0, 0.0, page_rect.width, crop_bottom)
                pix = page.get_pixmap(clip=clip, dpi=180)

            img_name = f"{paper_id}_fig{fig_num}_p{fig_page_no+1}.png"
            img_path = OUT_DIR / img_name
            pix.save(str(img_path))

            # Find main-text paragraphs referencing Figure/Fig. <fig_num>
            ref_pat = re.compile(rf"\b(?:Figure|Fig\.?)\s*{re.escape(fig_num)}\b", re.I)
            ref_paras = [
                bt for _, bt in all_blocks
                if ref_pat.search(bt) and bt != txt and len(bt) > 40
            ]

            pair = {
                "paper_id": paper_id,
                "figure_num": fig_num,
                "page": fig_page_no + 1,
                "caption_page": pno + 1,
                "image_file": img_name,
                "caption": txt,
                "referencing_paragraphs": ref_paras[:5],
            }
            pairs.append(pair)
            if len(pairs) >= max_figs:
                return pairs

    return pairs


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_pairs = []
    for pdf_path in sorted(REAL_DIR.glob("*.pdf")):
        pairs = extract_pairs_from_pdf(pdf_path, max_figs=5)
        all_pairs.extend(pairs)
        print(f"[{pdf_path.name}] extracted {len(pairs)} figure-text pairs")

    manifest = OUT_DIR / "real_pairs_manifest.json"
    manifest.write_text(json.dumps(all_pairs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTotal real pairs extracted: {len(all_pairs)} -> {manifest}")


if __name__ == "__main__":
    main()

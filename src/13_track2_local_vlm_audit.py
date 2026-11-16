"""Track-2 Local VLM Audit via Ollama (qwen2.5vl:7b).

Reads Track-1 flagged figure-caption pairs from real_paper_scale_triage.json,
resizes oversized images to <=1280px max dimension to stay safely within
10 GB VRAM (e.g., RTX 3080), queries local Ollama /api/chat for structured
visual-text verification, and records verdict + per-image latency.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TRIAGE_JSON = ROOT / "data" / "real_paper_scale_triage.json"
PAIR_DIR = ROOT / "data" / "real_paper_pairs_scale"
OUT_JSON = ROOT / "data" / "track2_local_vlm_audit.json"

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
DEFAULT_MODEL = os.environ.get("OLLAMA_VLM_MODEL", "qwen2.5vl:7b")
MAX_IMAGE_SIDE = 1280

SYSTEM_PROMPT = (
    "You are a meticulous scientific figure-text statistical auditor. "
    "Inspect the figure image and its caption/Track-1 flag, then respond ONLY with a valid JSON object "
    "matching this exact schema:\n"
    "{\n"
    '  "has_error_bars_or_bands": boolean,\n'
    '  "shaded_region_is_uncertainty": boolean or null,\n'
    '  "has_significance_markers": boolean,\n'
    '  "definition_deferred_to_appendix": boolean,\n'
    '  "track1_verdict": "confirmed_issue" | "false_positive" | "deferred_to_other_section" | "uncertain",\n'
    '  "reasoning": "1-2 concise sentences citing visual evidence from the figure and caption"\n'
    "}\n\n"
    "Decision rules for track1_verdict:\n"
    "- Set definition_deferred_to_appendix=true ONLY if the caption explicitly refers to an appendix, "
    "supplement, or another section for the error bar/band definition; if true, track1_verdict MUST be "
    '"deferred_to_other_section".\n'
    "- If the Track-1 flag is missing_error_bar_definition and has_error_bars_or_bands is false "
    "(and shaded_region_is_uncertainty is not true, e.g. 'shaded region' only highlights a background zone), "
    'track1_verdict MUST be "false_positive".\n'
    "- Set track1_verdict to \"confirmed_issue\" ONLY when error bars/uncertainty bands or significance "
    "markers are visually present AND their statistical definition is genuinely missing without deferral."
)


def encode_image_b64(image_path: Path, max_side: int = MAX_IMAGE_SIDE) -> tuple[str, tuple[int, int]]:
    """Load PNG/JPG, downscale if > max_side, and return (base64_str, (w, h))."""
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("ascii"), img.size


def parse_json_response(raw_text: str) -> dict[str, Any]:
    """Extract JSON object from model output, tolerating markdown code fences."""
    cleaned = raw_text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if brace:
            cleaned = brace.group(0)
    return json.loads(cleaned)


def audit_case_ollama(
    image_path: Path,
    caption: str,
    track1_findings: list[str],
    model: str = DEFAULT_MODEL,
    timeout: int = 120,
) -> dict[str, Any]:
    """Send one figure-caption pair to local Ollama VLM and return parsed audit + timing."""
    img_b64, resized_dim = encode_image_b64(image_path)
    user_prompt = (
        f"Track-1 automated flag(s): {json.dumps(track1_findings, ensure_ascii=False)}\n"
        f"Figure caption:\n{caption}\n\n"
        "Verify visually whether the figure actually contains statistical error bars / uncertainty bands "
        "or significance markers, whether any mentioned 'shaded region' is a statistical uncertainty band "
        "vs. a background highlight, and whether the caption defers the definition to an appendix/supplement."
    )

    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt, "images": [img_b64]},
        ],
    }

    t0 = time.perf_counter()
    resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    resp.raise_for_status()
    elapsed = time.perf_counter() - t0

    data = resp.json()
    raw_content = data.get("message", {}).get("content", "")
    try:
        parsed = parse_json_response(raw_content)
    except Exception as exc:
        parsed = {"parse_error": str(exc), "raw_content": raw_content}

    return {
        "image_dim_sent": list(resized_dim),
        "elapsed_sec": round(elapsed, 2),
        "eval_count": data.get("eval_count"),
        "prompt_eval_count": data.get("prompt_eval_count"),
        "vlm_result": parsed,
    }


def main() -> None:
    if not TRIAGE_JSON.exists():
        raise FileNotFoundError(f"Missing triage report: {TRIAGE_JSON}")

    triage = json.loads(TRIAGE_JSON.read_text(encoding="utf-8"))
    flagged = triage.get("flagged_cases", [])
    print(f"Loaded {len(flagged)} Track-1 flagged case(s) from {TRIAGE_JSON.name}.")

    results = []
    for idx, case in enumerate(flagged, 1):
        img_path = PAIR_DIR / case["image_file"]
        if not img_path.exists():
            print(f"[{idx}/{len(flagged)}] Missing image: {img_path}")
            continue

        print(f"[{idx}/{len(flagged)}] Auditing {case['paper_id']} Fig {case['figure_num']} via {DEFAULT_MODEL}...")
        audit = audit_case_ollama(
            image_path=img_path,
            caption=case.get("caption", ""),
            track1_findings=case.get("findings", []),
        )
        verdict = audit["vlm_result"].get("track1_verdict", "parse_error")
        print(f"  -> verdict={verdict} ({audit['elapsed_sec']}s)")
        results.append({
            "paper_id": case["paper_id"],
            "figure_num": case["figure_num"],
            "image_file": case["image_file"],
            "track1_findings": case.get("findings", []),
            **audit,
        })

    report = {
        "model": DEFAULT_MODEL,
        "ollama_url": OLLAMA_URL,
        "cases_audited": len(results),
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved Track-2 local VLM audit report to: {OUT_JSON}")


if __name__ == "__main__":
    main()

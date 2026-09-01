"""OCR a screenshot (optionally a region) -> (text, Citation).

Tesseract does the reading; the agent interprets the text but never invents it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytesseract
from PIL import Image

from iqr.schemas.evidence_graph import EvidenceGraph
from iqr.schemas.finding import Citation
from iqr.tools.citation import image_citation


class ImageNotFound(Exception):
    pass


def ocr_read(graph: EvidenceGraph, image_hash: str,
             region: tuple[int, int, int, int] | None = None) -> tuple[str, Citation]:
    fact = graph.images.get(image_hash)
    if fact is None:
        raise ImageNotFound(f"image {image_hash[:12]} not in evidence graph")
    with Image.open(Path(fact.stored_path)) as im:
        if region:
            im = im.crop(region)
        # deterministic config: single model, no dynamic page segmentation surprises
        text = pytesseract.image_to_string(im, config="--psm 6")
    return text.strip(), image_citation(image_hash, region)


def find_labeled_number(text: str, label: str) -> float | None:
    """Pull the number that follows a label in OCR text, e.g. 'Total Qty: 4,820'."""
    pattern = re.escape(label) + r"[^0-9\-]*(-?[\d,]+(?:\.\d+)?)"
    m = re.search(pattern, text, flags=re.IGNORECASE)
    if not m:
        return None
    return float(m.group(1).replace(",", ""))

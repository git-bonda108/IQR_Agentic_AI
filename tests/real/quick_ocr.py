"""Direct OCR quality test on real HP screenshots - no full ingest needed."""
import io, zipfile
from pathlib import Path
from PIL import Image
import pytesseract

BASE = Path("data/input/iqr_build_package/03_source_evidence")
TARGETS = [
    (BASE / "control_10075_emr_review/SS_Webi_-_Revenue_Validation_Q2_26_-_JU.docx", 2),
    (BASE / "control_23024_rebate_calc/SOX_404_Buy_Sell_Control_2_Updated.docx", 2),
]
for path, n in TARGETS:
    print(f"\n=== {path.name} ===", flush=True)
    with zipfile.ZipFile(path) as zf:
        media = [(i.file_size, i.filename) for i in zf.infolist()
                 if i.filename.startswith("word/media/")]
        media.sort(reverse=True)
        print(f"media files: {len(media)}, largest: {media[0] if media else None}", flush=True)
        for size, name in media[:n]:
            img = Image.open(io.BytesIO(zf.read(name)))
            text = pytesseract.image_to_string(img)
            words = text.split()
            print(f"\n-- {name} ({size:,}B {img.size[0]}x{img.size[1]}) "
                  f"OCR words={len(words)}", flush=True)
            print("   " + " ".join(words[:60]), flush=True)

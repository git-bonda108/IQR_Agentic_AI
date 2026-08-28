"""Generate HP-branded diagrams (PNG) and walkthrough GIFs for the IQR design
document. Pure PIL - no external design tools.

HP visual identity (brandcentral): Electric Blue primary, black typography,
white space; Power Storm and Orange Bloom as sparing accents.
Fonts: HP Forma DJR is proprietary; Arial substitutes cleanly.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "assets"
OUT.mkdir(parents=True, exist_ok=True)

# ---- HP palette ----
BLUE = "#0096D6"        # Electric Blue
BLUE_DARK = "#00537A"   # deep tone of Electric Blue for bars
TINT = "#EAF6FC"        # 8% blue tint
TINT2 = "#F5FBFE"
ORANGE = "#FF585D"      # Orange Bloom (Pantone 178 C)
STORM = "#4E7C96"       # Power Storm
INK = "#1A1A1A"
GRAY = "#6E6E73"
LINE = "#D6DEE4"
WHITE = "#FFFFFF"
GREEN = "#1E8E3E"       # verdict pass (functional color)
RED = "#C5221F"         # verdict fail (functional color)

_FONTS: dict = {}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in _FONTS:
        cands = (["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                  "/Library/Fonts/Arial Bold.ttf"] if bold else
                 ["/System/Library/Fonts/Supplemental/Arial.ttf",
                  "/Library/Fonts/Arial.ttf"])
        f = None
        for c in cands:
            try:
                f = ImageFont.truetype(c, size)
                break
            except OSError:
                continue
        _FONTS[key] = f or ImageFont.load_default(size)
    return _FONTS[key]


def rrect(d: ImageDraw.ImageDraw, box, r=14, fill=WHITE, outline=LINE, width=2):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def center_text(d, cx, y, s, f, fill=INK):
    w = d.textlength(s, font=f)
    d.text((cx - w / 2, y), s, font=f, fill=fill)


def wrap(d, x, y, s, f, max_w, fill=INK, lh=None):
    words, line, yy = s.split(), "", y
    lh = lh or (f.size + 6)
    for w_ in words:
        t = (line + " " + w_).strip()
        if d.textlength(t, font=f) <= max_w:
            line = t
        else:
            d.text((x, yy), line, font=f, fill=fill)
            yy += lh
            line = w_
    if line:
        d.text((x, yy), line, font=f, fill=fill)
        yy += lh
    return yy


def arrow(d, x1, y1, x2, y2, color=GRAY, w=4, head=12):
    d.line((x1, y1, x2, y2), fill=color, width=w)
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    for da in (2.6, -2.6):
        d.line((x2, y2, x2 - head * math.cos(ang + da) * 1.6,
                y2 - head * math.sin(ang + da) * 1.6), fill=color, width=w)


def header(d, W, title, subtitle):
    d.rectangle((0, 0, W, 12), fill=BLUE)
    d.text((60, 48), title, font=font(52, True), fill=INK)
    d.text((60, 118), subtitle, font=font(30), fill=GRAY)


def stage_card(d, box, kicker, title, body, active=False, kicker_color=BLUE):
    rrect(d, box, r=16, fill=(TINT if active else WHITE),
          outline=(BLUE if active else LINE), width=(4 if active else 2))
    x, y = box[0] + 24, box[1] + 22
    d.text((x, y), kicker, font=font(24, True), fill=kicker_color)
    d.text((x, y + 36), title, font=font(31, True), fill=INK)
    wrap(d, x, y + 82, body, font(24), box[2] - box[0] - 48, fill=GRAY, lh=31)


# =====================================================================
# D1 - three-layer architecture
# =====================================================================

def d1_layers():
    W, H = 2000, 1180
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    header(d, W, "IQR platform - three layers",
           "Documents enter once, deterministically. Agents reason over an addressable evidence graph, grounded by retrieval.")

    def layer(y0, y1, tag, tagc, name):
        rrect(d, (60, y0, W - 60, y1), r=20, fill=TINT2, outline=LINE)
        d.text((92, y0 + 22), tag, font=font(26, True), fill=tagc)
        d.text((92, y0 + 58), name, font=font(36, True), fill=INK)

    # Layer 1 - ingestion
    layer(190, 470, "1 · INGESTION", BLUE, "Deterministic Python - no model")
    steps = [("GRC package in", "performer upload · evidence lake"),
             ("Unpack tree", "email → zip → xlsx → image"),
             ("Extract", "openpyxl · OCR · email parser"),
             ("Hash + locate", "SHA-256 chain of custody"),
             ("Evidence Graph", "every fact addressable")]
    bx, bw, gap = 100, 330, 32
    for i, (t, s) in enumerate(steps):
        x0 = bx + i * (bw + gap)
        rrect(d, (x0, 300, x0 + bw, 430), r=14,
              fill=WHITE, outline=(BLUE if i == 4 else LINE), width=(4 if i == 4 else 2))
        d.text((x0 + 22, 322), t, font=font(29, True), fill=INK)
        wrap(d, x0 + 22, 364, s, font(23), bw - 44, fill=GRAY, lh=29)
        if i < 4:
            arrow(d, x0 + bw + 2, 365, x0 + bw + gap - 2, 365)

    # Layer 2 - knowledge
    layer(510, 790, "2 · KNOWLEDGE", STORM, "Grounding - vector-indexed, versioned")
    for i, (t, lines) in enumerate([
        ("Control Knowledge Base",
         "404 docs → compiled Validation Plans · expected evidence, checks, scope exclusions, sign-off rules · retrieval context for the Plan Compiler"),
        ("Golden Library",
         "adjudicated exemplars · prior verdicts + human overrides · “how was this judged before” · ships only after eval gate + SME sign-off")]):
        x0 = 100 + i * 940
        rrect(d, (x0, 620, x0 + 880, 760), r=14, fill=WHITE, outline=LINE)
        d.text((x0 + 24, 640), t, font=font(30, True), fill=INK)
        wrap(d, x0 + 24, 682, lines, font(23), 830, fill=GRAY, lh=29)

    # Layer 3 - reasoning
    layer(830, 1120, "3 · REASONING", ORANGE, "Agents + deterministic tools")
    cells = [("Match", "expected vs available - honest misses"),
             ("Check ×4", "numbers · vision · time · sign-off (parallel)"),
             ("Blinded Verify", "re-performs from citations alone"),
             ("Adjudicate", "citation gate → verdict + audit pack")]
    bw2 = 430
    for i, (t, s) in enumerate(cells):
        x0 = 100 + i * (bw2 + 32)
        rrect(d, (x0, 950, x0 + bw2, 1090), r=14, fill=WHITE,
              outline=(ORANGE if i == 2 else LINE), width=(4 if i == 2 else 2))
        d.text((x0 + 22, 972), t, font=font(30, True), fill=INK)
        wrap(d, x0 + 22, 1016, s, font(23), bw2 - 44, fill=GRAY, lh=29)
        if i < 3:
            arrow(d, x0 + bw2 + 2, 1020, x0 + bw2 + 30, 1020)
    im.save(OUT / "d1_layers.png")


# =====================================================================
# D2 - lifecycle: design once / run every period / learn governed
# =====================================================================

def d2_lifecycle():
    W, H = 2000, 1240
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    header(d, W, "Compiled-plan lifecycle",
           "Agents where judgment lives, code where numbers live - written once, approved by humans, executed identically every period.")

    cols = [(60, 660, "DESIGN - once per control", BLUE),
            (690, 1400, "RUN - every period", ORANGE),
            (1430, 1940, "LEARN - governed", STORM)]
    for x0, x1, t, c in cols:
        rrect(d, (x0, 190, x1, 1180), r=20, fill=TINT2, outline=LINE)
        d.text((x0 + 30, 214), t, font=font(30, True), fill=c)

    def node(x0, x1, y, t, s, accent=LINE, wdt=2, fill=WHITE):
        rrect(d, (x0, y, x1, y + 118), r=14, fill=fill, outline=accent, width=wdt)
        d.text((x0 + 22, y + 16), t, font=font(28, True), fill=INK)
        wrap(d, x0 + 22, y + 54, s, font(22), x1 - x0 - 44, fill=GRAY, lh=27)
        return y + 118

    # design column
    y = node(100, 620, 280, "SOX 404 document", "the control's process narrative (.docx)")
    arrow(d, 360, y + 4, 360, y + 34)
    y = node(100, 620, y + 40, "Plan Compiler agent", "DaVinci + Control-KB retrieval drafts the plan", BLUE)
    arrow(d, 360, y + 4, 360, y + 34)
    y = node(100, 620, y + 40, "SME review & approval", "human gate - nothing runs unapproved", BLUE, 4)
    arrow(d, 360, y + 4, 360, y + 34)
    y = node(100, 620, y + 40, "Frozen Validation Plan vX", "versioned JSON - immutable once approved", BLUE, 4, TINT)
    arrow(d, 620, 380, 730, 380, color=BLUE)

    # run column
    y = node(730, 1360, 280, "Ingest  (pure Python)", "unpack nested tree · hash every leaf · build Evidence Graph")
    arrow(d, 1045, y + 4, 1045, y + 30)
    y = node(730, 1360, y + 36, "Match", "plan's expected evidence ↔ graph · honest “missing”")
    arrow(d, 1045, y + 4, 1045, y + 30)
    yy = y + 36
    lane_w = 148
    labels = [("Numbers", "pure Python"), ("Vision", "OCR tie-out"),
              ("Time", "tz-normalize"), ("Sign-off", "SoD + order")]
    for i, (t, s) in enumerate(labels):
        x0 = 730 + i * (lane_w + 12)
        rrect(d, (x0, yy, x0 + lane_w, yy + 118), r=12,
              fill=WHITE, outline=ORANGE if i else LINE, width=2)
        d.text((x0 + 14, yy + 14), t, font=font(24, True), fill=INK)
        wrap(d, x0 + 14, yy + 48, s, font(20), lane_w - 26, fill=GRAY, lh=24)
    center_text(d, 1045, yy + 124, "4 parallel checks", font(20), GRAY)
    y = yy + 128
    arrow(d, 1045, y + 4, 1045, y + 30)
    y = node(730, 1360, y + 36, "Blinded Verifier", "sees only finding + clause + citations - never reasoning", ORANGE, 4)
    arrow(d, 1045, y + 4, 1045, y + 30)
    y = node(730, 1360, y + 36, "Adjudicator + citation gate", "uncited claims rejected · verdict: pass / gaps / fail", ORANGE, 4, TINT)
    arrow(d, 1045, y + 4, 1045, y + 30)
    node(730, 1360, y + 36, "Audit-ready pack (.zip)", "checklist · citations · manifest · gaps register · ledger")

    # learn column
    y = node(1470, 1900, 280, "Exception queue", "verifier disagreements + human overrides")
    arrow(d, 1685, y + 4, 1685, y + 34)
    y = node(1470, 1900, y + 40, "Golden Library", "adjudicated exemplars, vector-indexed", STORM)
    arrow(d, 1685, y + 4, 1685, y + 34)
    y = node(1470, 1900, y + 40, "Eval + SME gate", "5 metrics must pass - else nothing ships", STORM, 4)
    arrow(d, 1685, y + 4, 1685, y + 34)
    node(1470, 1900, y + 40, "Versioned release", "plan amendments & exemplars - never silent", STORM, 4, TINT)
    arrow(d, 1430, 1000, 1370, 1000, color=STORM)
    im.save(OUT / "d2_lifecycle.png")


# =====================================================================
# D3 - runtime topology (LangGraph) with citation gate
# =====================================================================

def d3_topology():
    W, H = 2000, 1000
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    header(d, W, "Run-time topology - fixed, versioned LangGraph",
           "Same shape every run; the topology hash is pinned in every run ledger. Typed state carries the Evidence Graph, never re-dumped text.")

    def gnode(x, y, w, t, s, accent=LINE, wdt=2, fill=WHITE):
        rrect(d, (x, y, x + w, y + 130), r=16, fill=fill, outline=accent, width=wdt)
        d.text((x + 24, y + 20), t, font=font(30, True), fill=INK)
        wrap(d, x + 24, y + 62, s, font(23), w - 48, fill=GRAY, lh=28)

    gnode(70, 300, 320, "ingest", "pure Python - unpack, hash, extract, graph")
    arrow(d, 390, 365, 450, 365)
    gnode(450, 300, 320, "match", "fuzzy map plan evidence; misses → gaps")
    # fan out
    lanes = [("check: numeric", "deterministic recompute - ZERO model calls", 210),
             ("check: vision", "agent + OCR tool - screenshot ↔ cell", 360),
             ("check: temporal", "agent + tz tools - GMT/CDT → UTC order", 510),
             ("check: signoff", "agent + email parser - SoD + sequence", 660)]
    for t, s, y in lanes:
        arrow(d, 770, 365, 830, y + 65)
        gnode(830, y, 430, t, s, accent=(LINE if "numeric" in t else ORANGE))
        arrow(d, 1260, y + 65, 1320, 505)
    gnode(1320, 440, 300, "verify", "blinded critic - citations only", ORANGE, 4)
    arrow(d, 1620, 505, 1665, 505)
    # citation gate diamond
    cx, cy = 1750, 505
    d.polygon([(cx, cy - 85), (cx + 85, cy), (cx, cy + 85), (cx - 85, cy)],
              fill=TINT, outline=BLUE, width=4)
    center_text(d, cx, cy - 30, "citation", font(24, True), BLUE_DARK)
    center_text(d, cx, cy - 2, "gate", font(24, True), BLUE_DARK)
    arrow(d, cx + 85, cy, cx + 130, cy, color=GREEN)
    d.text((cx + 88, cy - 60), "resolves", font=font(21), fill=GREEN)
    rrect(d, (1880, 470, 1990, 540), r=12, fill=WHITE, outline=GREEN, width=3)
    center_text(d, 1935, 492, "Verdict", font(24, True), GREEN)
    arrow(d, cx, cy + 85, cx, cy + 130, color=RED)
    d.text((cx + 10, cy + 95), "uncited / disagreement", font=font(21), fill=RED)
    rrect(d, (1620, 640, 1990, 715), r=12, fill=WHITE, outline=RED, width=3)
    center_text(d, 1805, 662, "human exception queue", font(24, True), RED)

    d.text((70, 800), "Model chain (auto mode):", font=font(26, True), fill=INK)
    chain = [("DaVinci API", BLUE, "primary - approved model"),
             ("Secondary endpoint", STORM, "optional, same wire format"),
             ("Offline stub", GRAY, "deterministic policy engine")]
    x = 70
    for i, (t, c, s) in enumerate(chain):
        rrect(d, (x, 845, x + 420, 935), r=12, fill=WHITE, outline=c, width=3)
        d.text((x + 20, 858), t, font=font(26, True), fill=c)
        d.text((x + 20, 894), s, font=font(21), fill=GRAY)
        if i < 2:
            arrow(d, x + 420, 890, x + 470, 890, color=ORANGE)
            center_text(d, x + 445, 845, "on fail", font(19, True), ORANGE)
        x += 470
    d.text((x + 20, 870), "every call records which backend answered\n→ run ledger (no silent switching)",
           font=font(22), fill=GRAY)
    im.save(OUT / "d3_topology.png")


# =====================================================================
# D4 - deployment & storage
# =====================================================================

def d4_storage():
    W, H = 2000, 1060
    im = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(im)
    header(d, W, "Deployment & storage",
           "Single-machine v1: clone, install, add keys, run. Every store is a plain directory - inspectable, portable, auditable.")

    # clients
    rrect(d, (60, 220, 480, 560), r=20, fill=TINT2, outline=LINE)
    d.text((84, 240), "CLIENTS", font=font(26, True), fill=BLUE)
    for i, (t, s) in enumerate([("Web console", "localhost:8400 - run, verdicts, pack download"),
                                ("CLI", "compile · approve · run · eval · testmodel · explain")]):
        y0 = 300 + i * 130
        rrect(d, (84, y0, 456, y0 + 110), r=12, fill=WHITE, outline=LINE)
        d.text((104, y0 + 14), t, font=font(27, True), fill=INK)
        wrap(d, 104, y0 + 52, s, font(21), 330, fill=GRAY, lh=26)
    arrow(d, 480, 390, 560, 390)

    # engine
    rrect(d, (560, 220, 1280, 800), r=20, fill=TINT2, outline=BLUE, width=3)
    d.text((584, 240), "IQR ENGINE (Python 3.12+)", font=font(26, True), fill=BLUE)
    for i, (t, s) in enumerate([
            ("FastAPI  iqr/api", "thin API - runs, plans, exceptions, packs"),
            ("LangGraph  iqr/graph", "fixed topology · typed state · parallel fan-out"),
            ("Agents  iqr/agents", "tool loop · DaVinci→secondary→stub fallback"),
            ("Tools  iqr/tools", "cell read · recompute · OCR · tz · email · citation")]):
        y0 = 292 + i * 122
        rrect(d, (584, y0, 1256, y0 + 104), r=12, fill=WHITE, outline=LINE)
        d.text((604, y0 + 12), t, font=font(27, True), fill=INK)
        wrap(d, 604, y0 + 50, s, font(21), 610, fill=GRAY, lh=26)
    arrow(d, 1280, 420, 1360, 420)

    # storage
    rrect(d, (1360, 220, 1940, 800), r=20, fill=TINT2, outline=LINE)
    d.text((1384, 240), "STORAGE  data/  (gitignored)", font=font(26, True), fill=STORM)
    stores = [("evidence_store/", "immutable blobs - filename = SHA-256"),
              ("plans/<control>/<ver>.json", "frozen SME-approved plans"),
              ("runs/<run_id>.jsonl", "replayable ledger - the ITGC evidence"),
              ("packs/<run_id>.zip", "audit-ready packages"),
              ("knowledge/", "Control KB + Golden Library indexes")]
    for i, (t, s) in enumerate(stores):
        y0 = 292 + i * 98
        rrect(d, (1384, y0, 1916, y0 + 82), r=12, fill=WHITE, outline=LINE)
        d.text((1404, y0 + 10), t, font=font(24, True), fill=INK)
        wrap(d, 1404, y0 + 44, s, font(20), 480, fill=GRAY, lh=24)

    # repo strip
    rrect(d, (60, 850, 1940, 990), r=16, fill=WHITE, outline=BLUE, width=3)
    d.text((90, 872), "Source of truth - private GitHub repo", font=font(28, True), fill=INK)
    d.text((90, 916), "git clone https://github.com/git-bonda108/iqr-sox.git   ·   "
                      "python3 -m venv .venv && .venv/bin/pip install -e .   ·   "
                      "cp .env.example .env  (keys never committed)",
           font=font(24), fill=BLUE_DARK)
    im.save(OUT / "d4_storage.png")


# =====================================================================
# GIF machinery - sample style: UI card canvas + bold caption bar
# =====================================================================

GW, GH = 1000, 620
BAR_H = 56


def gif_canvas(title_note=""):
    im = Image.new("RGB", (GW, GH), "#F4F8FB")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, GW, 44), fill=WHITE)
    d.line((0, 44, GW, 44), fill=LINE, width=2)
    d.text((24, 12), "IQR", font=font(22, True), fill=BLUE)
    d.text((78, 14), "· SOX 404 validation platform", font=font(19), fill=INK)
    if title_note:
        w = d.textlength(title_note, font=font(17))
        d.text((GW - w - 24, 15), title_note, font=font(17), fill=GRAY)
    return im, d


def caption(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, GH - BAR_H, GW, GH), fill=BLUE_DARK)
    d.rectangle((0, GH - BAR_H, 10, GH), fill=ORANGE)
    d.text((26, GH - BAR_H + 14), text, font=font(24, True), fill=WHITE)
    return im


def save_gif(frames, name, ms=1400):
    frames[0].save(OUT / name, save_all=True, append_images=frames[1:],
                   duration=ms, loop=0, optimize=True)
    # contact sheet for QA
    cols = min(4, len(frames))
    rows = (len(frames) + cols - 1) // cols
    tw, th = GW // 2, GH // 2
    sheet = Image.new("RGB", (cols * tw, rows * th), WHITE)
    for i, f in enumerate(frames):
        sheet.paste(f.resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sheet.save(OUT / f"{Path(name).stem}_frames.png")


# ---- GIF 1: end-to-end run (pipeline style like the sample) ----

def gif_pipeline():
    stages = [("1 · PLAN", "Frozen plan loads", "SME-approved v1.0.0 - runtime never re-plans"),
              ("2 · INGEST", "Tree unpacked & hashed", "email → zip → workbook → screenshot; SHA-256 custody"),
              ("3 · MATCH", "Evidence mapped", "expected ↔ found; absences declared honestly"),
              ("4 · CHECK", "4 modalities in parallel", "recompute · OCR tie-out · tz order · SoD"),
              ("5 · VERIFY", "Blinded re-performance", "citations only - executor reasoning never seen"),
              ("6 · REPORT", "Cited verdict + pack", "citation gate → checklist, gaps, audit .zip")]
    caps = ["A GRC package arrives - one control, nested evidence",
            "The frozen, SME-approved plan decides every check",
            "Deterministic Python builds the hashed evidence graph",
            "Honest matching - missing evidence can never pass",
            "Agents judge; tools compute; every fact gets a citation",
            "A blinded critic re-performs each finding from evidence alone",
            "Citation gate: uncited claims cannot enter the verdict",
            "Audit-ready pack out - every claim cited, every run replayable"]
    frames = []
    for step in range(len(caps)):
        im, d = gif_canvas("run-358a95e0f686")
        d.text((28, 66), "How a validation runs", font=font(30, True), fill=INK)
        d.text((28, 106), "Every control, same six stages - configured per control, engine built once.",
               font=font(19), fill=GRAY)
        rrect(d, (28, 140, 460, 178), r=18, fill=INK, outline=INK)
        d.text((44, 148), "“C23024 - Q2 FY26 rebate package”", font=font(18, True), fill=WHITE)
        cw, gap = 296, 18
        for i, (k, t, s) in enumerate(stages):
            row, col = divmod(i, 3)
            x0 = 28 + col * (cw + gap)
            y0 = 208 + row * 158
            active = (step - 2) >= i if step >= 2 else False
            current = (step - 2) == i
            box = (x0, y0, x0 + cw, y0 + 142)
            rrect(d, box, r=14, fill=(TINT if active else WHITE),
                  outline=(ORANGE if current else (BLUE if active else LINE)),
                  width=(4 if current else 2))
            d.text((x0 + 18, y0 + 14), k, font=font(17, True),
                   fill=(ORANGE if current else BLUE))
            d.text((x0 + 18, y0 + 40), t, font=font(21, True), fill=INK)
            wrap(d, x0 + 18, y0 + 70, s, font(16), cw - 36, fill=GRAY, lh=20)
            if active and not current:
                d.line((x0 + cw - 40, y0 + 24, x0 + cw - 32, y0 + 32), fill=GREEN, width=4)
                d.line((x0 + cw - 32, y0 + 32, x0 + cw - 18, y0 + 14), fill=GREEN, width=4)
        frames.append(caption(im, caps[step]))
    save_gif(frames, "iqr_run_pipeline.gif")


# ---- GIF 2: reviewer console walkthrough ----

def console_base(d):
    d.text((28, 66), "Reviewer console", font=font(30, True), fill=INK)
    d.text((28, 106), "Every claim cited. Every verdict repeatable.", font=font(19), fill=GRAY)
    rrect(d, (28, 140, 328, 182), r=8, fill=WHITE, outline=LINE)
    d.text((44, 152), "C23024", font=font(19), fill=INK)
    rrect(d, (340, 140, 760, 182), r=8, fill=WHITE, outline=LINE)
    d.text((356, 152), "grc_packages/C23024_Q2FY26/", font=font(19), fill=INK)
    rrect(d, (772, 140, 900, 182), r=8, fill=BLUE, outline=BLUE)
    d.text((800, 151), "Validate", font=font(20, True), fill=WHITE)


def gif_console():
    frames = []
    # f1 - empty form
    im, d = gif_canvas("localhost:8400")
    console_base(d)
    frames.append(caption(im, "Point at a control and its GRC evidence folder"))
    # f2 - running
    im, d = gif_canvas("localhost:8400")
    console_base(d)
    d.text((28, 212), "Running the frozen plan…", font=font(22), fill=GRAY)
    for i, t in enumerate(["ingest", "match", "checks ×3", "verify", "adjudicate"]):
        x0 = 28 + i * 150
        rrect(d, (x0, 250, x0 + 134, 288), r=18, fill=(TINT if i < 3 else WHITE),
              outline=(BLUE if i < 3 else LINE))
        center_text(d, x0 + 67, 259, t, font(17, True), BLUE_DARK if i < 3 else GRAY)
    frames.append(caption(im, "The fixed LangGraph executes - same topology every run"))
    # f3 - verdict
    rows = [("n1  Regional sales foot to total", "pass",
             "recomputed 454,000.00 = recorded (Δ 0.00)  ·  cell:Sales!B2-B5 → B7"),
            ("n2  Rebate = sales × rate", "pass",
             "recomputed 9,080.00 = recorded (Δ 0.00)  ·  cell:Rebate!B2·B3 → B4"),
            ("s1  Controller sign-off after prep", "pass",
             "ravi.mehta approved 06-Jul 14:30 UTC > prepared 05-Jul 14:00  ·  email:line 3")]
    im, d = gif_canvas("localhost:8400")
    console_base(d)
    d.text((28, 210), "C23024 - ", font=font(26, True), fill=INK)
    d.text((150, 210), "pass", font=font(26, True), fill=GREEN)
    d.text((222, 216), "(plan v1.0.0 · run-358a95e0f686)", font=font(18), fill=GRAY)
    for i, (t, v, s) in enumerate(rows):
        y0 = 256 + i * 92
        rrect(d, (28, y0, 972, y0 + 80), r=10, fill=WHITE, outline=LINE)
        d.text((46, y0 + 10), t, font=font(20, True), fill=INK)
        d.text((46, y0 + 42), s, font=font(16), fill=GRAY)
        rrect(d, (886, y0 + 12, 956, y0 + 44), r=14, fill="#E9F7EE", outline=GREEN)
        center_text(d, 921, y0 + 18, v, font(17, True), GREEN)
    frames.append(caption(im, "Verdict with a resolvable citation on every claim"))
    # f4 - citations zoom
    im, d = gif_canvas("localhost:8400")
    console_base(d)
    d.text((28, 208), "What a citation resolves to", font=font(24, True), fill=INK)
    for i, (loc, meaning) in enumerate([
            ("cell:37d2a0c1…:Sales!B7", "workbook hash + sheet + cell - the exact recomputed value"),
            ("image:7dde8180…:(40,130,860,220)", "screenshot hash + OCR region that was read"),
            ("email:<c23024-approval…>:line 3", "message id + body line holding the approval"),
            ("doc:9f1a…:para 4", "the 404 requirement a gap abstains against")]):
        y0 = 252 + i * 78
        rrect(d, (28, y0, 972, y0 + 66), r=10, fill=TINT2, outline=LINE)
        d.text((46, y0 + 8), loc, font=font(19, True), fill=BLUE_DARK)
        d.text((46, y0 + 36), meaning, font=font(17), fill=GRAY)
    frames.append(caption(im, "Locators are hashes, not filenames - tamper-evident by design"))
    # f5 - pack
    im, d = gif_canvas("localhost:8400")
    console_base(d)
    d.text((28, 208), "Audit-ready pack", font=font(24, True), fill=INK)
    for i, (t, s) in enumerate([
            ("verdict.json", "per-check results, computed values, citations"),
            ("checklist.md", "reviewer checklist, auto-completed & evidenced"),
            ("artifact_manifest.json", "every leaf + SHA-256 - chain of custody"),
            ("gaps_and_observations.md", "everything missing or unexpected - explicit"),
            ("citations.json + plan.json", "the claims and the frozen plan that produced them")]):
        y0 = 250 + i * 62
        rrect(d, (28, y0, 700, y0 + 52), r=10, fill=WHITE, outline=LINE)
        d.text((46, y0 + 6), t, font=font(19, True), fill=INK)
        d.text((46, y0 + 30), s, font=font(15), fill=GRAY)
    rrect(d, (730, 300, 972, 352), r=10, fill=BLUE, outline=BLUE)
    center_text(d, 851, 314, "Download .zip", font(21, True), WHITE)
    frames.append(caption(im, "One download - GRC-ready, auditor-ready"))
    save_gif(frames, "iqr_console.gif", ms=2000)


# ---- GIF 3: blinded verifier ----

def gif_verifier():
    def base():
        im, d = gif_canvas("verification")
        d.text((28, 66), "The critic never sees the reasoning. Only the evidence.",
               font=font(28, True), fill=INK)
        # executor card
        rrect(d, (28, 130, 468, 420), r=16, fill=WHITE, outline=LINE)
        d.text((52, 150), "EXECUTOR AGENT", font=font(18, True), fill=BLUE)
        d.text((52, 182), "Runs the check, produces a finding", font=font(18), fill=GRAY)
        rrect(d, (52, 220, 444, 300), r=10, fill=TINT2, outline=LINE)
        d.text((68, 232), "finding: s1 → pass", font=font(19, True), fill=INK)
        d.text((68, 262), "citations: email:line 3 · cell:Meta!B1", font=font(16), fill=GRAY)
        rrect(d, (52, 316, 444, 396), r=10, fill="#EFEFEF", outline="#BFBFBF")
        d.text((68, 328), "internal reasoning", font=font(18, True), fill="#8A8A8A")
        d.text((68, 358), "stays private - never forwarded", font=font(16), fill="#8A8A8A")
        # verifier card
        rrect(d, (532, 130, 972, 420), r=16, fill=WHITE, outline=ORANGE, width=3)
        d.text((556, 150), "BLINDED VERIFIER", font=font(18, True), fill=ORANGE)
        d.text((556, 182), "Re-performs from cited evidence alone", font=font(18), fill=GRAY)
        return im, d

    frames = []
    im, d = base()
    frames.append(caption(im, "Executor concludes - with citations, not just an opinion"))

    im, d = base()
    arrow(d, 468, 260, 532, 260, color=BLUE, w=5)
    center_text(d, 500, 232, "finding · clause ·", font(14, True), BLUE_DARK)
    center_text(d, 500, 250, "citations", font(14, True), BLUE_DARK)
    rrect(d, (556, 220, 948, 330), r=10, fill=TINT2, outline=LINE)
    d.text((572, 232), "re-reads email:line 3  →  approver ravi.mehta", font=font(17), fill=INK)
    d.text((572, 262), "re-reads cell:Meta!B1  →  prepared 14:00 GMT", font=font(17), fill=INK)
    d.text((572, 292), "recomputes order  →  approval AFTER prep", font=font(17), fill=INK)
    frames.append(caption(im, "Only three things cross the wall - never the reasoning"))

    im, d = base()
    rrect(d, (556, 220, 948, 330), r=10, fill=TINT2, outline=LINE)
    d.text((572, 232), "independent conclusion: pass", font=font(19, True), fill=GREEN)
    d.text((572, 266), "matches executor → finding enters the report", font=font(17), fill=GRAY)
    rrect(d, (556, 346, 948, 400), r=10, fill="#E9F7EE", outline=GREEN)
    d.line((574, 372, 582, 380), fill=GREEN, width=4)
    d.line((582, 380, 596, 362), fill=GREEN, width=4)
    d.text((610, 360), "AGREE  →  verdict + audit pack", font=font(19, True), fill=GREEN)
    frames.append(caption(im, "Agreement - the finding is independently reproduced"))

    im, d = base()
    rrect(d, (556, 220, 948, 330), r=10, fill=TINT2, outline=LINE)
    d.text((572, 232), "independent conclusion: fail", font=font(19, True), fill=RED)
    d.text((572, 266), "contradicts executor → nothing ships silently", font=font(17), fill=GRAY)
    rrect(d, (556, 346, 948, 400), r=10, fill="#FDECEA", outline=RED)
    d.text((572, 360), "× DISAGREE  →  human queue", font=font(19, True), fill=RED)
    frames.append(caption(im, "Disagreement routes to a human - the model never outvotes itself"))
    save_gif(frames, "iqr_blinded_verifier.gif", ms=2200)


if __name__ == "__main__":
    d1_layers()
    d2_lifecycle()
    d3_topology()
    d4_storage()
    gif_pipeline()
    gif_console()
    gif_verifier()
    for p in sorted(OUT.iterdir()):
        print(p.name, p.stat().st_size)

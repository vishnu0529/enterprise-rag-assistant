from pathlib import Path

from manifest import SEGMENTS, STAGES
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent
FRAMES = ROOT / "frames"
W, H = 1920, 1080

BG = (16, 19, 26)
PANEL = (23, 27, 36)
LINE = (43, 49, 64)
INK = (231, 234, 240)
INK_SOFT = (154, 163, 180)
INK_FAINT = (90, 97, 112)
ACCENT = (138, 166, 224)
ACCENT_WASH = (28, 39, 64)
GOOD = (95, 190, 132)

MONO = "/System/Library/Fonts/Menlo.ttc"
_SFNS = "/System/Library/Fonts/SFNS.ttf"
DISPLAY = _SFNS if Path(_SFNS).exists() else MONO


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def draw_pipeline(d, cx, cy, active, box_w=280, box_h=86, gap=56, font_size=22):
    """Draws STAGES as connected boxes centered at (cx, cy), highlighting `active` names."""
    f = font(MONO, font_size)
    n = len(STAGES)
    total_w = n * box_w + (n - 1) * gap
    x0 = cx - total_w / 2
    y0 = cy - box_h / 2
    for i, stage in enumerate(STAGES):
        bx = x0 + i * (box_w + gap)
        is_active = stage in active
        fill = ACCENT_WASH if is_active else PANEL
        outline = ACCENT if is_active else LINE
        d.rectangle(
            [(bx, y0), (bx + box_w, y0 + box_h)],
            fill=fill,
            outline=outline,
            width=3 if is_active else 2,
        )
        bbox = d.textbbox((0, 0), stage, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        color = INK if is_active else INK_FAINT
        d.text((bx + box_w / 2 - tw / 2, y0 + box_h / 2 - th / 2 - 4), stage, font=f, fill=color)
        if i < n - 1:
            ay = y0 + box_h / 2
            ax0 = bx + box_w + 10
            ax1 = bx + box_w + gap - 10
            d.line([(ax0, ay), (ax1, ay)], fill=LINE, width=3)
            d.polygon([(ax1, ay - 8), (ax1 + 10, ay), (ax1, ay + 8)], fill=LINE)


def draw_stage_strip(d, active):
    draw_pipeline(d, W / 2, 60, active, box_w=190, box_h=48, gap=28, font_size=15)


def draw_diagram_frame(seg):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title = seg["title"]
    size = 64
    max_w = W - 160
    while size > 24:
        f_title = font(DISPLAY, size)
        bbox = d.textbbox((0, 0), title, font=f_title)
        tw = bbox[2] - bbox[0]
        if tw <= max_w:
            break
        size -= 2
    f_sub = font(MONO, 28)
    f_byline = font(MONO, 22)
    d.text(((W - tw) / 2, 150), title, font=f_title, fill=INK)
    sub = seg.get("subtitle", "")
    bbox2 = d.textbbox((0, 0), sub, font=f_sub)
    sw = bbox2[2] - bbox2[0]
    d.text(((W - sw) / 2, 235), sub, font=f_sub, fill=INK_SOFT)
    byline = seg.get("byline", "")
    if byline:
        bbox4 = d.textbbox((0, 0), byline, font=f_byline)
        bw = bbox4[2] - bbox4[0]
        d.text(((W - bw) / 2, 285), byline, font=f_byline, fill=ACCENT)

    draw_pipeline(
        d,
        W / 2,
        H / 2,
        seg.get("active_stages", []),
        box_w=300,
        box_h=110,
        gap=50,
        font_size=24,
    )

    foot = "five stages, each with its own failure mode and its own control"
    f_foot = font(MONO, 22)
    bbox3 = d.textbbox((0, 0), foot, font=f_foot)
    fw = bbox3[2] - bbox3[0]
    d.text(((W - fw) / 2, H / 2 + 140), foot, font=f_foot, fill=INK_FAINT)
    return img


def draw_title_frame(seg):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    title = seg["title"]
    size = 64
    max_w = W - 160
    while size > 24:
        f_title = font(DISPLAY, size)
        bbox = d.textbbox((0, 0), title, font=f_title)
        tw = bbox[2] - bbox[0]
        if tw <= max_w:
            break
        size -= 2
    f_sub = font(MONO, 30)
    f_byline = font(MONO, 24)
    d.text(((W - tw) / 2, H / 2 - 80), title, font=f_title, fill=INK)
    sub = seg.get("subtitle", "")
    bbox2 = d.textbbox((0, 0), sub, font=f_sub)
    sw = bbox2[2] - bbox2[0]
    d.text(((W - sw) / 2, H / 2 + 20), sub, font=f_sub, fill=INK_SOFT)
    byline = seg.get("byline", "")
    if byline:
        bbox4 = d.textbbox((0, 0), byline, font=f_byline)
        bw = bbox4[2] - bbox4[0]
        d.text(((W - bw) / 2, H / 2 + 80), byline, font=f_byline, fill=ACCENT)
    return img


def draw_terminal_frame(seg):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_header = font(DISPLAY, 36)
    f_body = font(MONO, 30)

    draw_stage_strip(d, seg.get("active_stages", []))

    d.text((80, 140), seg["header"], font=f_header, fill=ACCENT)
    d.line([(80, 200), (W - 80, 200)], fill=LINE, width=2)

    panel_top = 240
    panel_bottom = H - 80
    d.rectangle([(80, panel_top), (W - 80, panel_bottom)], fill=PANEL, outline=LINE, width=2)

    lines = seg["body"].split("\n")
    y = panel_top + 40
    for line in lines:
        color = GOOD if line.strip().startswith("$") else INK
        if "PASSED" in line or "422" in line or "100%" in line:
            color = GOOD
        d.text((120, y), line, font=f_body, fill=color)
        y += 42
    return img


def draw_scorecard_frame(seg):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_header = font(DISPLAY, 36)
    f_num = font(DISPLAY, 90)
    f_lbl = font(MONO, 26)

    draw_stage_strip(d, seg.get("active_stages", []))

    d.text((80, 140), seg["header"], font=f_header, fill=ACCENT)
    d.line([(80, 200), (W - 80, 200)], fill=LINE, width=2)

    cols = [
        ("9", "Demonstrated", GOOD),
        ("5", "Partial", (210, 165, 63)),
        ("1", "Open", (217, 123, 99)),
    ]
    col_w = (W - 160) / 3
    for i, (n, lbl, color) in enumerate(cols):
        cx = 80 + col_w * i + col_w / 2
        bbox = d.textbbox((0, 0), n, font=f_num)
        nw = bbox[2] - bbox[0]
        d.text((cx - nw / 2, 460), n, font=f_num, fill=color)
        bbox2 = d.textbbox((0, 0), lbl, font=f_lbl)
        lw = bbox2[2] - bbox2[0]
        d.text((cx - lw / 2, 600), lbl, font=f_lbl, fill=INK_SOFT)

    foot = "15-point Agent Production Readiness Scorecard — enterprise-rag-assistant"
    bbox3 = d.textbbox((0, 0), foot, font=f_lbl)
    fw = bbox3[2] - bbox3[0]
    d.text(((W - fw) / 2, H - 140), foot, font=f_lbl, fill=INK_SOFT)
    return img


def main():
    for seg in SEGMENTS:
        if seg["kind"] == "title":
            img = draw_title_frame(seg)
        elif seg["kind"] == "diagram":
            img = draw_diagram_frame(seg)
        elif seg["kind"] == "terminal":
            img = draw_terminal_frame(seg)
        elif seg["kind"] == "scorecard":
            img = draw_scorecard_frame(seg)
        else:
            raise ValueError(seg["kind"])
        out = FRAMES / f"{seg['id']}.png"
        img.save(out)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()

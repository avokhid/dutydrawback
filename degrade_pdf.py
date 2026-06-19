"""
Degrade a clean PDF into realistic "messy" variants, to stress-test extraction.

Why: a validation run on pristine textbook 7501s gives a rosy scorecard that
lies. Real extraction has to survive faxes, re-scans, skew, and phone photos.
If you only have clean samples, this manufactures the long tail so your
validation set is honest about what extraction will actually face.

Each variant simulates a real failure mode:
  fax       — 1-bit black/white, low DPI, the classic "received by fax" look
  scan      — grayscale, mild blur + sensor noise + slight contrast loss
  photo     — perspective skew + uneven lighting, like a phone snap on a desk
  lowres    — just downscaled, the "someone emailed a tiny JPEG" case
  rotate    — a few degrees of rotation, very common with scanners/feeders

This is a TEST-DATA tool, not part of the product. It does not transmit anything
and needs no API key. Use it only on documents you're authorized to use.

Usage:
    python3 degrade_pdf.py clean_7501.pdf                  # all variants
    python3 degrade_pdf.py clean_7501.pdf --modes fax scan
    python3 degrade_pdf.py clean_7501.pdf --out ./messy --dpi 150
Produces, e.g., messy/clean_7501__fax.pdf etc. — feed the folder to
validate_extraction.py.
"""

from __future__ import annotations

import argparse
import io
import os
import random

import pypdfium2 as pdfium
from PIL import Image, ImageFilter, ImageEnhance
import img2pdf


MODES = ["fax", "scan", "photo", "lowres", "rotate"]


def render_pages(pdf_path: str, dpi: int = 150) -> list[Image.Image]:
    """Rasterize each PDF page to a PIL image (pypdfium2 — no external deps)."""
    pdf = pdfium.PdfDocument(pdf_path)
    scale = dpi / 72.0
    pages = []
    for i in range(len(pdf)):
        page = pdf[i]
        bitmap = page.render(scale=scale)
        pages.append(bitmap.to_pil().convert("RGB"))
    return pages


def _add_noise(img: Image.Image, amount: int = 18) -> Image.Image:
    px = img.load()
    w, h = img.size
    rnd = random.Random(42)  # deterministic so runs are repeatable
    for _ in range((w * h) // 12):
        x, y = rnd.randrange(w), rnd.randrange(h)
        d = rnd.randint(-amount, amount)
        if isinstance(px[x, y], tuple):
            r, g, b = px[x, y][:3]
            px[x, y] = (max(0, min(255, r + d)),) * 3
        else:
            px[x, y] = max(0, min(255, px[x, y] + d))
    return img


def degrade_fax(img: Image.Image) -> Image.Image:
    # low DPI feel + harsh 1-bit threshold (classic fax)
    small = img.resize((img.width // 2, img.height // 2)).convert("L")
    small = ImageEnhance.Contrast(small).enhance(1.4)
    bw = small.point(lambda p: 255 if p > 135 else 0, mode="1").convert("L")
    return bw.resize(img.size)


def degrade_scan(img: Image.Image) -> Image.Image:
    g = img.convert("L")
    g = g.filter(ImageFilter.GaussianBlur(0.8))
    g = ImageEnhance.Contrast(g).enhance(0.9)
    g = _add_noise(g, amount=22)
    return g.convert("RGB")


def degrade_photo(img: Image.Image) -> Image.Image:
    # uneven lighting: darken one corner with a gradient overlay
    g = img.convert("RGB")
    w, h = g.size
    grad = Image.new("L", (w, h), 0)
    gpx = grad.load()
    for y in range(h):
        for x in range(0, w, 4):  # step for speed
            v = int(70 * ((x / w) * (y / h)))
            for dx in range(4):
                if x + dx < w:
                    gpx[x + dx, y] = v
    dark = Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), g, grad)
    g = Image.blend(g, dark, 0.5)
    # mild perspective skew via rotate+crop
    g = g.rotate(-2.5, expand=True, fillcolor=(255, 255, 255))
    g = g.filter(ImageFilter.GaussianBlur(0.5))
    return g


def degrade_lowres(img: Image.Image) -> Image.Image:
    tiny = img.resize((max(1, img.width // 3), max(1, img.height // 3)))
    return tiny.resize(img.size)


def degrade_rotate(img: Image.Image) -> Image.Image:
    return img.rotate(-4, expand=True, fillcolor=(255, 255, 255))


DEGRADERS = {
    "fax": degrade_fax, "scan": degrade_scan, "photo": degrade_photo,
    "lowres": degrade_lowres, "rotate": degrade_rotate,
}


def images_to_pdf(images: list[Image.Image], out_path: str) -> None:
    buffers = []
    for im in images:
        b = io.BytesIO()
        im.convert("RGB").save(b, format="JPEG", quality=70)
        buffers.append(b.getvalue())
    with open(out_path, "wb") as f:
        f.write(img2pdf.convert(buffers))


def degrade(pdf_path: str, modes: list[str], out_dir: str, dpi: int) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    pages = render_pages(pdf_path, dpi=dpi)
    written = []
    for mode in modes:
        fn = DEGRADERS[mode]
        degraded = [fn(p) for p in pages]
        out = os.path.join(out_dir, f"{base}__{mode}.pdf")
        images_to_pdf(degraded, out)
        written.append(out)
        print(f"  wrote {out}")
    return written


def main():
    ap = argparse.ArgumentParser(description="Degrade a clean PDF into messy variants for extraction stress-testing.")
    ap.add_argument("pdf", help="a clean source PDF")
    ap.add_argument("--modes", nargs="+", choices=MODES, default=MODES)
    ap.add_argument("--out", default="messy_variants")
    ap.add_argument("--dpi", type=int, default=150)
    args = ap.parse_args()
    if not os.path.isfile(args.pdf):
        raise SystemExit(f"not a file: {args.pdf}")
    print(f"degrading {args.pdf} -> {args.out}/ ({', '.join(args.modes)})")
    degrade(args.pdf, args.modes, args.out, args.dpi)
    print("\nFeed the output folder to validate_extraction.py to see how "
          "extraction holds up on the messy variants.")


if __name__ == "__main__":
    main()

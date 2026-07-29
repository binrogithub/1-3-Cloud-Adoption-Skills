from playwright.sync_api import sync_playwright
import os
import numpy as np
from PIL import Image
import io
import fitz  # PyMuPDF

here = os.path.dirname(os.path.abspath(__file__))
html_path = os.path.join(here, "index.html")
pdf_path = os.path.join(here, "sms-migration.pdf")

CONTENT_WIDTH = 1008


def generate_pdf(page, width_px, height_px, out_path):
    page.pdf(
        path=out_path,
        width=f"{width_px}px",
        height=f"{height_px}px",
        print_background=True,
        margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
    )


def measure_pdf(pdf_file):
    """Returns (page_count, content_bottom_pts, page_height_pts)."""
    doc = fitz.open(pdf_file)
    pages = doc.page_count
    mat = fitz.Matrix(1, 1)

    if pages == 1:
        pix = doc[0].get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        pixs = [doc[i].get_pixmap(matrix=mat) for i in range(pages)]
        total_h = sum(p.height for p in pixs)
        img = Image.new("RGB", (pixs[0].width, total_h), (255, 255, 255))
        y = 0
        for p in pixs:
            img.paste(Image.frombytes("RGB", (p.width, p.height), p.samples), (0, y))
            y += p.height

    arr = np.array(img)
    page_h = doc[0].rect.height if pages == 1 else None
    doc.close()

    for y in range(arr.shape[0] - 1, -1, -1):
        if np.any(np.any(arr[y] < 245, axis=1)):
            return pages, y + 1, page_h
    return pages, 0, page_h


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/usr/bin/google-chrome-stable",
        args=["--no-sandbox", "--disable-setuid-sandbox"]
    )
    page = browser.new_page(viewport={"width": CONTENT_WIDTH, "height": 800})
    page.goto("file://" + html_path, wait_until="networkidle")
    page.wait_for_timeout(1000)

    page.evaluate("""() => {
        document.querySelectorAll('details').forEach(d => d.open = true);
    }""")

    page.emulate_media(media="print")
    page.wait_for_timeout(500)

    # Step 1: Generate generous to find content bottom
    scroll_height = page.evaluate("() => document.documentElement.scrollHeight")
    generous_h = scroll_height + 500
    print(f"Step 1: Generate at {CONTENT_WIDTH}x{generous_h}px")
    generate_pdf(page, CONTENT_WIDTH, generous_h, pdf_path)
    pages, cb_pts, _ = measure_pdf(pdf_path)
    print(f"  {pages} page(s), content ends at {cb_pts:.0f}pts")

    # Convert content bottom (pts) to CSS px for Chrome
    cb_css_px = cb_pts * 96 / 72
    print(f"  Content bottom in CSS px: {cb_css_px:.1f}px")

    # Binary search for minimum height that gives exactly 1 page
    # Low = 2 pages, High = 1 page
    low = int(cb_css_px)        # too tight, likely 2 pages
    high = int(cb_css_px) + 100  # generous, likely 1 page

    # Verify high is actually 1 page
    generate_pdf(page, CONTENT_WIDTH, high, pdf_path)
    pages_high, _, _ = measure_pdf(pdf_path)
    if pages_high > 1:
        high = int(cb_css_px) + 200
        generate_pdf(page, CONTENT_WIDTH, high, pdf_path)
        pages_high, _, _ = measure_pdf(pdf_path)

    print(f"Binary search range: {low}..{high}px")

    best_h = high
    while high - low > 1:
        mid = (low + high) // 2
        generate_pdf(page, CONTENT_WIDTH, mid, pdf_path)
        pages_mid, _, _ = measure_pdf(pdf_path)
        if pages_mid == 1:
            high = mid
            best_h = mid
        else:
            low = mid
        print(f"  Try {mid}px -> {pages_mid} page(s), range now {low}..{high}")

    # Generate final at best_h
    generate_pdf(page, CONTENT_WIDTH, best_h, pdf_path)
    print(f"\nFinal height: {best_h}px")

    browser.close()

# Final report
pages, cb, ph = measure_pdf(pdf_path)
doc = fitz.open(pdf_path)
page0 = doc[0]
mat = fitz.Matrix(1, 1)
pix = page0.get_pixmap(matrix=mat)
img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
arr = np.array(img)
for y in range(arr.shape[0]-1, -1, -1):
    if np.any(np.any(arr[y] < 245, axis=1)):
        blank = arr.shape[0]-1-y
        print(f"Final: {doc.page_count} page(s), {pix.width}x{pix.height}pts ({pix.width*96/72:.0f}x{pix.height*96/72:.0f}px)")
        print(f"Blank: {blank}px ({blank/arr.shape[0]*100:.1f}%)")
        break
doc.close()

size = os.path.getsize(pdf_path)
print(f"Size: {size/1024:.1f} KB")

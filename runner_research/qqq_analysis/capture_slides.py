"""
capture_slides.py — Render each slide of output/playbook.html to a PNG.

Headless Chromium at 1600x1000 (16:10, presentation-friendly). Navigates the deck with the
page's own show(i) function, waits for the fade transition, snapshots the viewport.
Outputs -> output/slides/playbook_01.png ... playbook_NN.png
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "output"
SLIDES = OUT / "slides"
SLIDES.mkdir(exist_ok=True)

W, H = 1600, 1000


def main():
    url = (OUT / "playbook.html").resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        page.goto(url)
        page.wait_for_load_state("networkidle")
        n = page.evaluate("document.querySelectorAll('.slide').length")
        print(f"[capture] {n} slides at {W}x{H}@2x")
        for i in range(n):
            page.evaluate(f"show({i})")
            page.wait_for_timeout(550)          # fade transition is .4s
            path = SLIDES / f"playbook_{i+1:02d}.png"
            page.screenshot(path=str(path))
            print(f"  wrote {path.name}")
        browser.close()
    print(f"[capture] done -> {SLIDES}")


if __name__ == "__main__":
    main()

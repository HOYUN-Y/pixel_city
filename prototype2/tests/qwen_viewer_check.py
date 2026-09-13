"""Headless visual/interaction check of a real Qwen run folder.

Usage: prototype2/.venv/bin/python prototype2/tests/qwen_viewer_check.py RUN_FOLDER
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def check(folder):
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1080}, device_scale_factor=1)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("requestfailed", lambda request: errors.append(request.url))
        page.goto((folder / "index.html").resolve().as_uri(), wait_until="load")
        report = json.loads((folder / "report.json").read_text())
        expected_title = ("같은 지도 — 로컬 Qwen / OpenRouter 비교" if report.get("local_only") is False
                          else "서울 픽셀 도시 — 로컬 Qwen 시험")
        assert page.locator("h1").inner_text() == expected_title
        assert page.locator("img").evaluate_all("imgs => imgs.every(i => i.complete && i.naturalWidth > 0)")
        controls_checked = bool(page.locator("#ai").count())
        if controls_checked:
            source = page.locator(".overlay img").first.bounding_box()
            overlay = page.locator("#ai").bounding_box()
            assert source == overlay, (source, overlay)
            page.locator("#opacity").fill("0")
            page.locator("#opacity").dispatch_event("input")
            assert page.locator("#ai").evaluate("e => e.style.opacity") == "0"
            page.locator("#opacity").fill("50")
            page.locator("#opacity").dispatch_event("input")
            options = page.locator("#candidate option").count()
            if options > 1:
                page.locator("#candidate").select_option(index=1)
                expected = page.locator("#candidate").input_value()
                assert page.locator("#ai").get_attribute("src") == expected
        page.screenshot(path=str(folder / "viewer_qa.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(folder / "viewer_mobile_qa.png"), full_page=True)
        if controls_checked:
            page.locator(".cards figure").nth(2).screenshot(path=str(folder / "candidate_mobile_qa.png"))
        assert not errors, errors
        browser.close()
    print(f"Qwen viewer passed: local images; overlay controls checked={controls_checked}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("folder", type=Path)
    check(ap.parse_args().folder)

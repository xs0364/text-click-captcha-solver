"""
Coordinate mapping and Playwright click orchestration.

Takes character boxes identified by the vision model, maps their
coordinates from screenshot-pixel space to CSS-pixel space,
then clicks them in order via Playwright.

The key insight: Playwright page.screenshot(clip=CSS_rect) returns
different pixel counts depending on devicePixelRatio:
  - headless (DPR=1):  screenshot pixels == CSS pixels
  - headed   (DPR=1.25~2): screenshot pixels = CSS × DPR

We read the actual screenshot dimensions and compute the scale
to map model-detected coordinates correctly back to CSS space.
"""

from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


def map_and_click(
    page: Page,
    merged_boxes: list[tuple[int, int, int, int]],
    classify_result: list[dict],
    wordlist: list[str],
    panel_x: float,
    panel_y: float,
    css_w: float,
    css_h: float,
    snap_w: int,
    snap_h: int,
) -> bool:
    """
    Map classified character regions to CSS coordinates and click in order.

    Args:
        page: Playwright Page to click on.
        merged_boxes: List of (x, y, w, h) for each candidate region (screenshot px).
        classify_result: Vision model output: [{"n":0, "c":"唱", "t":true}, ...].
        wordlist: Target character order.
        panel_x, panel_y: Panel offset in CSS pixels.
        css_w, css_h: Panel CSS dimensions (from getBoundingClientRect).
        snap_w, snap_h: Screenshot actual pixel dimensions.

    Returns:
        True if all clicks were performed, False if match failed.
    """
    # Build char → (cx, cy) mapping from classified regions
    found: dict[str, tuple[int, int]] = {}

    for r in classify_result:
        ch = r.get("c", "")
        is_target = r.get("t", False)
        idx = r.get("n", -1)

        if is_target and ch in wordlist and ch not in found:
            if 0 <= idx < len(merged_boxes):
                x, y, cw, ch_h = merged_boxes[idx]
                center_x = x + cw // 2
                center_y = y + ch_h // 2
                found[ch] = (center_x, center_y)

    # Verify all targets found
    for ch in wordlist:
        if ch not in found:
            print(f"  [CLICK] Missing target '{ch}' in classification result")
            return False

    # scale: screenshot pixels → CSS pixels
    # (DPR=1 in headless → snap == css, scale = 1.0)
    scale_x = css_w / snap_w if snap_w else 1.0
    scale_y = css_h / snap_h if snap_h else 1.0

    for ch in wordlist:
        x_img, y_img = found[ch]
        click_x = panel_x + x_img * scale_x
        click_y = panel_y + y_img * scale_y
        page.mouse.click(int(click_x), int(click_y))
        page.wait_for_timeout(400)

    return True

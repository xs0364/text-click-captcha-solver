"""
Captcha element locator — finds the captcha image and hint text on the page.

Uses JavaScript injection into the Playwright page to:
1. Find hint text containing 【】 brackets
2. Find the largest >150x150 image (the captcha panel)
3. Return geometry for screenshot + coordinate mapping
"""

from typing import Any, Optional
from playwright.sync_api import Page


_LOCATE_CAPTCHA_JS = """() => {
    const out = { imgData: null, hintText: '', panelRect: null, naturalW: 500, naturalH: 300 };

    // 1. Find hint text — any visible element containing 【】
    const allEls = document.querySelectorAll('*');
    for (const el of allEls) {
        const t = (el.innerText || '').trim();
        if (t.includes('【') && t.includes('】') && (el.offsetParent !== null || true)) {
            out.hintText = t;
            break;
        }
    }

    // 2. Find captcha image — largest >150x150 image
    let bestImg = null, bestArea = 0;
    for (const img of document.querySelectorAll('img')) {
        const r = img.getBoundingClientRect();
        if (r.width < 150 || r.height < 150) continue;
        const area = r.width * r.height;
        if (area > bestArea) {
            bestArea = area;
            bestImg = img;
        }
    }
    if (bestImg) {
        const r = bestImg.getBoundingClientRect();
        out.panelRect = { x: r.x, y: r.y, w: r.width, h: r.height };
        out.naturalW = bestImg.naturalWidth || r.width;
        out.naturalH = bestImg.naturalHeight || r.height;
        try {
            const c = document.createElement('canvas');
            c.width = out.naturalW;
            c.height = out.naturalH;
            const ctx = c.getContext('2d');
            ctx.drawImage(bestImg, 0, 0);
            out.imgData = c.toDataURL('image/png');
        } catch(e) {}
    }

    return out;
}"""


def find_captcha_elements(page: Page) -> Optional[dict[str, Any]]:
    """
    Find the captcha image and hint text on the current page.

    Args:
        page: A Playwright Page instance.

    Returns:
        dict with keys:
            - imgData (str|None): base64 data URL (may be None due to CORS)
            - hintText (str): text containing 【target characters】
            - panelRect (dict): {x, y, w, h} in CSS pixels
            - naturalW (int), naturalH (int): image natural dimensions
        Returns None if no captcha elements are found.
    """
    result = page.evaluate(_LOCATE_CAPTCHA_JS)
    if result.get("panelRect") and result.get("hintText"):
        return result
    return None


def parse_wordlist(hint_text: str) -> list[str]:
    """
    Extract target characters from hint text like "请依次点击【工、厂、大】".

    Args:
        hint_text: The full hint text containing 【】.

    Returns:
        List of target character strings in click order.
    """
    import re
    match = re.search(r"【(.*?)】", hint_text)
    if not match:
        return []
    chars = [c.strip() for c in match.group(1).replace("、", ",").split(",") if c.strip()]
    return chars

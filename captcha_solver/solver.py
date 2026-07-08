"""
Main solver class — orchestrates the full captcha solving pipeline.

Usage:
    solver = TextClickCaptchaSolver(api_key="nvapi-...")
    solver.solve(page)
"""

from __future__ import annotations

import io
import re
from typing import Optional

from PIL import Image as PILImage
from playwright.sync_api import Page

from .captcha_locator import find_captcha_elements, parse_wordlist
from .contour import (
    build_grid_image,
    find_character_boxes,
    merge_overlapping_boxes,
    preprocess_image,
)
from .click import map_and_click
from .exceptions import CaptchaNotFoundError, ContourDetectionError, VisionAPIError
from .vision import classify_characters


class TextClickCaptchaSolver:
    """
    Solves text-sequence CAPTCHAs using OpenCV contour detection + vision AI.

    Pipeline:
        find captcha → screenshot → contour detection → grid image →
        vision classify → match wordlist → click in order

    Default configuration targets Chinese text-sequence CAPTCHAs
    (文字点选验证码) on logistics/port websites.
    """

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://integrate.api.nvidia.com/v1",
        vision_model: str = "meta/llama-3.2-90b-vision-instruct",
        contour_min_area: int = 80,
        contour_max_area: int = 50000,
        contour_min_size: int = 8,
        contour_max_size_ratio: float = 0.5,
        contour_min_aspect: float = 0.25,
        contour_max_aspect: float = 4.0,
        merge_threshold: int = 8,
    ):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.vision_model = vision_model

        # OpenCV contour parameters
        self.contour_min_area = contour_min_area
        self.contour_max_area = contour_max_area
        self.contour_min_size = contour_min_size
        self.contour_max_size_ratio = contour_max_size_ratio
        self.contour_min_aspect = contour_min_aspect
        self.contour_max_aspect = contour_max_aspect
        self.merge_threshold = merge_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(self, page: Page) -> bool:
        """
        Find, analyze, and click the captcha on the current page.

        Args:
            page: Playwright Page at the captcha state.

        Returns:
            True if captcha was solved and clicks performed.
        """
        captcha = find_captcha_elements(page)
        if not captcha:
            raise CaptchaNotFoundError(
                "No captcha found on page. Ensure the login form was submitted "
                "and a captcha popup is visible."
            )

        hint_text = captcha["hintText"]
        panel = captcha["panelRect"]
        wordlist = parse_wordlist(hint_text)

        if not wordlist:
            raise CaptchaNotFoundError(
                f"Could not parse wordlist from hint: {hint_text[:80]}"
            )

        # Screenshot the captcha panel (bypasses CORS)
        clip = {
            "x": panel["x"],
            "y": panel["y"],
            "width": panel["w"],
            "height": panel["h"],
        }
        screenshot_bytes = page.screenshot(clip=clip)
        snap_img = PILImage.open(io.BytesIO(screenshot_bytes))
        snap_w, snap_h = snap_img.size

        # OpenCV contour detection
        img, binary, img_w, img_h = preprocess_image(screenshot_bytes)
        boxes = find_character_boxes(
            binary, img_w, img_h,
            min_area=self.contour_min_area,
            max_area=self.contour_max_area,
            min_size=self.contour_min_size,
            max_size_ratio=self.contour_max_size_ratio,
            min_aspect=self.contour_min_aspect,
            max_aspect=self.contour_max_aspect,
        )

        if len(boxes) < len(wordlist):
            raise ContourDetectionError(
                f"Only {len(boxes)} candidates found, need ≥{len(wordlist)}. "
                "Try adjusting contour parameters."
            )

        boxes = merge_overlapping_boxes(boxes, merge_threshold=self.merge_threshold)

        # Build grid image for vision model
        _, grid_data_url = build_grid_image(img, boxes)

        # Vision classification
        classify_result = classify_characters(
            grid_data_url=grid_data_url,
            wordlist=wordlist,
            n_regions=len(boxes),
            api_key=self.api_key,
            api_base=self.api_base,
            model=self.vision_model,
        )

        if not classify_result:
            raise VisionAPIError(
                "Vision model returned no valid classification result."
            )

        # Click in order
        success = map_and_click(
            page=page,
            merged_boxes=boxes,
            classify_result=classify_result,
            wordlist=wordlist,
            panel_x=panel["x"],
            panel_y=panel["y"],
            css_w=panel["w"],
            css_h=panel["h"],
            snap_w=snap_w,
            snap_h=snap_h,
        )

        return success

    def solve_with_geometry(
        self,
        page: Page,
        wordlist: list[str],
        panel_rect: dict,
    ) -> bool:
        """
        Solve a captcha when the geometry is already known (e.g., from a previous
        detection call). Useful when you've manually located the captcha panel.

        Args:
            page: Playwright Page.
            wordlist: Target characters in click order.
            panel_rect: dict with keys x, y, w, h (CSS pixels).

        Returns:
            True if solved.
        """
        from .captcha_locator import find_captcha_elements

        clip = {
            "x": panel_rect["x"],
            "y": panel_rect["y"],
            "width": panel_rect["w"],
            "height": panel_rect["h"],
        }
        screenshot_bytes = page.screenshot(clip=clip)
        snap_img = PILImage.open(io.BytesIO(screenshot_bytes))
        snap_w, snap_h = snap_img.size

        img, binary, img_w, img_h = preprocess_image(screenshot_bytes)
        boxes = find_character_boxes(
            binary, img_w, img_h,
            min_area=self.contour_min_area,
            max_area=self.contour_max_area,
        )

        if len(boxes) < len(wordlist):
            return False

        boxes = merge_overlapping_boxes(boxes, merge_threshold=self.merge_threshold)
        _, grid_data_url = build_grid_image(img, boxes)

        classify_result = classify_characters(
            grid_data_url=grid_data_url,
            wordlist=wordlist,
            n_regions=len(boxes),
            api_key=self.api_key,
            api_base=self.api_base,
            model=self.vision_model,
        )

        if not classify_result:
            return False

        return map_and_click(
            page=page,
            merged_boxes=boxes,
            classify_result=classify_result,
            wordlist=wordlist,
            panel_x=panel_rect["x"],
            panel_y=panel_rect["y"],
            css_w=panel_rect["w"],
            css_h=panel_rect["h"],
            snap_w=snap_w,
            snap_h=snap_h,
        )

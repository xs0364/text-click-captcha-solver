"""
Test the full captcha solver pipeline.
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from captcha_solver.solver import TextClickCaptchaSolver
from captcha_solver.captcha_locator import find_captcha_elements, parse_wordlist
from captcha_solver.contour import (
    preprocess_image,
    find_character_boxes,
    merge_overlapping_boxes,
    build_grid_image,
)


def test_parse_wordlist():
    """Test wordlist parsing from hint text."""
    tests = [
        ("请依次点击【工、厂、大】", ["工", "厂", "大"]),
        ("请依次点击【唱、今】", ["唱", "今"]),
        ("请点击【验、证】", ["验", "证"]),
        ("no brackets here", []),
        ("【】", []),
        ("请依次点击【月、也】", ["月", "也"]),
    ]

    for hint, expected in tests:
        result = parse_wordlist(hint)
        assert result == expected, f"Failed: {hint} → {result} (expected {expected})"
    print("✅ test_parse_wordlist passed")


def test_contour_pipeline():
    """Test contour detection with a test image."""
    import cv2
    import numpy as np

    # Create a simple test image with characters
    img = np.ones((300, 500, 3), dtype=np.uint8) * 245

    # Draw rectangles simulating characters
    # Simulates: two target chars + one distractor
    cv2.rectangle(img, (50, 50), (100, 100), (0, 0, 0), -1)   # char 1
    cv2.rectangle(img, (200, 150), (250, 200), (0, 0, 0), -1)  # char 2
    cv2.rectangle(img, (350, 80), (390, 140), (100, 100, 100), -1)  # distractor

    cv2.imwrite("/tmp/test_captcha.png", img)

    with open("/tmp/test_captcha.png", "rb") as f:
        img_bytes = f.read()

    _, binary, w, h = preprocess_image(img_bytes)
    assert w == 500
    assert h == 300

    boxes = find_character_boxes(binary, w, h)
    merged = merge_overlapping_boxes(boxes)

    print(f"  Found {len(merged)} character boxes in test image")
    for bx in merged:
        print(f"    {bx}")

    assert len(merged) >= 2, f"Expected at least 2 boxes, got {len(merged)}"
    print("✅ test_contour_pipeline passed")


def test_build_grid():
    """Test grid image construction."""
    import cv2
    import numpy as np
    import base64

    img = np.ones((300, 500, 3), dtype=np.uint8) * 245
    boxes = [(50, 50, 50, 50), (200, 150, 50, 50), (350, 80, 40, 60)]

    grid_img, data_url = build_grid_image(img, boxes)
    assert data_url.startswith("data:image/png;base64,")
    print("✅ test_build_grid passed")


def test_full_integration():
    """Integration test requiring API key."""
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        print("⏭️ Skipping integration test — set NVIDIA_API_KEY")
        return

    solver = TextClickCaptchaSolver(api_key=api_key)
    assert solver.api_key == api_key
    assert solver.vision_model == "meta/llama-3.2-90b-vision-instruct"
    print("✅ test_full_integration passed")


if __name__ == "__main__":
    test_parse_wordlist()
    test_contour_pipeline()
    test_build_grid()
    test_full_integration()
    print("\n🎉 All tests passed!")

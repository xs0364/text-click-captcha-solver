"""
OpenCV contour detection pipeline.

Finds all candidate character boxes from a captcha screenshot:
1. Grayscale → GaussianBlur → adaptiveThreshold → morphology → dilation
2. findContours → filter by size/aspect ratio → merge overlapping
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np


def preprocess_image(
    image_bytes: bytes,
    blur_ksize: int = 5,
    block_size: int = 15,
    c_value: int = 2,
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """
    Preprocess captcha screenshot for contour detection.

    Pipeline: decode → grayscale → blur → adaptive threshold → close → open → dilate

    Args:
        image_bytes: Raw PNG bytes from Playwright screenshot.
        blur_ksize: Gaussian blur kernel size.
        block_size: Adaptive threshold block size (odd).
        c_value: Adaptive threshold C constant.

    Returns:
        Tuple of (original BGR image, dilated binary image, width, height).
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. Gaussian blur to reduce noise and fragment artifacts
    blurred = cv2.GaussianBlur(gray, (blur_ksize, blur_ksize), 0)

    # 2. Adaptive threshold (inverted: text = white)
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, block_size, c_value,
    )

    # 3. Morphology: close to connect broken strokes
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

    # 4. Dilate to connect nearby fragments
    dilated = cv2.dilate(cleaned, kernel, iterations=1)

    h, w = img.shape[:2]
    return img, dilated, w, h


def find_character_boxes(
    binary_img: np.ndarray,
    img_w: int,
    img_h: int,
    min_area: int = 80,
    max_area: int = 50000,
    min_size: int = 8,
    max_size_ratio: float = 0.5,
    min_aspect: float = 0.25,
    max_aspect: float = 4.0,
) -> list[tuple[int, int, int, int]]:
    """
    Find all candidate character bounding boxes using contour detection.

    Args:
        binary_img: Binary image from preprocessing.
        img_w: Image width in pixels.
        img_h: Image height in pixels.
        min_area: Minimum contour area for valid character.
        max_area: Maximum contour area.
        min_size: Minimum width/height in pixels.
        max_size_ratio: Maximum width/height as fraction of image.
        min_aspect: Minimum aspect ratio (w/h).
        max_aspect: Maximum aspect ratio.

    Returns:
        List of (x, y, w, h) bounding tuples, sorted by row then column.
    """
    contours, _ = cv2.findContours(binary_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    max_dim = max(img_w, img_h)

    boxes = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        aspect = cw / max(ch, 1)

        if not (min_area < area < max_area):
            continue
        if not (min_size < cw < img_w * max_size_ratio):
            continue
        if not (min_size < ch < img_h * max_size_ratio):
            continue
        if not (min_aspect < aspect < max_aspect):
            continue

        boxes.append((x, y, cw, ch))

    # Sort by rough row-then-column (row grouping = y // 30)
    boxes.sort(key=lambda b: (b[1] // 30, b[0]))
    return boxes


def merge_overlapping_boxes(
    boxes: list[tuple[int, int, int, int]],
    merge_threshold: int = 8,
) -> list[tuple[int, int, int, int]]:
    """
    Merge boxes that overlap or are very close together.

    Args:
        boxes: List of (x, y, w, h) tuples.
        merge_threshold: Maximum pixel gap to consider "mergeable".

    Returns:
        Merged list of (x, y, w, h) tuples.
    """
    if not boxes:
        return []

    merged = [boxes[0]]
    for bx in boxes[1:]:
        last = merged[-1]
        # Check overlap
        overlap = (
            bx[0] < last[0] + last[2] and bx[0] + bx[2] > last[0]
            and bx[1] < last[1] + last[3] and bx[1] + bx[3] > last[1]
        )
        gap_x = bx[0] - (last[0] + last[2])
        gap_y = bx[1] - (last[1] + last[3])

        if overlap or (abs(gap_x) < merge_threshold and abs(gap_y) < merge_threshold):
            nx = min(last[0], bx[0])
            ny = min(last[1], bx[1])
            nw = max(last[0] + last[2], bx[0] + bx[2]) - nx
            nh = max(last[1] + last[3], bx[1] + bx[3]) - ny
            merged[-1] = (nx, ny, nw, nh)
        else:
            merged.append(bx)

    return merged


def build_grid_image(
    img: np.ndarray,
    boxes: list[tuple[int, int, int, int]],
    cols: int = 5,
    pad: int = 10,
) -> tuple[np.ndarray, str]:
    """
    Build a grid image from character crop regions for vision model classification.

    Each crop is placed into a grid cell with its index number drawn above it.

    Args:
        img: Original BGR image.
        boxes: List of (x, y, w, h) character bounding boxes.
        cols: Number of columns in the grid.
        pad: Padding around each crop in pixels.

    Returns:
        Tuple of (grid BGR image as numpy array, base64 PNG data URL string).
    """
    import base64

    cell_w = max(b[2] for b in boxes) + pad * 2
    cell_h = max(b[3] for b in boxes) + pad * 2
    cols = min(len(boxes), cols)
    rows = (len(boxes) + cols - 1) // cols
    grid_w = cols * cell_w
    grid_h = rows * cell_h

    canvas = np.full((grid_h, grid_w, 3), 255, dtype=np.uint8)

    for i, (x, y, cw, ch) in enumerate(boxes):
        col = i % cols
        row = i // cols
        crop = img[y : y + ch, x : x + cw]
        cx_dst = col * cell_w + pad
        cy_dst = row * cell_h + pad
        canvas[cy_dst : cy_dst + ch, cx_dst : cx_dst + cw] = crop
        cv2.putText(
            canvas, str(i), (cx_dst, cy_dst - 3),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1,
        )

    _, buf = cv2.imencode(".png", canvas)
    b64 = base64.b64encode(buf.tobytes()).decode()
    return canvas, f"data:image/png;base64,{b64}"

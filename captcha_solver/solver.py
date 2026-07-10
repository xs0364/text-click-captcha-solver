"""
文字顺序点击验证码 (clickWord) 破解核心
========================================
基于 ddddocr 的离线验证码识别方案：
YOLO检测文字位置 → CNN识别文字 → 模糊匹配目标字 → 输出点击坐标

无需API密钥，完全离线运行。
依赖: pip install ddddocr Pillow
"""

import base64
import io
import re
from typing import Optional, List, Tuple
from difflib import SequenceMatcher

from PIL import Image
import ddddocr


class TextClickCaptchaSolver:
    """
    文字顺序点击验证码破解器 (主入口类)

    用法:
        solver = TextClickCaptchaSolver()
        points = solver.solve_image(image_base64, ["甲", "乙"])
        if points:
            for x, y in points:
                page.locator("img").click(position={"x": x, "y": y})
    """

    def __init__(self, show_ad: bool = False):
        """
        初始化OCR引擎

        Args:
            show_ad: 是否显示ddddocr广告信息
        """
        self.det = ddddocr.DdddOcr(det=True, ocr=False, show_ad=show_ad)
        self.ocr = ddddocr.DdddOcr(det=False, ocr=True, show_ad=show_ad)

    # ------------------------------------------------------------------
    # 核心求解方法
    # ------------------------------------------------------------------

    def solve_image(
        self,
        image_base64: str,
        target_words: list,
        min_similarity: float = 0.3,
    ) -> Optional[List[Tuple[int, int]]]:
        """
        识别验证码图片并返回按顺序的点击坐标（图片像素空间）

        Args:
            image_base64: 验证码图片的base64字符串（可含 data:url 前缀）
            target_words: 目标字列表，如 ['甲', '乙']
            min_similarity: 字符匹配最低相似度 (0~1)，默认0.3

        Returns:
            [(x, y), ...] 按目标顺序的图片像素坐标
            匹配失败返回 None，调用方应刷新验证码重试
        """
        # 1. 解码
        try:
            img_data = self._decode_base64(image_base64)
            if not img_data:
                return None
            img = Image.open(io.BytesIO(img_data))
        except Exception:
            return None
        img_w, img_h = img.size

        # 2. 检测文字区域
        bboxes = self.det.detection(img_data)
        if not bboxes:
            return None

        # 3. OCR识别每个区域
        candidates = []
        for bbox in bboxes:
            x1, y1, x2, y2 = [int(v) for v in bbox]
            pad = 8
            crop = img.crop((
                max(0, x1 - pad), max(0, y1 - pad),
                min(img_w, x2 + pad), min(img_h, y2 + pad)
            ))
            buf = io.BytesIO()
            crop.save(buf, format='PNG')
            try:
                char = self.ocr.classification(buf.getvalue()).strip()
                if char:
                    cx = (x1 + x2) // 2
                    cy = (y1 + y2) // 2
                    candidates.append({'char': char, 'x': cx, 'y': cy})
            except Exception:
                continue

        if not candidates:
            return None

        # 4. 模糊匹配
        used = set()
        result = []

        for target in target_words:
            best_idx = None
            best_score = 0.0
            for idx, c in enumerate(candidates):
                if idx in used:
                    continue
                score = SequenceMatcher(None, target, c['char']).ratio()
                if target == c['char']:
                    score = 1.0
                elif target in c['char'] or c['char'] in target:
                    score = max(score, 0.85)
                if score > best_score:
                    best_score = score
                    best_idx = idx

            if best_idx is not None and best_score >= min_similarity:
                used.add(best_idx)
                result.append((candidates[best_idx]['x'], candidates[best_idx]['y']))
            else:
                return None  # 匹配失败

        return result if len(result) == len(target_words) else None

    # ------------------------------------------------------------------
    # 兼容旧版接口：solve(page) — 基于Playwright Page
    # ------------------------------------------------------------------

    def solve(self, page) -> bool:
        """
        兼容旧版接口：接收 Playwright Page，自动完成定位→识别→点击

        注意：这要求 page 已经处于验证码弹窗状态。
        点击通过 page.locator("img").click(position=...) 完成。

        Args:
            page: Playwright Page 对象（已触发验证码弹窗）

        Returns:
            True 表示验证码已点击（需调用方自行验证结果）
            False 表示识别失败
        """
        # 查找验证码图片
        import re as _re

        img_src = page.evaluate("""
            () => {
                const img = document.querySelector('.verify-img-out img, [class*="captcha"] img, ' +
                    '.verifybox-bottom img, .mask img');
                return img ? img.src : null;
            }
        """)

        if not img_src:
            return False

        # 提取base64
        b64 = img_src.split(",")[-1] if "," in img_src else img_src

        # 获取提示文字
        prompt = page.evaluate("""
            () => {
                const texts = document.querySelectorAll('.verifybox-bottom, .verifybox-top, ' +
                    '[class*="captcha"]');
                for (const el of texts) {
                    const m = el.textContent.match(/【(.+?)】/);
                    if (m) return m[1];
                }
                return '';
            }
        """)

        words = [w.strip() for w in re.split(r'[、，,]', prompt) if w.strip()]
        if not words:
            return False

        points = self.solve_image(b64, words)
        if not points:
            return False

        # 获取图片位置
        img_box = page.evaluate("""
            () => {
                const img = document.querySelector('.verify-img-out img, ' +
                    '[class*="captcha"] img, .verifybox-bottom img, .mask img');
                if (!img) return null;
                const r = img.getBoundingClientRect();
                return { x: r.x, y: r.y, w: r.width, h: r.height,
                         nw: img.naturalWidth, nh: img.naturalHeight };
            }
        """)

        if not img_box:
            return False

        scale_x = img_box['w'] / img_box['nw']
        scale_y = img_box['h'] / img_box['nh']

        for i, (px, py) in enumerate(points):
            x = px * scale_x + (i * 7 + 3) % 5 - 2  # 微抖动
            y = py * scale_y + (i * 11 + 1) % 5 - 2
            page.mouse.click(img_box['x'] + x, img_box['y'] + y)
            page.wait_for_timeout(200)

        return True

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_base64(data: str) -> bytes:
        """安全解码base64（兼容带 data:url 前缀的情况）"""
        if ',' in data:
            data = data.split(',', 1)[1]
        return base64.b64decode(data)


# ==================== 快捷函数 ====================

_solver: Optional[TextClickCaptchaSolver] = None


def solve_clickword(
    image_base64: str,
    target_words: list,
    min_similarity: float = 0.3,
) -> Optional[List[Tuple[int, int]]]:
    """
    快捷调用（单例模式，避免重复初始化OCR引擎）

    Args:
        image_base64: 验证码图片base64
        target_words: 目标字列表
        min_similarity: 最低相似度

    Returns:
        [(x, y), ...] 或 None
    """
    global _solver
    if _solver is None:
        _solver = TextClickCaptchaSolver()
    return _solver.solve_image(image_base64, target_words, min_similarity)


def extract_words_from_prompt(prompt: str) -> list:
    """
    从提示文字中解析目标字

    支持格式:
        "请依次点击【甲、乙】" → ['甲', '乙']
        "请依次点击【甲,乙】" → ['甲', '乙']

    Args:
        prompt: 提示文字

    Returns:
        目标字列表
    """
    m = re.search(r'【(.+?)】', prompt)
    if m:
        return [w.strip() for w in re.split(r'[、，,]', m.group(1)) if w.strip()]
    return []

"""
文字顺序点击验证码 (clickWord) 破解模块
=====================================
可被其他项目直接导入使用，不依赖具体登录流程。

特点：
- 输入验证码base64图片 + 目标字列表
- 输出按顺序的点击坐标 (图片像素空间)
- 失败返回 None，调用方自行刷新重试

依赖: pip install ddddocr Pillow
"""

import base64
import io
from typing import Optional
from difflib import SequenceMatcher

from PIL import Image
import ddddocr


class ClickWordSolver:
    """
    文字顺序点击验证码破解器

    用法:
        solver = ClickWordSolver()
        points = solver.solve(image_base64, ["甲", "乙"])
        if points:
            for x, y in points:
                page.mouse.click(x, y)
        else:
            # 刷新验证码重试
    """

    def __init__(self, show_ad: bool = False):
        self.det = ddddocr.DdddOcr(det=True, ocr=False, show_ad=show_ad)
        self.ocr = ddddocr.DdddOcr(det=False, ocr=True, show_ad=show_ad)

    def solve(
        self,
        image_base64: str,
        target_words: list,
        min_similarity: float = 0.3,
    ) -> Optional[list]:
        """
        识别验证码并返回按顺序的点击坐标

        参数:
            image_base64: 验证码图片的base64字符串 (不含data:url前缀)
            target_words: 目标字列表，如 ['甲', '乙']
            min_similarity: 字符匹配最低相似度 (0~1)，默认0.3

        返回:
            [(x, y), ...] 按目标顺序的图片像素坐标
            如果匹配失败返回 None
        """
        # 1. 解码图片
        try:
            img_data = base64.b64decode(image_base64)
        except Exception:
            img_data = base64.b64decode(image_base64.split(",")[-1])

        img = Image.open(io.BytesIO(img_data))
        img_w, img_h = img.size

        # 2. 检测所有文字区域
        bboxes = self.det.detection(img_data)
        if not bboxes:
            return None

        # 3. 逐个识别
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

        # 4. 匹配目标字
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
                return None  # 匹配不上，需要刷新

        return result


# ==================== 快捷函数 ====================

_solver: Optional[ClickWordSolver] = None


def solve_clickword(
    image_base64: str,
    target_words: list,
    min_similarity: float = 0.3,
) -> Optional[list]:
    """
    快捷调用（单例模式，避免重复初始化OCR引擎）

    用法:
        points = solve_clickword(img_b64, ["甲", "乙"])
        if points:
            for x, y in points:
                ...
    """
    global _solver
    if _solver is None:
        _solver = ClickWordSolver()
    return _solver.solve(image_base64, target_words, min_similarity)


def extract_words_from_prompt(prompt: str) -> list:
    """
    从提示文字中解析目标字
    支持格式: "请依次点击【甲、乙】" / "请依次点击【甲,乙】"

    用法:
        words = extract_words_from_prompt("请依次点击【甲、乙】")
        # 返回 ['甲', '乙']
    """
    import re
    m = re.search(r'【(.+?)】', prompt)
    if m:
        return [w.strip() for w in re.split(r'[、，,]', m.group(1)) if w.strip()]
    return []


def extract_base64_from_dataurl(data_url: str) -> str:
    """
    从 data:image 前缀中提取纯base64

    用法:
        b64 = extract_base64_from_dataurl("data:image/png;base64,iVBOR...")
    """
    if ',' in data_url:
        return data_url.split(',', 1)[1]
    return data_url

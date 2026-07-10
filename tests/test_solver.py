"""
测试 clickWord 验证码破解器
"""

import sys
import os
import base64
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from captcha_solver import TextClickCaptchaSolver, solve_clickword, extract_words_from_prompt


def test_extract_words():
    """测试目标字提取"""
    tests = [
        ("请依次点击【工、厂、大】", ["工", "厂", "大"]),
        ("请依次点击【唱、今】", ["唱", "今"]),
        ("请点击【验、证】", ["验", "证"]),
        ("no brackets here", []),
        ("【】", []),
    ]
    for hint, expected in tests:
        result = extract_words_from_prompt(hint)
        assert result == expected, f"失败: {hint} → {result} (期望 {expected})"
    print(f"PASS: test_extract_words 通过")

def test_solver_init():
    """Testing solver initialization"""
    solver = TextClickCaptchaSolver()
    assert solver.det is not None
    assert solver.ocr is not None
    print(f"PASS: test_solver_init 通过")


def test_solve_fails_empty():
    """Empty input returns None"""
    result = solve_clickword("", ["甲"])
    assert result is None
    print(f"PASS: test_solve_fails_empty 通过")


def test_solve_fails_bad_base64():
    """Invalid base64 returns None"""
    result = solve_clickword("this-is-not-valid-base64!!!", ["甲"])
    assert result is None
    print(f"PASS: test_solve_fails_bad_base64 通过")


def test_solve_white_image():
    """纯白图片（无文字）返回 None"""
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (500, 300), (255, 255, 255)).save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()

    result = solve_clickword(b64, ["甲"])
    assert result is None
    print(f"PASS: test_solve_white_image 通过")


def test_solve_with_dataurl_prefix():
    """data:image 前缀的情况"""
    from PIL import Image
    import random
    buf = io.BytesIO()
    img = Image.new('RGB', (500, 300), (200, 200, 200))
    for i in range(3):
        x, y = random.randint(20, 450), random.randint(20, 250)
        for dx in range(20):
            for dy in range(20):
                if 0 <= x+dx < 500 and 0 <= y+dy < 300:
                    img.putpixel((x+dx, y+dy), (0, 0, 0))
    img.save(buf, format='PNG')
    raw_b64 = base64.b64encode(buf.getvalue()).decode()
    data_url = f"data:image/png;base64,{raw_b64}"

    result = solve_clickword(data_url, ["测"])
    print(f"  data_url输入正常处理，结果: {result}")
    print(f"PASS: test_solve_with_dataurl_prefix 通过")


def test_solver_singleton():
    """快捷函数的单例模式"""
    from captcha_solver.solver import _solver as s1
    solve_clickword("", ["甲"])
    from captcha_solver.solver import _solver as s2
    assert s2 is not None
    print(f"PASS: test_solver_singleton 通过")


if __name__ == "__main__":
    test_extract_words()
    test_solver_init()
    test_solve_fails_empty()
    test_solve_fails_bad_base64()
    test_solve_white_image()
    test_solve_with_dataurl_prefix()
    test_solver_singleton()
    print("\n=== All tests passed! ===")

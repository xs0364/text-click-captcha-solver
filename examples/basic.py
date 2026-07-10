"""
文字顺序点击验证码破解 — 使用示例

无需API Key，完全离线运行。

前置:
    1. pip install ddddocr Pillow playwright
    2. playwright install chromium

运行:
    python examples/basic.py
"""

import os
import sys
import re
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from captcha_solver import TextClickCaptchaSolver


def main():
    # ============ 配置 ============
    USERNAME = "your-username"
    PASSWORD = "your-password"
    TARGET_URL = "https://eport.cmp1872.com/login"

    # 初始化求解器（无需API Key！完全离线）
    solver = TextClickCaptchaSolver(show_ad=False)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, slow_mo=50,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.set_default_timeout(30000)

        # === 1. 打开网站 ===
        page.goto(TARGET_URL)
        page.wait_for_timeout(3000)

        # === 2. 填写登录信息 ===
        page.fill('#username', USERNAME)
        page.fill('input[type="password"]', PASSWORD)
        page.click('.tab-one .ivu-checkbox')
        page.wait_for_timeout(500)

        # === 3. 点击登录触发验证码 ===
        page.click('button:has-text("登录")')
        page.wait_for_timeout(3000)

        # === 4. 循环尝试破解验证码 ===
        for attempt in range(1, 31):
            print(f"\n--- 尝试 {attempt} ---")

            # 获取验证码图片(API方式: 拦截响应)
            # 简化演示: 直接从页面img元素获取

            img_src = page.evaluate("""
                () => {
                    const img = document.querySelector('.verify-img-out img');
                    return img ? img.src : null;
                }
            """)

            if not img_src:
                # 可能已经登录成功
                print("✅ 验证码已消失，登录成功！")
                break

            b64 = img_src.split(",")[-1] if "," in img_src else img_src

            # 获取提示文字 → 解析目标字
            prompt = page.evaluate("""
                () => {
                    const el = document.querySelector('.verifybox-bottom');
                    return el ? el.textContent.trim() : '';
                }
            """)

            m = re.search(r'【(.+?)】', prompt)
            if not m:
                print("❌ 无法解析目标字，刷新重试")
                page.click('.verifybox-refresh')
                page.wait_for_timeout(3000)
                continue

            words = [w.strip() for w in re.split(r'[、，,]', m.group(1)) if w.strip()]
            print(f"  目标字: {words}")

            # 求解
            points = solver.solve_image(b64, words)
            if not points:
                print("❌ OCR匹配失败，刷新重试")
                page.click('.verifybox-refresh')
                page.wait_for_timeout(3000)
                continue

            print(f"  点击坐标: {points}")

            # 点击
            img_box = page.evaluate("""
                () => {
                    const img = document.querySelector('.verify-img-out img');
                    if (!img) return null;
                    const r = img.getBoundingClientRect();
                    return { x: r.x, y: r.y, w: r.width, h: r.height,
                             nw: img.naturalWidth, nh: img.naturalHeight };
                }
            """)

            if not img_box:
                continue

            scale_x = img_box['w'] / img_box['nw']
            scale_y = img_box['h'] / img_box['nh']

            for i, (px, py) in enumerate(points):
                x = img_box['x'] + px * scale_x
                y = img_box['y'] + py * scale_y
                # 微抖动
                x += (i * 7 + 3) % 5 - 2
                y += (i * 11 + 1) % 5 - 2
                page.mouse.move(x, y, steps=10)
                page.wait_for_timeout(100)
                page.mouse.click(x, y)
                page.wait_for_timeout(200)

            # 等待验证结果
            page.wait_for_timeout(3000)

            # 检查遮罩是否消失
            mask_visible = page.evaluate("""
                () => {
                    const mask = document.querySelector('.mask');
                    if (!mask) return false;
                    return getComputedStyle(mask).display !== 'none';
                }
            """)

            if not mask_visible:
                print("\n✅✅✅ 验证通过！登录成功！✅✅✅")
                break

            print("❌ 验证失败，刷新重试")
            page.click('.verifybox-refresh')
            page.wait_for_timeout(3000)

        browser.close()


if __name__ == "__main__":
    main()

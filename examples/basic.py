"""
Basic usage example — solve a text-sequence CAPTCHA on a target page.

Prerequisites:
    1. pip install text-click-captcha-solver
    2. playwright install chromium
    3. Set your NVIDIA NIM API key

Usage:
    python examples/basic.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

from captcha_solver import TextClickCaptchaSolver


def main():
    # API key — get yours from https://build.nvidia.com/
    api_key = os.environ.get("NVIDIA_API_KEY", "nvapi-your-key-here")

    solver = TextClickCaptchaSolver(
        api_key=api_key,
        api_base="https://integrate.api.nvidia.com/v1",
        vision_model="meta/llama-3.2-90b-vision-instruct",
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.set_default_timeout(60000)

        # --- Replace with your target page ---
        page.goto("https://eport.cmp1872.com/login")
        page.fill('input[type="text"]', "your-username")
        page.fill('input[type="password"]', "your-password")

        # Click login to trigger captcha
        page.click('button:has-text("登录")')
        page.wait_for_timeout(5000)

        # Solve captcha
        try:
            success = solver.solve(page)
            if success:
                print("✅ Captcha solved!")
                # If captcha verification is auto, wait for redirect
                # Or re-click the login button if the form was blocked
                page.wait_for_timeout(5000)
                print(f"   Final URL: {page.url}")
            else:
                print("❌ Failed to solve captcha")
        except Exception as e:
            print(f"💥 Error: {e}")

        browser.close()


if __name__ == "__main__":
    main()

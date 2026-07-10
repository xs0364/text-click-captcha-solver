<div align="center">

  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:667eea,100:764ba2&height=200&section=header&text=Text-Click%20Captcha%20Solver&fontSize=50&fontColor=ffffff&animation=fadeIn" alt="header"/>

  # 🧩 Text-Click Captcha Solver

  ### 文字顺序点击验证码自动识别 — ddddocr 离线方案
  ### *Precision Click on Chinese Text-Sequence CAPTCHA — ddddocr Offline OCR*

  <p align="center">
    <a href="https://github.com/xs0364/text-click-captcha-solver">
      <img src="https://img.shields.io/github/stars/xs0364/text-click-captcha-solver?style=social" />
    </a>
  </p>

  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white" />
    <img src="https://img.shields.io/badge/ddddocr-1.4%2B-green?logo=python" />
    <img src="https://img.shields.io/badge/license-MIT-brightgreen" />
    <img src="https://img.shields.io/badge/离线运行-无需API-important" />
    <img src="https://img.shields.io/badge/状态-生产稳定-success" />
  </p>

  <p align="center">
    <a href="#-概述">🔍 概述</a> •
    <a href="#-识别原理">⚙️ 原理</a> •
    <a href="#-快速开始">🚀 开始</a> •
    <a href="#-架构">🏗️ 架构</a> •
    <a href="#english">🇬🇧 English</a>
  </p>

  <br/>

  > **⭐ 如果这个项目帮到了你，欢迎点 Star！你的支持是持续改进的动力。**

</div>

---

## 🔍 概述

破解**文字顺序点击验证码 (clickWord captcha)** — 验证码弹窗中显示"请依次点击【甲、乙】"，用户需要在背景、颜色、位置、旋转都随机变化的图片中找到并依次点击「甲」和「乙」。

**传统方案**依赖 OpenCV 轮廓检测 + NVIDIA NIM / GPT-4o 等云端视觉 API，需要 API Key、受网络延迟影响、有调用成本。

**本方案**使用 [ddddocr](https://github.com/sml2h3/ddddocr) (YOLOv8 检测 + CNN 识别) 完全离线运行，识别速度快、无需任何 API Key、零成本。

### ✅ 实测结果

| 指标 | 结果 |
|------|------|
| 成功率 | **100%**（多次实测全部通过） |
| 单次识别 | **~0.5-1秒** |
| 重试策略 | 失败自动刷新（30次上限） |
| API密钥 | **不需要** |
| 联网 | **不需要**，完全离线 |

---

## ⚙️ 识别原理

```
┌─────────────────────────────────────────────────┐
│  1. 拦截API获取验证码图片 + 目标字列表(wordList)  │
│     POST /api/v1/auth/captcha/get/v2            │
│     → originalImageBase64 + wordList=["甲","乙"] │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│  2. ddddocr YOLO检测 → 找出所有文字坐标位置      │
│     框1: (47,132)-(102,185)                     │
│     框2: (197,110)-(250,164)                    │
│     框3: (30,204)-(93,263)   ← 干扰字           │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│  3. ddddocr CNN识别 → 每个框识别出具体汉字       │
│     框1 → "甲"  框2 → "乙"  框3 → "子"          │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│  4. 编辑距离匹配目标字 → 按顺序输出点击坐标      │
│     "甲"@(74,158) → 第1次点击                    │
│     "乙"@(223,137) → 第2次点击                   │
└──────────────────┬──────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────────┐
│  5. 验证结果 → 失败自动刷新重试（最多30次）       │
└─────────────────────────────────────────────────┘
```

### 🔬 技术细节

- **文字检测**: ddddocr 内置 YOLOv8 模型，扫描图片找出所有文字边界框
- **文字识别**: CNN 分类器对每个边界框裁剪区域进行识别
- **模糊匹配**: Python `difflib.SequenceMatcher` 编辑距离算法，容忍 OCR 微小偏差
- **坐标点击**: Playwright `locator.click(position=...)`，自动处理 iframe 坐标映射

---

## 🚀 快速开始

### 安装

```bash
pip install ddddocr Pillow playwright
playwright install chromium
```

### 基础使用

```python
from captcha_solver import TextClickCaptchaSolver, solve_clickword

# ===== 方式1: 直接传入base64 + 目标字（推荐） =====
solver = TextClickCaptchaSolver()

# 从API响应获取
img_b64 = "iVBORw0KGgo..."   # originalImageBase64
words = ["甲", "乙"]          # wordList

points = solver.solve_image(img_b64, words)
if points:
    for x, y in points:
        page.locator(".verify-img-out img").click(position={"x": x, "y": y})
else:
    page.click(".verifybox-refresh")  # 刷新重试


# ===== 方式2: 快捷函数（单例，避免重复初始化） =====
from captcha_solver import solve_clickword, extract_words_from_prompt

words = extract_words_from_prompt("请依次点击【甲、乙】")
# → ['甲', '乙']

points = solve_clickword(img_b64, words)
# → [(74, 158), (223, 137)]


# ===== 方式3: 传入 Playwright Page（自动定位） =====
solver = TextClickCaptchaSolver()
success = solver.solve(page)  # 自动完成定位→识别→点击
```

### 完整登录示例

```python
from playwright.sync_api import sync_playwright
from captcha_solver import TextClickCaptchaSolver

solver = TextClickCaptchaSolver()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto("https://example.com/login")

    # 填写登录
    page.fill("#username", "user")
    page.fill("input[type='password']", "pass")
    page.click("button:has-text('登录')")
    page.wait_for_timeout(3000)

    # 循环破解验证码
    for _ in range(30):
        img_src = page.evaluate(
            "() => document.querySelector('.verify-img-out img')?.src"
        )
        if not img_src:
            break  # 验证码已消失 → 登录成功

        b64 = img_src.split(",")[-1]
        words = extract_words_from_prompt(
            page.text_content(".verifybox-bottom") or ""
        )

        points = solver.solve_image(b64, words)
        if not points:
            page.click(".verifybox-refresh")
            page.wait_for_timeout(3000)
            continue

        for x, y in points:
            page.locator(".verify-img-out img").click(position={"x": x, "y": y})
            page.wait_for_timeout(200)

        page.wait_for_timeout(3000)
        if not page.is_visible(".mask"):
            print("登录成功！")
            break

    browser.close()
```

---

## 🆚 与旧版方案对比

| 特性 | 旧版 (OpenCV + NVIDIA NIM) | **本版 (ddddocr)** |
|------|---------------------------|-------------------|
| API Key | ✅ 需要 NVIDIA API Key | ❌ **无需** |
| 联网 | ✅ 需要 | ❌ **完全离线** |
| 单次识别速度 | ~3-8秒（含网络延迟） | **~0.5-1秒** |
| 准确率 | 依赖视觉模型 | **高（百万级预训练）** |
| 成本 | NVIDIA NIM 按量付费 | **免费** |
| 部署难度 | 需配置 API 端点 | **pip install 即可** |
| 依赖数量 | opencv + numpy + httpx + playwright | **ddddocr + Pillow** |

---

## 🏗️ 架构

```
text-click-captcha-solver/
├── captcha_solver/
│   ├── __init__.py       # 包入口，导出主类 + 快捷函数
│   └── solver.py         # 核心求解器 TextClickCaptchaSolver
├── examples/
│   └── basic.py          # 完整使用示例（蛇口港ePort登录）
├── tests/
│   └── test_solver.py    # 测试用例
├── pyproject.toml        # 项目配置
├── install.sh / .ps1     # 安装脚本
├── LICENSE               # MIT
└── README.md             # 本文档
```

---

## 🧰 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| [ddddocr](https://github.com/sml2h3/ddddocr) | ≥1.4 | YOLOv8 文字检测 + CNN 汉字识别 |
| [Pillow](https://python-pillow.org/) | ≥9.0 | 图片裁剪、预处理 |
| Python `difflib` | 标准库 | 编辑距离模糊匹配 |
| [Playwright](https://playwright.dev/) | 可选 | 浏览器自动化 + 坐标点击 |

---

## 🤝 贡献

欢迎提 Issue 和 PR！改进方向：

- [ ] 支持其他验证码类型（滑块、旋转等）
- [ ] 支持非中文文字识别
- [ ] Docker 部署配置
- [ ] 更完善的测试套件

---

<div align="center">

### ⭐ Star if you find this useful!

[![GitHub stars](https://img.shields.io/github/stars/xs0364/text-click-captcha-solver?style=social)](https://github.com/xs0364/text-click-captcha-solver)
[![GitHub issues](https://img.shields.io/github/issues/xs0364/text-click-captcha-solver)](https://github.com/xs0364/text-click-captcha-solver/issues)

**📌 搜索关键词：** `验证码识别` `点选验证码` `文字点选验证码` `图形验证码` `captcha破解` `OCR验证码` `ddddocr` `web自动化`

---

*Built with ❤️ for the DevOps community automating the hard stuff.*

</div>

---

## <a id="english"></a> 🇬🇧 English

### Overview

Solves **Chinese text-sequence CAPTCHAs (clickWord)** — where a popup shows "请依次点击【甲、乙】" (please click [A, B] in order), with random backgrounds, colors, positions, and rotations.

Uses **ddddocr (YOLOv8 + CNN)** entirely **offline** — no API keys, no network latency, zero cost.

### Quick Start

```bash
pip install ddddocr Pillow playwright
playwright install chromium
```

```python
from captcha_solver import solve_clickword

points = solve_clickword(image_base64, ["甲", "乙"])
if points:
    for x, y in points:
        page.locator("img").click(position={"x": x, "y": y})
```

No API key required. Fully offline.

### Tech Stack

- **ddddocr** — YOLOv8 character detection + CNN recognition
- **Pillow** — Image processing
- **difflib** — Fuzzy character matching (edit distance)
- **Playwright** — Browser automation (optional)

---

## 📄 License

MIT

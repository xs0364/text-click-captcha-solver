# Text-Click Captcha Solver
# 文字顺序点击验证码自动破解
# Version: 1.0.0

from .solver import TextClickCaptchaSolver, solve_clickword, extract_words_from_prompt

__all__ = [
    "TextClickCaptchaSolver",
    "solve_clickword",
    "extract_words_from_prompt",
]

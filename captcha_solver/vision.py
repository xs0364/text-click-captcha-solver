"""
Vision AI API client for character classification.

Takes a grid image of cropped character regions and returns which
region contains which character, using an OpenAI-compatible vision API.

Default: NVIDIA NIM (meta/llama-3.2-90b-vision-instruct)
Can be swapped to: GPT-4o, Gemini, Claude, or any vision model.
"""

from __future__ import annotations

import json
import re
from typing import Optional

import httpx


# Default classification prompt — guided JSON output
_CLASSIFY_PROMPT_TPL = """Identify the Chinese character in each numbered region.

The image has {n_regions} regions numbered 0 to {n_regions-1}. Target characters: {targets}

For each region, tell me:
1. The actual character shown
2. Whether it matches any target character

Return ONLY a JSON array, no explanation:
[{{"n":0,"c":"字","t":false}},...]
'c' = actual character, 't' = true if it's a target character."""


def classify_characters(
    grid_data_url: str,
    wordlist: list[str],
    n_regions: int,
    api_key: str,
    api_base: str = "https://integrate.api.nvidia.com/v1",
    model: str = "meta/llama-3.2-90b-vision-instruct",
    timeout: int = 60,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> Optional[list[dict]]:
    """
    Send a grid image to the vision API and classify each region's character.

    Args:
        grid_data_url: base64 PNG data URL of the grid image.
        wordlist: List of target characters to match.
        n_regions: Number of regions in the grid.
        api_key: API key for the vision service.
        api_base: API base URL (OpenAI-compatible).
        model: Model name.
        timeout: HTTP request timeout in seconds.
        temperature: Model temperature (low = deterministic).
        max_tokens: Max tokens for response.

    Returns:
        List of dicts: [{"n": int, "c": str, "t": bool}, ...] or None on failure.
    """
    targets_str = "、".join(wordlist)
    prompt = _CLASSIFY_PROMPT_TPL.format(n_regions=n_regions, targets=targets_str)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": grid_data_url}},
                ],
            }
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        resp = httpx.post(
            f"{api_base.rstrip('/')}/chat/completions",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
    except httpx.TimeoutException:
        print("  [VISION] API timeout")
        return None
    except httpx.RequestError as e:
        print(f"  [VISION] API request failed: {e}")
        return None

    if resp.status_code != 200:
        print(f"  [VISION] API error {resp.status_code}: {resp.text[:200]}")
        return None

    content = resp.json()["choices"][0]["message"]["content"]
    return _parse_json_response(content)


def _parse_json_response(content: str) -> Optional[list[dict]]:
    """
    Extract and parse a JSON array from the vision model response.

    Handles markdown-wrapped JSON and text-before-JSON patterns.
    """
    # Strip markdown code fences
    json_str = content
    if "```json" in json_str:
        json_str = json_str.split("```json")[1]
    if "```" in json_str:
        json_str = json_str.split("```")[0]
    json_str = json_str.strip()

    # Find first [ and last ]
    start = json_str.find("[")
    end = json_str.rfind("]")
    if start < 0 or end <= start:
        print(f"  [VISION] No JSON array found in response:\n{content[:200]}")
        return None
    json_str = json_str[start : end + 1]

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"  [VISION] JSON parse error: {e}")
        print(f"  [VISION] Raw extract: {json_str[:200]}")
        return None

    if not isinstance(result, list):
        return None

    # Validate and standardize
    validated = []
    for item in result:
        if isinstance(item, dict) and "n" in item and "c" in item:
            validated.append({
                "n": int(item["n"]),
                "c": str(item.get("c", "?")).strip(),
                "t": bool(item.get("t", False)),
            })

    return validated

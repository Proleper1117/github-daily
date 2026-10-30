#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 GitHub 实时拉取候选仓库（星标 > 10000）。

只依赖 GitHub 搜索 API（未认证时 10 次/分钟），用少量查询覆盖多个方向：
AI 前沿、Agent/Skill、Awesome 清单、办公提效、自动化、量化、自建服务等。

输出 candidates.json：{"owner/name": {...}, ...}
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "candidates.json"
MIN_STARS = 10000
PER_PAGE = 60
DELAY = 7.0  # 搜索 API 限 10 次/分钟，留出余量

# 在 GitHub Actions 运行时可注入 GITHUB_TOKEN 提高限流（未认证仅 10 次/分钟）
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""

QUERIES = [
    "topic:ai",
    "topic:llm",
    "topic:agent",
    "topic:mcp",
    "topic:awesome",
    "topic:productivity",
    "topic:automation",
    "topic:workflow",
    "topic:self-hosted",
    "topic:quant",
    "topic:data-science",
    "topic:video",
    "topic:trading",
    "topic:finance",
    "topic:cli",
    "topic:developer-tools",
    "topic:learning",
    "topic:interview",
    "topic:scraping",
    "topic:saas",
]


def api_get(url: str) -> dict:
    headers = {
        "User-Agent": "dsh-daily-digest",
        "Accept": "application/vnd.github+json",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    found: dict[str, dict] = {}
    used_queries = 0

    for i, topic in enumerate(QUERIES, 1):
        q = f"{topic}+stars:%3E{MIN_STARS}"
        url = (
            f"https://api.github.com/search/repositories"
            f"?q={q}&sort=stars&order=desc&per_page={PER_PAGE}"
        )
        print(f"[{i}/{len(QUERIES)}] {topic} ...", end="", flush=True)
        try:
            data = api_get(url)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:200]
            print(f" HTTP {e.code}: {body}")
            if e.code == 403:  # 限流，等一分钟再继续
                print("   等待 60 秒后重试...")
                time.sleep(60)
                try:
                    data = api_get(url)
                except Exception as e2:  # noqa: BLE001
                    print(f"   重试失败: {e2}")
                    continue
            else:
                continue
        except Exception as e:  # noqa: BLE001
            print(f" 失败: {e}")
            continue

        added = 0
        for item in data.get("items", []):
            if (item.get("stargazers_count") or 0) < MIN_STARS:
                continue
            name = item["full_name"]
            if name.lower() in found:
                continue
            found[name.lower()] = {
                "name": item["name"],
                "owner": item["owner"]["login"],
                "fullName": name,
                "stars": item["stargazers_count"],
                "language": item.get("language"),
                "description": (item.get("description") or "").strip(),
                "topics": item.get("topics") or [],
                "url": item["html_url"],
                "updatedAt": item.get("pushed_at"),
                "archived": item.get("archived", False),
            }
            added += 1
        used_queries += 1
        print(f" +{added}（累计 {len(found)}）")
        if i < len(QUERIES):
            time.sleep(DELAY)

    # 去掉归档仓库（不会再更新，学习价值低）
    before = len(found)
    found = {k: v for k, v in found.items() if not v["archived"]}

    OUT.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n[完成] 成功查询 {used_queries}/{len(QUERIES)}，候选 {before} → 过滤归档后 {len(found)}")
    print(f"       已写入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

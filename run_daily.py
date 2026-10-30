#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""每日更新入口（带防重复守卫）。

为什么需要这个：定时任务可能因为电脑关机/未登录而错过。
本脚本先检查「今天的数据是否已经生成」：
  - 已是今天 → 直接跳过（避免开机、登录、多次触发时重复抓取）
  - 不是今天 → 执行完整流程：抓取 → 挑选 → 发布 → 部署

这样配合多个触发时机（8点 / 20点 / 登录时），无论电脑什么时候开机，
当天都能补上一次更新，且最多跑一次。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data.js"


def today_done() -> bool:
    """data.js 里第一天的日期是不是今天。"""
    try:
        text = DATA.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    m = re.search(r'"date":\s*"(\d{4}-\d{2}-\d{2})"', text)
    if not m:
        return False
    return m.group(1) == date.today().isoformat()


def run(script: str, extra_args: list[str] | None = None) -> int:
    print(f"\n----- 运行 {script} -----", flush=True)
    cmd = [sys.executable, str(ROOT / script)] + (extra_args or [])
    res = subprocess.run(
        cmd,
        cwd=str(ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return res.returncode


def main() -> int:
    force = "--force" in sys.argv
    no_deploy = "--no-deploy" in sys.argv
    write_root = "--root" in sys.argv

    if not force and today_done():
        print(f"[跳过] 今天（{date.today().isoformat()}）的数据已经生成过了。")
        return 0

    print(f"[开始] 更新 {date.today().isoformat()} 的每日精品")
    steps = ["fetch_candidates.py", "build_daily.py"]
    for script in steps:
        code = run(script)
        if code != 0:
            print(f"[失败] {script} 返回 {code}，中止后续步骤。")
            return code

    ps_args = []
    if no_deploy:
        ps_args.append("--no-deploy")
    if write_root:
        ps_args.append("--root")
    code = run("publish_sync.py", ps_args)
    if code != 0:
        return code

    print("\n[完成] 今日更新结束。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

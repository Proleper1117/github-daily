#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成每日精选：从候选池里按日期确定性挑选 10 个项目，写入 data.js。

设计要点：
- 用日期做随机种子 → 同一天结果固定，可复现；不同天自动换一批
- 按分类配额挑选（AI前沿/变现/提效/量化/学习/Awesome），保证每天覆盖均衡
- 回溯 7 天已选项目并排除 → 每天都是"新的 10 个"
- 输出 data.js（含今天 + 最近 7 天），页面用 <script src> 加载，file:// 直接可用
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "candidates.json"
OUT = ROOT / "data.js"

# 分类配额（合计 10）
QUOTA = {
    "AI前沿": 3,
    "AI变现": 2,
    "工作提效": 2,
    "量化交易": 1,
    "学习资源": 1,
    "Awesome精选": 1,
}

# topics → 分类（未人工标注时的兜底）
TOPIC_MAP = {
    "ai": "AI前沿", "llm": "AI前沿", "agent": "AI前沿", "agents": "AI前沿",
    "mcp": "AI前沿", "prompt-engineering": "AI前沿", "prompts": "AI前沿",
    "gpt": "AI前沿", "chatgpt": "AI前沿", "openai": "AI前沿",
    "awesome": "Awesome精选", "awesome-list": "Awesome精选",
    "automation": "AI变现", "workflow": "AI变现", "no-code": "AI变现",
    "low-code": "AI变现",
    "productivity": "工作提效", "self-hosted": "工作提效", "cli": "工作提效",
    "tools": "工作提效", "developer-tools": "工作提效",
    "quant": "量化交易", "trading": "量化交易", "finance": "量化交易",
    "crypto": "量化交易",
    "video": "AI变现",
    "learning": "学习资源", "interview": "学习资源", "course": "学习资源",
    "tutorial": "学习资源",
}

CAT_HEURISTIC_MONEY = {
    "AI前沿": "学懂后做 AI 应用定制/咨询，是当下最好卖的技能",
    "AI变现": "工具类项目，直接可接单或做产品",
    "工作提效": "提效工具，省下的时间本身就是收益，也可做效率内容",
    "量化交易": "交易/数据方向，注意实盘风险，先模拟盘",
    "学习资源": "底层能力建设，长期回报最高",
    "Awesome精选": "资源导航，适合做内容与选品",
}

# 未人工标注项目的通用工作流模板（按分类）
CAT_WORKFLOW = {
    "AI前沿": [
        "通读项目文档，跑通官方 demo，弄清它能解决什么问题",
        "在自己的真实场景复现一次，记录省下了什么",
        "挑 3 个可复用场景，各做一份演示（录屏 2 分钟）",
        "把演示发给需要的人（行业群/小红书/私信），验证有没有人愿意付费",
        "先低价接 3~5 单攒案例，再逐步提价并标准化交付流程",
    ],
    "AI变现": [
        "部署并跑通项目，截图关键效果",
        "选 2 个高频变现场景，各打一个可交付模板",
        "做作品集页/演示视频，标清价格与周期",
        "在闲鱼/小红书/行业群发布，先接小单验证需求",
        "按「定金 + 验收」收款，交付后推月度维护",
    ],
    "工作提效": [
        "把项目跑起来，用自己的真实数据试一次",
        "整理「前后对比」，量化省下来的时间",
        "把流程固化成模板或脚本",
        "在团队/社群分享，验证通用性",
        "做成教程或代做服务对外出售",
    ],
    "量化交易": [
        "部署项目，用历史数据跑通回测",
        "先做全样本外回测（不要只看训练集），记录夏普与回撤",
        "上模拟盘验证 1 个月，对比回测与实盘差异",
        "把流程固化成可复用的策略/工具",
        "对外提供服务时明确免责声明，先收技术服务费而非分成",
    ],
    "学习资源": [
        "通读资料，整理出自己的知识地图",
        "挑 3 个核心点动手复现一次",
        "把理解写成笔记或教程",
        "形成可分享的成果（文章/视频/项目）",
        "用成果换机会：面试作品、课程、或社群分享",
    ],
    "Awesome精选": [
        "按清单挑 5 个与自己方向相关的项目",
        "逐个验证可用性，筛出真正好用的 2~3 个",
        "把筛选结果写成测评/导航内容",
        "做成导航站或合集内容引流",
        "接广告/推广或做付费清单",
    ],
}


def infer_category(repo: dict) -> str:
    topics = [t.lower() for t in (repo.get("topics") or [])]
    for t in topics:
        if t in TOPIC_MAP:
            return TOPIC_MAP[t]
    name = repo["fullName"].lower()
    if "awesome" in name:
        return "Awesome精选"
    return "学习资源"


def build_pool(candidates: dict, annotations: dict) -> dict[str, list[dict]]:
    """按分类把候选仓库分桶。"""
    pool: dict[str, list[dict]] = {c: [] for c in QUOTA}
    for key, repo in candidates.items():
        ann = annotations.get(key)
        cat = ann["cat"] if ann else infer_category(repo)
        if cat not in pool:
            cat = "学习资源"
        item = {
            "fullName": repo["fullName"],
            "name": repo["name"],
            "owner": repo["owner"],
            "url": repo["url"],
            "stars": repo["stars"],
            "language": repo.get("language"),
            "description": (repo.get("description") or "").strip(),
            "cat": cat,
            "money": ann["money"] if ann else CAT_HEURISTIC_MONEY[cat],
            "buyer": ann.get("buyer", "—") if ann else "—",
            "price": ann.get("price", "—") if ann else "—",
            "cycle": ann.get("cycle", "—") if ann else "—",
            "tags": ann["tags"] if ann else [],
            "diff": ann["diff"] if ann else 2,
            "curated": ann is not None,
            "awesome": cat == "Awesome精选" or "awesome" in repo["fullName"].lower(),
            "workflow": ann["workflow"] if ann else CAT_WORKFLOW.get(cat, CAT_WORKFLOW["学习资源"]),
        }
        pool[cat].append(item)
    # 每个分类内按星标降序（越热越优先，但不强制）
    for cat in pool:
        pool[cat].sort(key=lambda x: -x["stars"])
    return pool


def pick_for_date(d: date, pool: dict[str, list[dict]], used: set[str]) -> list[dict]:
    """按分类配额为某天挑 10 个，跳过 used 中的项目。"""
    rng = random.Random(d.isoformat())
    picked: list[dict] = []
    picked_names: set[str] = set()

    def take(cat: str, n: int) -> None:
        members = [x for x in pool[cat] if x["fullName"] not in used and x["fullName"] not in picked_names]
        rng.shuffle(members)
        # 优先人工标注过的（质量更高），再按热度补足
        curated = [x for x in members if x["curated"]]
        other = [x for x in members if not x["curated"]]
        ordered = curated + other
        for x in ordered[:n]:
            picked.append(x)
            picked_names.add(x["fullName"])

    for cat, n in QUOTA.items():
        take(cat, n)

    # 配额没凑满时，从剩下的分类补
    if len(picked) < 10:
        rest = [x for cat in pool for x in pool[cat]
                if x["fullName"] not in used and x["fullName"] not in picked_names]
        rng.shuffle(rest)
        for x in rest:
            if len(picked) >= 10:
                break
            picked.append(x)
            picked_names.add(x["fullName"])

    picked.sort(key=lambda x: -x["stars"])
    return picked[:10]


def main() -> int:
    # utf-8-sig：PowerShell 写文件可能带 BOM，容忍一下
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8-sig"))
    from annotations import ANNOTATIONS  # noqa: PLC0415

    # 合并「手动添加」的标注（优先级最高，覆盖同名项目）
    annotations = dict(ANNOTATIONS)
    manual_path = ROOT / "manual_annotations.json"
    if manual_path.exists():
        manual = json.loads(manual_path.read_text(encoding="utf-8"))
        annotations.update(manual)
        print(f"[手动标注] 已合并 {len(manual)} 个手动添加的项目")

    pool = build_pool(candidates, annotations)
    print("候选池分布：")
    for cat, items in pool.items():
        print(f"  {cat:<10} {len(items):>4} 个（人工标注 {sum(1 for x in items if x['curated'])}）")

    today = date.today()
    days = []
    used: set[str] = set()
    # 从今天往前生成：今天优先拿到人工标注的精选，之后几天依次用剩下的
    for offset in range(0, 8):
        d = today - timedelta(days=offset)
        picks = pick_for_date(d, pool, used)
        used.update(x["fullName"] for x in picks)
        days.append({
            "date": d.isoformat(),
            "weekday": "一二三四五六日"[d.weekday()],
            "issue": (d - date(2026, 1, 1)).days + 1,
            "items": picks,
        })

    # 应用「今日追加」：手动添加的项目，今天这批一定包含
    extra_path = ROOT / "今日追加.json"
    if extra_path.exists():
        try:
            extra = json.loads(extra_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            extra = {}
        today_iso = today.isoformat()
        if extra.get("date") == today_iso and extra.get("projects"):
            by_name = {x["fullName"]: x for cat in pool for x in pool[cat]}
            todays = days[0]["items"]
            present = {x["fullName"] for x in todays}
            forced = [by_name[n] for n in extra["projects"] if n in by_name and n not in present]
            if forced:
                # 替换掉当日星标最低的若干个，优先保留分类均衡
                todays.sort(key=lambda x: x["stars"])
                for f in forced[:len(todays)]:
                    if todays:
                        todays.pop(0)  # 去掉星标最低的
                        todays.append(f)
                todays.sort(key=lambda x: -x["stars"])
                print(f"[今日追加] 已把 {len(forced)} 个手动添加的项目放进今天的列表")

    payload = {
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "starsThreshold": 10000,
        "totalCandidates": len(candidates),
        "days": days,
        # 完整候选池：页面上的「换一批」直接用它在本地重新挑选，不再请求 GitHub
        "pool": [x for cat in pool for x in pool[cat]],
    }
    body = "// 本文件由 build_daily.py 自动生成，请勿手改\nwindow.DAILY_DATA = " + \
           json.dumps(payload, ensure_ascii=False, indent=1) + ";\n"
    OUT.write_text(body, encoding="utf-8")

    t = days[0]
    print(f"\n[完成] 生成 {len(days)} 天数据，今天 {t['date']}（第 {t['issue']} 期）10 个项目：")
    for i, it in enumerate(t["items"], 1):
        print(f"  {i:2d}. [{it['cat']:<6}] {it['fullName']:<42} ★{it['stars']:>7,}")
    print(f"\n写入 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""发布同步：把网页文件复制到「发布」目录；若配置了 GitHub token 则自动部署。

被 更新内容.cmd / 定时更新.cmd 调用（这两个 .cmd 保持纯 ASCII，
避免 cmd 代码页把中文路径读坏 —— 中文逻辑都放在这里）。
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

ROOT = Path(__file__).resolve().parent
SRC_FILES = ["index.html", "data.js", "app.js", "style.css"]
PUB = ROOT / "发布"


def _hash8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


def sync(write_root: bool = False) -> None:
    PUB.mkdir(exist_ok=True)
    for name in SRC_FILES:
        src = ROOT / name
        if src.exists():
            shutil.copy2(src, PUB / name)

    # 给 CSS/JS 引用加内容哈希版本号，避免 GitHub Pages 的 10 分钟缓存
    # 让用户继续看到旧样式（踩过：修复了却「还是关不掉」）。
    index = PUB / "index.html"
    css_ver = _hash8(PUB / "style.css") if (PUB / "style.css").exists() else "1"
    js_ver = _hash8(PUB / "app.js") if (PUB / "app.js").exists() else "1"
    html = index.read_text(encoding="utf-8")
    html = re.sub(r"style\.css(\?v=[^\"']*)?", f"style.css?v={css_ver}", html)
    html = re.sub(r"app\.js(\?v=[^\"']*)?", f"app.js?v={js_ver}", html)
    index.write_text(html, encoding="utf-8")

    # --root：同时把带版本号的 index.html 写回根目录。
    # GitHub Actions 里 Pages 直接从仓库根目录提供服务，需要这一份。
    if write_root:
        (ROOT / "index.html").write_text(html, encoding="utf-8")

    print(f"[同步] 已更新「发布」目录（{len(SRC_FILES)} 个文件，css={css_ver} js={js_ver}）")


def deploy_if_configured() -> None:
    token_file = ROOT / ".gh_token"
    if not token_file.exists() or not token_file.read_text(encoding="utf-8").strip():
        print("[部署] 未配置 .gh_token，跳过自动部署")
        return
    print("[部署] 检测到 .gh_token，开始部署到 GitHub Pages…")
    env = dict(os.environ)
    env["GH_TOKEN"] = token_file.read_text(encoding="utf-8").strip()
    env["PYTHONIOENCODING"] = "utf-8"
    res = subprocess.run(
        [sys.executable, str(ROOT / "deploy_github_pages.py")],
        cwd=str(ROOT), env=env, text=True, encoding="utf-8", errors="replace",
        capture_output=True,
    )
    sys.stdout.write(res.stdout or "")
    if res.returncode != 0:
        sys.stderr.write(res.stderr or "")
        print(f"[部署] 失败（退出码 {res.returncode}）")


def main() -> int:
    write_root = "--root" in sys.argv
    no_deploy = "--no-deploy" in sys.argv
    sync(write_root=write_root)
    if no_deploy:
        print("[部署] --no-deploy：跳过部署（GitHub Actions 里由提交触发 Pages 重建）")
    else:
        deploy_if_configured()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

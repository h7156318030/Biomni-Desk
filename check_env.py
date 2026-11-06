"""Biomni-Desk 配置自检：不发起任何 API 请求，只看配置是否被正确装载。

用法：
    .venv\\Scripts\\python.exe check_env.py
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 必须先加载 .env，再导入 biomni —— a1.py 内部是"先导入配置、后加载 .env"，顺序颠倒
ENV_PATH = Path(__file__).resolve().parent / ".env"
if not ENV_PATH.exists():
    sys.exit(f"[X] 找不到 {ENV_PATH}")
load_dotenv(ENV_PATH, override=True)

from biomni.config import default_config  # noqa: E402


def mask(v: str | None) -> str:
    if not v:
        return "(空)"
    if len(v) <= 12:
        return "*" * len(v)
    return f"{v[:10]}{'*' * 8}{v[-4:]}"


print("=" * 56)
print("Biomni-Desk 配置自检")
print("=" * 56)
print(f".env 路径        : {ENV_PATH}")
print(f"source           : {default_config.source}")
print(f"base_url         : {default_config.base_url}")
print(f"api_key          : {mask(default_config.api_key)}")
print(f"llm              : {default_config.llm}")
print(f"path (工作目录)  : {default_config.path}")
print(f"timeout_seconds  : {default_config.timeout_seconds}")
print(f"use_tool_retriever: {default_config.use_tool_retriever}")
print(f"commercial_mode  : {default_config.commercial_mode}")
print("=" * 56)

problems = []
if default_config.source != "Custom":
    problems.append("source 不是 Custom，请求会走错端点")
if not default_config.base_url:
    problems.append("base_url 为空")
if not default_config.api_key or default_config.api_key == "EMPTY":
    problems.append("api_key 未装载")
if "/" not in (default_config.llm or ""):
    problems.append("llm 缺少厂商前缀（OpenRouter 需要 provider/model 形式）")

if problems:
    print("\n[X] 发现问题：")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)

print("\n[OK] 配置装载正常，可以进行 API 测试")

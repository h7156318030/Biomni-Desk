"""运行 Biomni-Desk agent。

用法：
    .venv\\Scripts\\python.exe ask.py "Query UniProt for TP53 protein information"

不带参数时只初始化并打印工具数量，不消耗 API 额度。
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH, override=True)

from biomni.agent import A1  # noqa: E402


def main() -> None:
    query = " ".join(sys.argv[1:]).strip()

    agent = A1()

    n_tools = sum(len(v) for v in agent.module2api.values())
    print(f"\n已加载模块 {len(agent.module2api)} 个，工具 {n_tools} 个")

    if not query:
        print("未提供问题，仅完成初始化。示例：")
        print('  .venv\\Scripts\\python.exe ask.py "Query UniProt for TP53"')
        return

    print(f"\n提问: {query}\n")
    result = agent.go(query)
    print("\n" + "=" * 56)
    print("最终结果:")
    print(result)


if __name__ == "__main__":
    main()

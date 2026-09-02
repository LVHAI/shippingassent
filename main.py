from __future__ import annotations

from agent.graph import run_once


def main() -> None:
    print("运费助手已启动，输入 exit 退出。")
    state = None
    while True:
        try:
            user_input = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user_input:
            continue
        if user_input.casefold() in {"exit", "quit", "q"}:
            print("再见！")
            break

        state = run_once(user_input, state)
        print(f"助手：{state.get('response', '')}")
        print()


if __name__ == "__main__":
    main()

"""Sign in to ChatGPT for Biomni-Lite: `python -m biomni_ui.chatgpt_login` (add `--check` to test, `--logout` to forget)."""

from __future__ import annotations

import sys

from biomni_ui import chatgpt_api as api


def main(argv: list[str]) -> int:
    if "--logout" in argv:
        api.logout()
        print("Logged out of ChatGPT.")
        return 0
    if "--check" in argv:
        if not api.is_logged_in():
            print("Not logged in.")
            return 1
        from langchain_core.messages import HumanMessage

        reply = api.ChatCodexAPI(reasoning_effort="medium").invoke([HumanMessage(content="Reply with exactly: pong")])
        print("Model reply: ", reply.content)
        return 0
    device = api.request_device_code()
    print(f"\n1. Open in your browser: {device['verification_url']}")
    print(f"2. Enter the code: {device['user_code']}")
    print("Waiting for you to finish logging in in the browser… (valid for 15 minutes)", flush=True)
    api.poll_device_code(device)
    print("Login succeeded. Credentials are saved in ui_data/chatgpt_auth.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

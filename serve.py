"""
Biomni-Lite Gradio web UI entrypoint.

Launch with:
    python serve.py
    # or inside Docker:
    docker compose up biomni-lite-gradio

Agent selection
---------------
Set the BIOMNI_AGENT env var to bypass the selector:
    BIOMNI_AGENT=a1   → launch A1  (general biomedical agent)
    BIOMNI_AGENT=ad1  → launch AD1 (Alzheimer's Disease agent)

When BIOMNI_AGENT is unset a landing page is shown at port 7860 so the
user can pick their agent interactively before the full UI loads.

CLI usage (no Gradio):
    python -c "from biomni.agent import A1; A1().go('your query')"
    python -c "from biomni.agent.ad1 import AD1; AD1().go('your query')"
"""

import logging
import os
import socket
import threading
import time

# Disable Gradio analytics and set server binding before any Gradio import so
# that no external CDN calls are made at startup (required for air-gapped VMs).
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("GRADIO_SERVER_NAME", "0.0.0.0")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [biomni-serve] %(message)s",
)
logger = logging.getLogger("biomni-serve")

_GRADIO_PORT = 7860


def _wait_for_port_free(port: int, timeout: float = 15.0) -> None:
    """Block until *port* on localhost is no longer in use."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                logger.info("Port %d is free.", port)
                return
        time.sleep(0.5)
    logger.warning("Port %d still in use after %.0fs — proceeding anyway.", port, timeout)


def _check_llm_connectivity(llm_model: str) -> None:
    """Quick smoke-test: make sure the LLM API is reachable.

    Uses a minimal httpx HEAD/GET to the provider's endpoint.  If the
    connection fails because of SSL inspection or a blocked network,
    this prints an actionable error *before* the agent starts.
    """
    import ssl

    # Determine endpoint from model name
    if llm_model.startswith("claude"):
        url = "https://api.anthropic.com"
        provider = "Anthropic"
    elif llm_model.startswith(("gpt-", "gpt_")):
        url = "https://api.openai.com"
        provider = "OpenAI"
    elif llm_model.startswith("gemini"):
        url = "https://generativelanguage.googleapis.com"
        provider = "Google Gemini"
    else:
        logger.info("Skipping connectivity check for model: %s", llm_model)
        return

    logger.info("Checking connectivity to %s (%s) …", provider, url)
    try:
        import httpx

        # Build an SSL context that honours SSL_CERT_FILE / SSL_CERT_DIR
        ssl_cert = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
        verify = ssl_cert if ssl_cert else True

        with httpx.Client(verify=verify, timeout=10) as client:
            resp = client.get(url, follow_redirects=True)
            logger.info("%s reachable (HTTP %s)", provider, resp.status_code)
    except (httpx.ConnectError, ssl.SSLError) as exc:
        logger.error(
            "\n"
            "=" * 60 + "\n"
            "  ❌  Cannot reach %s API  (%s)\n"
            "  Error: %s\n\n"
            "  This usually means your VPN / firewall is blocking or\n"
            "  doing SSL inspection on outbound HTTPS traffic.\n\n"
            "  Possible fixes:\n"
            "    1. Ask IT to whitelist %s\n"
            "    2. Set SSL_CERT_FILE=/path/to/corporate-ca-bundle.crt in .env\n"
            "    3. (NOT recommended for production) Set HTTPX_SSL_VERIFY=false in .env\n"
            "=" * 60,
            provider, url, exc, url,
        )
        # Don't exit — let the user see the Gradio UI and get the error
        # when they actually submit a query.
    except Exception as exc:
        logger.warning("Connectivity check inconclusive: %s", exc)


def main() -> None:
    llm = os.getenv("BIOMNI_LLM", "claude-opus-4-5")
    path = os.getenv("BIOMNI_PATH", "./data")
    env = os.getenv("BIOMNI_AGENT", "").strip().lower()

    # ── Connectivity pre-check ──────────────────────────────────────────────
    _check_llm_connectivity(llm)

    # ── Honour HTTPX_SSL_VERIFY for corporate proxies ───────────────────────
    ssl_verify = os.environ.get("HTTPX_SSL_VERIFY", "").strip().lower()
    if ssl_verify == "false":
        # Disable SSL verification globally for httpx (last resort)
        logger.warning(
            "HTTPX_SSL_VERIFY=false → disabling SSL certificate verification. "
            "This is insecure — use SSL_CERT_FILE instead when possible."
        )
        os.environ["SSL_CERT_FILE"] = ""
        os.environ["CURL_CA_BUNDLE"] = ""
        import httpx
        # Monkey-patch httpx defaults
        httpx._config.DEFAULT_CERTS = None  # type: ignore[attr-defined]

    # ── Direct launch via env var (skips selector) ──────────────────────────
    if env == "a1":
        logger.info("Launching A1 agent directly (BIOMNI_AGENT=a1)")
        from biomni.agent import A1
        A1(llm=llm, path=path).launch_gradio_demo(server_name="0.0.0.0")
        return

    if env == "ad1":
        logger.info("Launching AD1 agent directly (BIOMNI_AGENT=ad1)")
        from biomni.agent.ad1 import AD1
        AD1(llm=llm, path=path).launch_ui(server_name="0.0.0.0")
        return

    # ── Interactive selector landing page ────────────────────────────────────
    logger.info("No BIOMNI_AGENT set — showing interactive selector")
    import gradio as gr

    chosen: dict = {"value": "a1"}
    ready = threading.Event()

    with gr.Blocks(title="Biomni-Lite — Select Agent") as selector:
        gr.Markdown(
            "# 🧬 Biomni-Lite\n"
            "**Choose an agent to launch:**"
        )
        with gr.Row():
            btn_a1 = gr.Button(
                "🔬 A1 — General Biomedical",
                variant="primary",
                scale=1,
            )
            btn_ad1 = gr.Button(
                "🧠 AD1 — Alzheimer's Disease",
                variant="secondary",
                scale=1,
            )
        status = gr.Markdown(
            "_A1: broad biomedical tasks &nbsp;·&nbsp; "
            "AD1: extends A1 with Alzheimer's Disease domain expertise_"
        )

        def _pick(val: str) -> str:
            chosen["value"] = val
            ready.set()
            return (
                f"⏳ Launching **{val.upper()}** — the page will reload "
                "automatically in a few seconds.\n\n"
                "_If it does not reload, please **refresh your browser** manually._"
            )

        # Client-side JS reloads the page after 8 s so the browser picks up
        # the new agent server once it is ready.
        _reload_js = "() => { setTimeout(() => window.location.reload(), 8000); }"

        btn_a1.click(lambda: _pick("a1"), outputs=status, js=_reload_js)
        btn_ad1.click(lambda: _pick("ad1"), outputs=status, js=_reload_js)

    logger.info("Starting selector on port %d", _GRADIO_PORT)
    selector.launch(
        server_name="0.0.0.0",
        server_port=_GRADIO_PORT,
        prevent_thread_lock=True,
        share=False,
        show_api=False,
    )

    # Block until the user clicks a button
    ready.wait()
    logger.info("User selected agent: %s — shutting down selector …", chosen["value"])
    selector.close()

    # Wait for the port to be fully released before binding the agent server.
    _wait_for_port_free(_GRADIO_PORT)
    time.sleep(1)  # extra buffer for OS socket cleanup

    # ── Launch selected agent ────────────────────────────────────────────────
    logger.info("Starting %s agent on port %d", chosen["value"].upper(), _GRADIO_PORT)
    try:
        if chosen["value"] == "ad1":
            from biomni.agent.ad1 import AD1
            AD1(llm=llm, path=path).launch_ui(server_name="0.0.0.0")
        else:
            from biomni.agent import A1
            A1(llm=llm, path=path).launch_gradio_demo(server_name="0.0.0.0")
    except Exception:
        logger.exception("Agent failed to start")
        raise


if __name__ == "__main__":
    main()

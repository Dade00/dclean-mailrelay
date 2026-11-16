"""Mail relay Railway -> Brevo HTTP API.

Railway blocks outbound SMTP (25/465/587/2525), so GlitchTip cannot talk to
Brevo over SMTP. This service listens for SMTP on the private network and
forwards each message to https://api.brevo.com/v3/smtp/email over HTTPS (443),
which is allowed.

Env:
  BREVO_API_KEY  Brevo v3 API key (SMTP & API -> API keys). Missing => 451.
  FROM_EMAIL     verified Brevo sender, default glitchtip@davidezambecco.it
  FROM_NAME      display name, default GlitchTip
  RELAY_PORT     SMTP listen port, default 2525
"""

import logging
import os
import time
from email import message_from_bytes, policy

import requests
from aiosmtpd.controller import Controller

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mailrelay")

BREVO_API = "https://api.brevo.com/v3/smtp/email"
KEY = os.environ.get("BREVO_API_KEY", "").strip()
FROM = os.environ.get("FROM_EMAIL", "glitchtip@davidezambecco.it").strip()
FROM_NAME = os.environ.get("FROM_NAME", "GlitchTip").strip()
PORT = int(os.environ.get("RELAY_PORT", "2525"))


def brevo_send(raw: bytes, rcpts: list[str]) -> tuple[int, str]:
    msg = message_from_bytes(raw, policy=policy.default)
    subject = str(msg.get("Subject") or "(no subject)")

    text = html = None
    parts = list(msg.walk()) if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_maintype() == "multipart" or part.get_filename():
            continue
        ctype = part.get_content_type()
        try:
            body = part.get_content()
        except Exception:
            continue
        if ctype == "text/plain" and text is None:
            text = body
        elif ctype == "text/html" and html is None:
            html = body

    payload = {
        "sender": {"email": FROM, "name": FROM_NAME},
        "to": [{"email": a} for a in rcpts],
        "subject": subject,
    }
    if html:
        payload["htmlContent"] = html
    if text:
        payload["textContent"] = text
    if not html and not text:
        payload["textContent"] = "(empty message)"

    r = requests.post(
        BREVO_API,
        json=payload,
        headers={
            "api-key": KEY,
            "accept": "application/json",
            "content-type": "application/json",
        },
        timeout=25,
    )
    return r.status_code, (r.text or "")[:300]


class Handler:
    async def handle_DATA(self, server, session, envelope):
        rcpts = list(envelope.rcpt_tos)
        if not KEY:
            log.error("BREVO_API_KEY not set, refusing message to %s", rcpts)
            return "451 4.3.0 relay not configured (BREVO_API_KEY missing)"
        try:
            code, body = brevo_send(envelope.original_content, rcpts)
        except Exception as exc:  # noqa: BLE001 - report upstream failure to the SMTP client
            log.error("upstream exception: %s", exc)
            return "451 4.3.0 relay exception"
        log.info("brevo_status=%s rcpts=%s body=%s", code, rcpts, body)
        if 200 <= code < 300:
            return "250 2.0.0 forwarded to brevo"
        return f"451 4.3.0 upstream {code}"


if __name__ == "__main__":
    controller = Controller(Handler(), hostname="0.0.0.0", port=PORT)
    controller.start()
    log.info(
        "mailrelay listening on 0.0.0.0:%s from=%s api_key=%s",
        PORT,
        FROM,
        "set" if KEY else "MISSING",
    )
    while True:
        time.sleep(3600)

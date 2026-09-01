"""Twilio SMS integration for operational alert delivery."""

import os
from pathlib import Path
from typing import Iterable, Sequence


def _load_env_file() -> None:
    for env_path in [
        Path(".env"),
        Path("backend/.env"),
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
    ]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if not line.strip() or line.strip().startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()


def twilio_config() -> dict[str, str]:
    return {
        "account_sid": os.getenv("TWILIO_ACCOUNT_SID", "").strip(),
        "auth_token": os.getenv("TWILIO_AUTH_TOKEN", "").strip(),
        "from_number": os.getenv("TWILIO_FROM_NUMBER", "").strip(),
    }


def configured_recipients() -> list[str]:
    raw = os.getenv("SMS_RECIPIENTS", "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def send_sms(to_number: str, body: str, from_number: str | None = None) -> dict:
    """Send a real SMS when Twilio credentials are configured; otherwise return a no-op result."""
    config = twilio_config()
    if not config["account_sid"] or not config["auth_token"] or not config["from_number"]:
        return {"status": "skipped", "reason": "TWILIO_* not configured"}
    if not to_number:
        return {"status": "skipped", "reason": "recipient missing"}

    try:
        from twilio.rest import Client

        client = Client(config["account_sid"], config["auth_token"])
        message = client.messages.create(
            body=body,
            from_=from_number or config["from_number"],
            to=to_number,
        )
        return {"status": "sent", "sid": message.sid, "to": to_number, "from": from_number or config["from_number"]}
    except Exception as exc:  # pragma: no cover - network/config path only
        return {"status": "error", "reason": str(exc)}


def broadcast_alert_sms(body: str, recipients: Sequence[str] | None = None) -> list[dict]:
    numbers = list(recipients) if recipients else configured_recipients()
    if not numbers:
        return [{"status": "skipped", "reason": "no SMS recipients configured"}]
    return [send_sms(number, body) for number in numbers]

import logging
import sys
import traceback
from typing import Optional

import requests

from app.core.config import settings


# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class GoogleChatHandler(logging.Handler):
    """Logging handler that posts error-level logs to a Google Chat incoming webhook.

    It posts a simple JSON payload: {"text": "..."}. The webhook URL is taken from
    `settings.GOOGLE_CHAT_WEBHOOK`. If no webhook is configured, this handler is a no-op.
    """

    def __init__(self, webhook_url: Optional[str] = None, level: int = logging.ERROR):
        super().__init__(level=level)
        self.webhook_url = webhook_url or settings.GOOGLE_CHAT_WEBHOOK

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if not self.webhook_url:
                return

            # Format the log entry
            msg = self.format(record)

            # Include exception traceback if present
            if record.exc_info:
                tb = "\n" + "".join(traceback.format_exception(*record.exc_info))
                msg = f"{msg}\n{tb}"

            payload = {"text": msg}

            # Send to Google Chat incoming webhook (simple text card)
            headers = {"Content-Type": "application/json; charset=UTF-8"}
            try:
                requests.post(self.webhook_url, json=payload, headers=headers, timeout=5)
            except Exception:
                # Don't raise in logging handler; fallback to writing to stderr
                sys.stderr.write("Failed to send Google Chat alert for log record\n")
        except Exception:
            # Ensure logging never raises
            try:
                sys.stderr.write("Error in GoogleChatHandler.emit\n")
            except Exception:
                pass


# Create module-level logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Ensure the module logger has at least one handler so logs appear under uvicorn/reload
if not logger.handlers:
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(sh)

# Attach GoogleChatHandler to the root logger if webhook is configured so all modules' errors are forwarded
google_webhook = getattr(settings, "GOOGLE_CHAT_WEBHOOK", "")
if google_webhook:
    gh = GoogleChatHandler(webhook_url=google_webhook)
    gh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(gh)


# Explicitly export logger for imports
__all__ = ["logger", "GoogleChatHandler"]
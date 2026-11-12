"""Suppress SDK payload diagnostics only within the current generation context."""

import logging
from contextlib import contextmanager
from contextvars import ContextVar

_private_call = ContextVar("cyberforge_private_sdk_call", default=False)


class _SDKPrivacyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _private_call.get()


# These are the payload/exception loggers in the verified SDK versions.
# Context-local filtering preserves other threads' unrelated application logs.
for _name in ("groq", "groq._base_client", "google.genai", "google_genai._api_client"):
    logging.getLogger(_name).addFilter(_SDKPrivacyFilter())


@contextmanager
def private_sdk_logs():
    token = _private_call.set(True)
    try:
        yield
    finally:
        _private_call.reset(token)

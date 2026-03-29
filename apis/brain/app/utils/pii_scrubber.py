import logging

from app.services.pii import _PATTERNS


def _scrub(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class PIIScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _scrub(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _scrub(v) if isinstance(v, str) else v for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    _scrub(arg) if isinstance(arg, str) else arg for arg in record.args
                )
        return True


def setup_pii_scrubbing() -> None:
    pii_filter = PIIScrubFilter()
    for handler in logging.root.handlers:
        handler.addFilter(pii_filter)
    logging.root.addFilter(pii_filter)

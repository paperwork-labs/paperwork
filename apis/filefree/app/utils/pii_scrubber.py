import logging
import re

SSN_PATTERN = re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")
SSN_REPLACEMENT = "***-**-****"
EIN_PATTERN = re.compile(r"\b\d{2}-\d{7}\b")
EIN_REPLACEMENT = "**-*******"


def _scrub(text: str) -> str:
    return EIN_PATTERN.sub(EIN_REPLACEMENT, SSN_PATTERN.sub(SSN_REPLACEMENT, text))


class PIIScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _scrub(record.msg)
        if record.args:
            new_args: list[object] = []
            for arg in record.args if isinstance(record.args, tuple) else (record.args,):
                if isinstance(arg, str):
                    new_args.append(_scrub(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        return True


def setup_pii_scrubbing() -> None:
    pii_filter = PIIScrubFilter()
    for handler in logging.root.handlers:
        handler.addFilter(pii_filter)
    logging.root.addFilter(pii_filter)

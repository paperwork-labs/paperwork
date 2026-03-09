import logging
import re

SSN_PATTERN = re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")
SSN_REPLACEMENT = "***-**-****"


class PIIScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = SSN_PATTERN.sub(SSN_REPLACEMENT, record.msg)
        if record.args:
            new_args = []
            for arg in record.args if isinstance(record.args, tuple) else (record.args,):
                if isinstance(arg, str):
                    new_args.append(SSN_PATTERN.sub(SSN_REPLACEMENT, arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
        return True


def setup_pii_scrubbing() -> None:
    pii_filter = PIIScrubFilter()
    for handler in logging.root.handlers:
        handler.addFilter(pii_filter)
    logging.root.addFilter(pii_filter)

"""Public exports for ``pii-scrubber``."""

from pii_scrubber.scrubber import ScrubMode as ScrubMode
from pii_scrubber.scrubber import ScrubResult as ScrubResult
from pii_scrubber.scrubber import scrub as scrub
from pii_scrubber.structured import scrub_dict as scrub_dict

__all__ = [
    "ScrubMode",
    "ScrubResult",
    "scrub",
    "scrub_dict",
]

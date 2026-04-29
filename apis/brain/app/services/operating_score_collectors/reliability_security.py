"""Reliability + security pillar — uptime / ASVS tooling deferred.

medallion: ops
"""

from __future__ import annotations


def collect() -> tuple[float, bool, str]:
    return (60.0, False, "bootstrap estimate — uptime API collector deferred")

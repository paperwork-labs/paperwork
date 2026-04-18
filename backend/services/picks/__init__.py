"""Picks pipeline (email parser + candidate generator + validator).

Sub-packages:

    email_parser   — Polymorphic LLM-based email parser (this PR).
    generators     — Candidate generators (added in PR #328).

This module is intentionally minimal so it merges cleanly with PR #327
(picks data models) and PR #328 (candidate generator framework).
"""

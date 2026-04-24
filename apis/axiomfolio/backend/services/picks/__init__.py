"""Picks pipeline services.

This package owns everything that turns raw signal sources (validator
emails, X posts, system snapshots) into rows in the picks tables defined
in ``backend.models.picks``.

Module layout::

    candidate_generator.py   Base class + registry for system-generated picks.
    generators/              One module per concrete generator (e.g.
                             stage2a_rs_strong.py).
    email_parser/            Polymorphic LLM-based email parser that
                             normalizes inbox messages into structured
                             pick payloads.

medallion: gold
"""

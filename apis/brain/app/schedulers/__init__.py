"""In-process schedulers owned by Brain.

See ``pr_sweep.py`` for the PR-sweep job that replaced the
``auto-merge-sweep.yaml`` GitHub Actions workflow in Track B, Week 1.

Only one scheduler instance per process — ``start()``/``shutdown()`` are
called from ``app.main``'s lifespan context. Do not start schedulers from
routers or services; that would break clean shutdown.
"""

from .pr_sweep import start_scheduler, shutdown_scheduler, get_scheduler

__all__ = ["start_scheduler", "shutdown_scheduler", "get_scheduler"]

"""
Pipeline Runner
===============

Orchestrates market data pipeline stages with progress tracking.
Used by the nightly pipeline and auto-remediation tasks.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class PipelineStage(Enum):
    """Standard pipeline stages for market data."""
    CONSTITUENTS = "constituents"
    TRACKED = "tracked"
    DAILY_BARS = "daily_bars"
    INDICATORS = "indicators"
    HISTORY = "history"
    REGIME = "regime"
    COVERAGE = "coverage"


@dataclass
class StageResult:
    """Result of a single pipeline stage."""
    stage: str
    success: bool
    duration_s: float
    records_processed: int = 0
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""
    success: bool
    total_duration_s: float
    stages: List[StageResult] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to JSON-serializable dict."""
        return {
            "success": self.success,
            "total_duration_s": round(self.total_duration_s, 2),
            "stages": [
                {
                    "stage": s.stage,
                    "success": s.success,
                    "duration_s": round(s.duration_s, 2),
                    "records_processed": s.records_processed,
                    "error": s.error,
                }
                for s in self.stages
            ],
            "error": self.error,
        }


class PipelineRunner:
    """Orchestrates multi-stage data pipelines with error handling.

    Usage:
        runner = PipelineRunner()
        runner.add_stage("constituents", refresh_constituents, timeout=60)
        runner.add_stage("daily_bars", backfill_daily, timeout=300)
        result = runner.run()
    """

    def __init__(self, name: str = "market_data"):
        self.name = name
        self._stages: List[Dict] = []
        self._progress_callback: Optional[Callable[[str, str], None]] = None

    def add_stage(
        self,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: Optional[Dict] = None,
        timeout: int = 300,
        continue_on_error: bool = False,
    ) -> "PipelineRunner":
        """Add a stage to the pipeline.

        Args:
            name: Stage name for logging/tracking
            func: Function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            timeout: Max execution time in seconds
            continue_on_error: Whether to continue if this stage fails

        Returns:
            self for chaining
        """
        self._stages.append({
            "name": name,
            "func": func,
            "args": args,
            "kwargs": kwargs or {},
            "timeout": timeout,
            "continue_on_error": continue_on_error,
        })
        return self

    def set_progress_callback(
        self, callback: Callable[[str, str], None]
    ) -> "PipelineRunner":
        """Set a callback for progress updates.

        Args:
            callback: Function(stage_name, status) called at each stage

        Returns:
            self for chaining
        """
        self._progress_callback = callback
        return self

    def run(self) -> PipelineResult:
        """Execute all stages in order.

        Returns:
            PipelineResult with success status and stage details
        """
        import time

        start_time = time.time()
        results = []
        overall_success = True
        overall_error = None

        for stage in self._stages:
            stage_name = stage["name"]
            stage_start = time.time()

            # Notify progress
            if self._progress_callback:
                self._progress_callback(stage_name, "running")

            logger.info("Pipeline [%s]: Starting stage '%s'", self.name, stage_name)

            timeout_s = stage["timeout"]
            try:
                # NOTE: shutdown(wait=False, cancel_futures=True) prevents the
                # executor from blocking, but the underlying OS thread may keep
                # running after a timeout.  Python threads cannot be killed.
                # Hard cancellation relies on Celery's soft_time_limit at the
                # task level, or cooperative checks inside each stage function.
                executor = ThreadPoolExecutor(max_workers=1)
                try:
                    future = executor.submit(
                        stage["func"], *stage["args"], **stage["kwargs"]
                    )
                    result = future.result(timeout=timeout_s)
                finally:
                    executor.shutdown(wait=False, cancel_futures=True)

                # Extract record count if returned
                records = 0
                details = {}
                if isinstance(result, dict):
                    records = result.get("count", result.get("processed", 0))
                    details = result

                stage_result = StageResult(
                    stage=stage_name,
                    success=True,
                    duration_s=time.time() - stage_start,
                    records_processed=records,
                    details=details,
                )
                results.append(stage_result)

                if self._progress_callback:
                    self._progress_callback(stage_name, "completed")

                logger.info(
                    "Pipeline [%s]: Stage '%s' completed in %.1fs",
                    self.name, stage_name, stage_result.duration_s
                )

            except FuturesTimeoutError:
                err_msg = (
                    f"Stage '{stage_name}' exceeded timeout of {timeout_s}s"
                )
                logger.error(
                    "Pipeline [%s]: %s",
                    self.name,
                    err_msg,
                )
                stage_result = StageResult(
                    stage=stage_name,
                    success=False,
                    duration_s=time.time() - stage_start,
                    error=err_msg,
                )
                results.append(stage_result)

                if self._progress_callback:
                    self._progress_callback(stage_name, "failed")

                if not stage["continue_on_error"]:
                    overall_success = False
                    overall_error = err_msg
                    break

            except Exception as e:
                logger.exception("Pipeline [%s]: Stage '%s' failed", self.name, stage_name)

                stage_result = StageResult(
                    stage=stage_name,
                    success=False,
                    duration_s=time.time() - stage_start,
                    error=str(e),
                )
                results.append(stage_result)

                if self._progress_callback:
                    self._progress_callback(stage_name, "failed")

                if not stage["continue_on_error"]:
                    overall_success = False
                    overall_error = f"Stage '{stage_name}' failed: {e}"
                    break

        return PipelineResult(
            success=overall_success,
            total_duration_s=time.time() - start_time,
            stages=results,
            error=overall_error,
        )


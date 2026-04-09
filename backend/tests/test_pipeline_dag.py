"""Tests for pipeline DAG resolution, orchestration, resume, and retry."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import fakeredis
import pytest

os.environ.setdefault("AXIOMFOLIO_TESTING", "1")

from backend.services.pipeline.dag import (
    PIPELINE_DAG,
    STEP_ERROR,
    STEP_OK,
    STEP_PENDING,
    STEP_SKIPPED,
    StepDef,
    _step_key,
    all_deps_satisfied,
    dag_edges,
    get_step_status,
    mark_step,
    resolve_execution_order,
)
from backend.services.pipeline.orchestrator import run_pipeline

pytestmark = pytest.mark.no_db


# Override the autouse fixtures that pull in the DB.
@pytest.fixture(autouse=True)
def _schema_guard():
    yield

@pytest.fixture
def db_session():
    yield None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def fake_redis():
    """Provide a fakeredis instance and patch the DAG module to use it."""
    r = fakeredis.FakeRedis(decode_responses=True)
    with patch("backend.services.pipeline.dag._redis_client", return_value=r):
        yield r


MINI_DAG = {
    "a": StepDef(deps=(), task_path="mod.fn_a", timeout_s=60, display_name="Step A"),
    "b": StepDef(deps=("a",), task_path="mod.fn_b", timeout_s=60, display_name="Step B"),
    "c": StepDef(deps=("a",), task_path="mod.fn_c", timeout_s=60, display_name="Step C"),
    "d": StepDef(deps=("b", "c"), task_path="mod.fn_d", timeout_s=60, display_name="Step D"),
}

DIAMOND_DAG = {
    "root": StepDef(deps=(), task_path="x.root", timeout_s=10, display_name="Root"),
    "left": StepDef(deps=("root",), task_path="x.left", timeout_s=10, display_name="Left"),
    "right": StepDef(deps=("root",), task_path="x.right", timeout_s=10, display_name="Right"),
    "join": StepDef(deps=("left", "right"), task_path="x.join", timeout_s=10, display_name="Join"),
}


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------

class TestTopoSort:
    def test_full_dag_valid_order(self):
        order = resolve_execution_order(PIPELINE_DAG)
        assert len(order) == len(PIPELINE_DAG)
        seen: set[str] = set()
        for step in order:
            for dep in PIPELINE_DAG[step].deps:
                assert dep in seen, f"{step} ran before its dep {dep}"
            seen.add(step)

    def test_mini_dag_order(self):
        order = resolve_execution_order(MINI_DAG)
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_subset_includes_transitive_deps(self):
        order = resolve_execution_order(PIPELINE_DAG, steps=["digest"])
        assert "constituents" in order
        assert "tracked_cache" in order
        assert "daily_bars" in order
        assert "indicators" in order
        assert "regime" in order
        assert "scan_overlay" in order
        assert "digest" in order
        assert "exit_cascade" not in order
        assert "audit" not in order

    def test_cycle_detection(self):
        cyclic = {
            "x": StepDef(deps=("y",), task_path="m.x", timeout_s=1, display_name="X"),
            "y": StepDef(deps=("x",), task_path="m.y", timeout_s=1, display_name="Y"),
        }
        with pytest.raises(ValueError, match="Cycle"):
            resolve_execution_order(cyclic)

    def test_unknown_step_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            resolve_execution_order(PIPELINE_DAG, steps=["nonexistent_step"])

    def test_single_step_no_deps(self):
        order = resolve_execution_order(PIPELINE_DAG, steps=["constituents"])
        assert order == ["constituents"]


# ---------------------------------------------------------------------------
# DAG edges
# ---------------------------------------------------------------------------

class TestDAGEdges:
    def test_edge_count(self):
        edges = dag_edges(PIPELINE_DAG)
        total_deps = sum(len(s.deps) for s in PIPELINE_DAG.values())
        assert len(edges) == total_deps

    def test_edge_format(self):
        edges = dag_edges(MINI_DAG)
        assert {"from": "a", "to": "b"} in edges
        assert {"from": "a", "to": "c"} in edges
        assert {"from": "b", "to": "d"} in edges


# ---------------------------------------------------------------------------
# Redis state helpers
# ---------------------------------------------------------------------------

class TestRedisState:
    def test_mark_and_get_step(self, fake_redis):
        mark_step("run-1", "indicators", STEP_OK, duration_s=12.5)
        assert get_step_status("run-1", "indicators") == STEP_OK

    def test_missing_step_returns_none(self, fake_redis):
        assert get_step_status("run-1", "nonexistent") is None

    def test_all_deps_satisfied_true(self, fake_redis):
        mark_step("run-1", "a", STEP_OK)
        assert all_deps_satisfied("run-1", "b", MINI_DAG) is True

    def test_all_deps_satisfied_false(self, fake_redis):
        mark_step("run-1", "a", STEP_ERROR)
        assert all_deps_satisfied("run-1", "b", MINI_DAG) is False

    def test_all_deps_missing_returns_false(self, fake_redis):
        assert all_deps_satisfied("run-1", "b", MINI_DAG) is False

    def test_step_with_no_deps_always_satisfied(self, fake_redis):
        assert all_deps_satisfied("run-1", "a", MINI_DAG) is True


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _make_step_fn(return_value=None):
    """Create a mock step function returning a dict."""
    result = return_value or {"status": "ok"}
    return MagicMock(return_value=result)


class TestOrchestrator:
    @patch("backend.services.pipeline.orchestrator._resolve_callable")
    @patch("backend.services.pipeline.orchestrator._summarize", return_value="ok")
    def test_full_run_all_ok(self, _mock_summary, mock_resolve, fake_redis):
        mock_resolve.return_value = _make_step_fn()
        result = run_pipeline("test-run-1", dag=MINI_DAG)
        assert result["status"] == "ok"
        assert result["steps_ok"] == 4
        assert result["steps_error"] == 0
        assert result["steps_skipped"] == 0

    @patch("backend.services.pipeline.orchestrator._resolve_callable")
    @patch("backend.services.pipeline.orchestrator._summarize", return_value="ok")
    def test_resume_skips_completed(self, _mock_summary, mock_resolve, fake_redis):
        mark_step("resume-run", "a", STEP_OK)
        mark_step("resume-run", "b", STEP_OK)
        call_count = {"count": 0}
        def counting_fn(**kw):
            call_count["count"] += 1
            return {"status": "ok"}
        mock_resolve.return_value = counting_fn
        result = run_pipeline("resume-run", dag=MINI_DAG)
        assert result["status"] == "ok"
        assert call_count["count"] == 2  # only c and d executed

    @patch("backend.services.pipeline.orchestrator._resolve_callable")
    @patch("backend.services.pipeline.orchestrator._summarize", return_value="ok")
    def test_dep_failure_cascades_skip(self, _mock_summary, mock_resolve, fake_redis):
        call_order = []
        def step_fn(**kw):
            return {"status": "ok"}
        def failing_fn(**kw):
            raise RuntimeError("boom")

        def resolver(path):
            if path == "mod.fn_a":
                return failing_fn
            call_order.append(path)
            return step_fn

        mock_resolve.side_effect = resolver
        result = run_pipeline("fail-run", dag=MINI_DAG)
        assert result["status"] == "error" or result["status"] == "partial"
        assert result["steps_error"] >= 1
        assert result["steps_skipped"] >= 1
        assert get_step_status("fail-run", "a") == STEP_ERROR
        assert get_step_status("fail-run", "b") == STEP_SKIPPED
        assert get_step_status("fail-run", "c") == STEP_SKIPPED
        assert get_step_status("fail-run", "d") == STEP_SKIPPED

    @patch("backend.services.pipeline.orchestrator._resolve_callable")
    @patch("backend.services.pipeline.orchestrator._summarize", return_value="ok")
    def test_independent_branches(self, _mock_summary, mock_resolve, fake_redis):
        """In diamond DAG: if 'left' fails, 'right' still runs, 'join' is skipped."""
        def resolver(path):
            if path == "x.left":
                def fail(**kw):
                    raise RuntimeError("left failed")
                return fail
            return _make_step_fn()
        mock_resolve.side_effect = resolver

        result = run_pipeline("branch-run", dag=DIAMOND_DAG)
        assert get_step_status("branch-run", "root") == STEP_OK
        assert get_step_status("branch-run", "left") == STEP_ERROR
        assert get_step_status("branch-run", "right") == STEP_OK
        assert get_step_status("branch-run", "join") == STEP_SKIPPED

    @patch("backend.services.pipeline.orchestrator._resolve_callable")
    @patch("backend.services.pipeline.orchestrator._summarize", return_value="ok")
    def test_retry_single_step(self, _mock_summary, mock_resolve, fake_redis):
        """Retry a single step when deps are already ok."""
        mark_step("retry-run", "a", STEP_OK)
        mark_step("retry-run", "b", STEP_ERROR, error="original failure")

        mock_resolve.return_value = _make_step_fn()
        result = run_pipeline("retry-run", steps=["b"], dag=MINI_DAG)
        assert get_step_status("retry-run", "b") == STEP_OK
        assert result["steps_ok"] >= 1

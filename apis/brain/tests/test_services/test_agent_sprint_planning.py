"""Unit tests for sprint planner + task idempotency helpers."""

from app.schemas.agent_tasks import AgentTaskSpec
from app.services.agent_sprint_store import in_flight_task_ids
from app.services.sprint_planner import (
    add_path_collision_dependencies,
    parallelizability_score,
    select_sprint_bucket,
)


def test_path_collision_adds_dependency() -> None:
    a = AgentTaskSpec(
        task_id="aaa",
        title="a",
        scope="s",
        estimated_minutes=15,
        agent_type="shell",
        model_hint="composer-2-fast",
        depends_on=[],
        touches_paths=["apps/foo"],
        source={"kind": "tracker", "ref": "x"},
    )
    b = AgentTaskSpec(
        task_id="bbb",
        title="b",
        scope="s",
        estimated_minutes=15,
        agent_type="shell",
        model_hint="composer-2-fast",
        depends_on=[],
        touches_paths=["apps/foo/bar.ts"],
        source={"kind": "tracker", "ref": "y"},
    )
    add_path_collision_dependencies([a, b])
    assert a.task_id < b.task_id
    assert a.task_id in b.depends_on


def test_select_sprint_bucket_respects_cap() -> None:
    tasks = [
        AgentTaskSpec(
            task_id=f"t{i}",
            title=f"task {i}",
            scope="do work",
            estimated_minutes=60,
            agent_type="generalPurpose",
            model_hint="gpt-5.5-medium",
            depends_on=[],
            touches_paths=[f"path{i}"],
            source={"kind": "tracker", "ref": str(i)},
        )
        for i in range(10)
    ]
    picked = select_sprint_bucket(tasks, max_tasks=3, day_cap_minutes=120)
    assert len(picked) <= 3
    assert sum(t.estimated_minutes for t in picked) <= 120


def test_parallelizability_score_range() -> None:
    t = AgentTaskSpec(
        task_id="only",
        title="only",
        scope="s",
        estimated_minutes=5,
        agent_type="shell",
        model_hint="composer-2-fast",
        depends_on=[],
        touches_paths=["a"],
        source={"kind": "tracker", "ref": "r"},
    )
    assert parallelizability_score([t]) == 1.0


def test_in_flight_task_ids_empty_without_store(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    # Point brain data dir away from real store by patching module path — simplest: no file
    from app.services import agent_sprint_store as mod

    monkeypatch.setattr(mod, "_store_path", lambda: str(tmp_path / "none.json"))
    assert in_flight_task_ids() == set()

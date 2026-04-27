"""Shared sprint planning helpers for cheap-agent 1-day buckets.

Extends the surface area anticipated by PR #240 (`sprint_planner`): keep
collision detection, budgeting, and bucket selection here so #240 can add
LLM-backed planning without duplicating this module.

v1 is fully heuristic — no LLM calls.

medallion: ops
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.agent_tasks import AgentTaskSpec

logger = logging.getLogger(__name__)

# Cheap-agent capacity for one "day" sprint (configurable via env in scheduler).
DEFAULT_DAY_CAP_MINUTES = 8 * 60
ALLOWED_ESTIMATES = (5, 15, 30, 60, 120)


def normalize_estimate(minutes: int) -> int:
    """Snap to allowed discrete estimates."""
    if minutes in ALLOWED_ESTIMATES:
        return minutes
    for step in ALLOWED_ESTIMATES:
        if minutes <= step:
            return step
    return ALLOWED_ESTIMATES[-1]


def stable_task_hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def paths_collide(paths_a: list[str], paths_b: list[str]) -> bool:
    """True if any path prefix overlaps (same file or shared directory prefix)."""
    norm = [p.replace("\\", "/").strip().strip("/") for p in paths_a if p.strip()]
    other = [p.replace("\\", "/").strip().strip("/") for p in paths_b if p.strip()]
    if not norm or not other:
        return False
    for a in norm:
        for b in other:
            if a == b:
                return True
            if a.startswith(b + "/") or b.startswith(a + "/"):
                return True
    return False


def add_path_collision_dependencies(tasks: list[AgentTaskSpec]) -> None:
    """Mutates ``depends_on`` so overlapping ``touches_paths`` run sequentially.

    Deterministic tie-break: lexicographic ``task_id`` — lower id runs first
    (higher id lists the lower id in ``depends_on``).
    """
    n = len(tasks)
    for i in range(n):
        for j in range(i + 1, n):
            ti, tj = tasks[i], tasks[j]
            if not paths_collide(ti.touches_paths, tj.touches_paths):
                continue
            first, second = (ti, tj) if ti.task_id < tj.task_id else (tj, ti)
            if first.task_id not in second.depends_on:
                second.depends_on.append(first.task_id)
    for t in tasks:
        t.depends_on = sorted(set(t.depends_on))


def parallelizability_score(tasks: list[AgentTaskSpec]) -> float:
    """Heuristic in ``[0, 1]`` — higher means fewer forced serial edges."""
    n = len(tasks)
    if n <= 1:
        return 1.0
    overlap_pairs = 0
    total_pairs = n * (n - 1) // 2
    for i in range(n):
        for j in range(i + 1, n):
            if paths_collide(tasks[i].touches_paths, tasks[j].touches_paths):
                overlap_pairs += 1
    dep_weight = sum(len(t.depends_on) for t in tasks) / max(1, n * (n - 1))
    overlap_frac = overlap_pairs / max(1, total_pairs)
    score = 1.0 - 0.55 * overlap_frac - 0.35 * min(1.0, dep_weight)
    return round(max(0.0, min(1.0, score)), 2)


def _topo_order(task_ids: list[str], deps: dict[str, set[str]]) -> list[str] | None:
    """Return topological order, or None if cycle.

    ``deps[t]`` are prerequisite task ids for ``t``.
    """
    ids_set = set(task_ids)
    indeg: dict[str, int] = {
        t: sum(1 for d in deps.get(t, ()) if d in ids_set) for t in task_ids
    }
    dependents: dict[str, list[str]] = defaultdict(list)
    for t in task_ids:
        for d in deps.get(t, ()):
            if d in ids_set:
                dependents[d].append(t)

    q = deque([t for t, v in indeg.items() if v == 0])
    out: list[str] = []
    while q:
        u = q.popleft()
        out.append(u)
        for v in dependents.get(u, ()):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    if len(out) != len(task_ids):
        return None
    return out


def select_sprint_bucket(
    tasks: list[AgentTaskSpec],
    *,
    max_tasks: int,
    day_cap_minutes: int,
) -> list[AgentTaskSpec]:
    """Pick a parallel-aware subset that fits one cheap-agent day.

    - Respects ``depends_on`` via topological ordering.
    - Prefers tasks whose ``touches_paths`` are disjoint from already picked paths.
    - Stops at ``max_tasks`` or ``day_cap_minutes`` total estimate.
    """
    if not tasks:
        return []

    by_id = {t.task_id: t for t in tasks}
    deps = {t.task_id: set(t.depends_on) for t in tasks}
    order = _topo_order(list(by_id.keys()), deps)
    if order is None:
        logger.warning("sprint_planner: cycle in depends_on — falling back to task_id sort")
        order = sorted(by_id.keys())

    picked: list[AgentTaskSpec] = []
    picked_ids: set[str] = set()
    used_paths: list[str] = []
    used_minutes = 0

    def can_pick(t: AgentTaskSpec) -> bool:
        if t.task_id in picked_ids:
            return False
        for d in t.depends_on:
            if d not in picked_ids:
                return False
        if len(picked) >= max_tasks:
            return False
        return not used_minutes + t.estimated_minutes > day_cap_minutes

    # Multi-pass: try tasks in topo order; prefer low path overlap with picked set
    remaining = [by_id[i] for i in order]

    def overlap_count(t: AgentTaskSpec) -> int:
        c = 0
        for p in used_paths:
            if paths_collide([p], t.touches_paths):
                c += 1
        return c

    safety = 0
    while remaining and len(picked) < max_tasks and safety < len(tasks) * 3:
        safety += 1
        candidates = [t for t in remaining if can_pick(t)]
        if not candidates:
            # unblock: pick next task whose deps are satisfied by full task set
            # (deps may point outside bucket — treat unsatisfied as skip)
            break
        candidates.sort(key=lambda x: (overlap_count(x), -x.estimated_minutes, x.task_id))
        choice = candidates[0]
        picked.append(choice)
        picked_ids.add(choice.task_id)
        used_minutes += choice.estimated_minutes
        for p in choice.touches_paths:
            if p.strip():
                used_paths.append(p.strip())
        remaining = [t for t in remaining if t.task_id != choice.task_id]

    return picked

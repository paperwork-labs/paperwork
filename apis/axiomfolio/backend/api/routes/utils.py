from typing import List, Dict, Any
from backend.models.market_data import JobRun


def serialize_job_runs(rows: List[JobRun]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "task_name": r.task_name,
                "status": r.status,
                "started_at": getattr(r.started_at, "isoformat", lambda: None)(),
                "finished_at": getattr(r.finished_at, "isoformat", lambda: None)(),
                "params": r.params,
                "counters": r.counters,
                "error": r.error,
            }
        )
    return out


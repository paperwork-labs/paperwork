import argparse
import importlib
import json
from typing import Any, Callable


def _resolve_task(task_path: str) -> Callable[..., Any]:
    if "." not in task_path:
        raise ValueError(
            "Task path must be a dotted path, e.g. "
            "backend.tasks.market.coverage.health_check"
        )
    module_name, attr = task_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    task = getattr(module, attr, None)
    if task is None:
        raise AttributeError(f"Task {attr} not found in module {module_name}")
    return task


def main() -> None:
    parser = argparse.ArgumentParser(description="Enqueue a Celery task by dotted path.")
    parser.add_argument("task_path", help="Dotted path to the task function.")
    parser.add_argument("--args", default="[]", help="JSON array of positional args.")
    parser.add_argument("--kwargs", default="{}", help="JSON object of keyword args.")
    args = parser.parse_args()

    task = _resolve_task(args.task_path)
    task_args = json.loads(args.args)
    task_kwargs = json.loads(args.kwargs)

    result = task.delay(*task_args, **task_kwargs)
    print(result.id)


if __name__ == "__main__":
    main()

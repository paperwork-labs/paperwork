from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

APP_PARENTS = ("apis", "apps", "packages", "tools")
REGISTRY_RELATIVE_PATH = Path("apis") / "brain" / "data" / "app_registry.json"
REGISTRY_SCHEMA = "app_registry/v1"
REGISTRY_DESCRIPTION = (
    "All monorepo apps + their conformance status. Brain reads this for systemwide ops decisions."
)

_IGNORED_SIZE_DIRS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".turbo",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
}
_TEST_PATTERNS = ("test_*.py", "*_test.py", "*.test.ts", "*.test.tsx", "*.spec.ts", "*.spec.tsx")
_PY_DEPS = {
    "postgres": ("sqlalchemy", "asyncpg", "psycopg"),
    "redis": ("redis", "upstash-redis"),
    "openai": ("openai",),
    "anthropic": ("anthropic",),
}
_NODE_DEPS = {
    "postgres": ("@vercel/postgres", "pg", "postgres"),
    "redis": ("@upstash/redis", "redis", "ioredis"),
    "vercel": ("next",),
}


@dataclass(frozen=True)
class MarkerResult:
    marker: str
    required: bool
    present: bool
    gap: str


@dataclass(frozen=True)
class AppReport:
    name: str
    relative_path: str
    app_type: str
    framework: str
    language: str
    markers: tuple[MarkerResult, ...]

    @property
    def missing_required_markers(self) -> list[str]:
        return [m.marker for m in self.markers if m.required and not m.present]

    @property
    def conformance_score(self) -> float:
        required = [m for m in self.markers if m.required]
        if not required:
            return 1.0
        present = sum(1 for marker in required if marker.present)
        return round(present / len(required), 4)

    @property
    def is_conformant(self) -> bool:
        return not self.missing_required_markers


def iter_app_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for parent_name in APP_PARENTS:
        parent = root / parent_name
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir()):
            if child.is_dir() and not child.name.startswith("_"):
                paths.append(child)
    return paths


def build_onboard_report(root: Path, app_path: Path) -> AppReport:
    resolved = (root / app_path).resolve() if not app_path.is_absolute() else app_path.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        msg = f"{resolved} is outside monorepo root {root}"
        raise ValueError(msg) from exc
    if not resolved.is_dir():
        msg = f"{relative} does not exist"
        raise FileNotFoundError(msg)

    app_type = detect_app_type(root, resolved)
    framework = detect_framework(resolved)
    language = detect_language(resolved)
    markers = tuple(_marker_results(root, resolved, app_type, language))
    return AppReport(
        name=resolved.name,
        relative_path=relative.as_posix(),
        app_type=app_type,
        framework=framework,
        language=language,
        markers=markers,
    )


def render_markdown_report(report: AppReport) -> str:
    lines = [
        f"# pwl onboard {report.relative_path}",
        "",
        f"- app: `{report.name}`",
        f"- type: `{report.app_type}`",
        f"- framework: `{report.framework}`",
        f"- language: `{report.language}`",
        f"- conformance_score: `{report.conformance_score:.2f}`",
        "",
        "| marker | required | present | gap |",
        "| --- | --- | --- | --- |",
    ]
    for marker in report.markers:
        gap = marker.gap.replace("|", "\\|")
        lines.append(
            f"| {marker.marker} | {_yes_no(marker.required)} | {_yes_no(marker.present)} | {gap} |"
        )
    if report.missing_required_markers:
        lines.extend(
            [
                "",
                "## Gaps",
                *[f"- {marker}" for marker in report.missing_required_markers],
            ]
        )
    return "\n".join(lines) + "\n"


def build_registry(root: Path) -> dict[str, Any]:
    render_services = _render_services(root)
    now = _rfc3339_now()
    apps = [_registry_entry(root, path, render_services) for path in iter_app_paths(root)]
    apps.sort(key=lambda item: item["path"])
    return {
        "schema": REGISTRY_SCHEMA,
        "description": REGISTRY_DESCRIPTION,
        "version": 1,
        "generated_at": now,
        "generated_by": "pwl registry-build",
        "apps": apps,
    }


def write_registry(root: Path) -> Path:
    path = root / REGISTRY_RELATIVE_PATH
    data = build_registry(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def detect_app_type(root: Path, path: Path) -> str:
    relative_parts = path.relative_to(root).parts
    parent = relative_parts[0] if relative_parts else ""
    framework = detect_framework(path)
    if parent == "apis" and _has_python_project(path):
        return "python-api"
    if parent == "apps" and framework == "Next.js":
        return "next-app"
    if parent in {"packages", "tools"}:
        return "package"
    if (path / "package.json").is_file():
        return "package"
    return "unknown"


def detect_language(path: Path) -> str:
    if _has_python_project(path):
        return "python"
    if (path / "package.json").is_file() or (path / "tsconfig.json").is_file():
        return "typescript"
    return "unknown"


def detect_framework(path: Path) -> str:
    package = _load_json_if_exists(path / "package.json")
    deps = _node_dependencies(package)
    if (
        "next" in deps
        or (path / "next.config.js").is_file()
        or (path / "next.config.mjs").is_file()
    ):
        return "Next.js"
    if _python_dependency_names(path) & {"fastapi"}:
        return "FastAPI"
    if (path / "pyproject.toml").is_file() or (path / "requirements.txt").is_file():
        return "Python"
    if package is not None:
        return "Node"
    return "unknown"


def _registry_entry(root: Path, path: Path, render_services: dict[str, str]) -> dict[str, Any]:
    report = build_onboard_report(root, path.relative_to(root))
    language_version = _language_version(path, report.language, root)
    deploy_target, service_name = _deploy_target(root, path, render_services)
    return {
        "name": path.name,
        "path": path.relative_to(root).as_posix(),
        "type": report.app_type,
        "framework": report.framework,
        "language": report.language,
        "language_version": language_version,
        "package_manager": _package_manager(root, path, report.language),
        "test_runner": _test_runner(path, report.language),
        "linter": _linter(path, report.language),
        "formatter": _formatter(path, report.language),
        "deploy_target": deploy_target,
        "service_name": service_name,
        "owner_persona": _owner_persona(path),
        "conformance": {
            "score": report.conformance_score,
            "missing_markers": report.missing_required_markers,
        },
        "size_signals": _size_signals(path),
        "last_modified": _last_modified(root, path),
        "depends_on_services": _depends_on_services(path),
    }


def _marker_results(root: Path, path: Path, app_type: str, language: str) -> list[MarkerResult]:
    markers: list[MarkerResult] = []
    if language == "python":
        pyproject = _load_toml_if_exists(path / "pyproject.toml")
        has_pyproject = pyproject is not None
        ruff_present = bool(_toml_get(pyproject, ("tool", "ruff"))) if pyproject else False
        pytest_present = (
            bool(_toml_get(pyproject, ("tool", "pytest", "ini_options"))) if pyproject else False
        )
        markers.extend(
            [
                _marker("pyproject.toml", True, has_pyproject, "missing Python project metadata"),
                _marker("[tool.ruff]", True, ruff_present, "missing Ruff configuration"),
                _marker(
                    "[tool.pytest.ini_options]",
                    True,
                    pytest_present,
                    "missing pytest configuration",
                ),
                _marker(".python-version", True, (path / ".python-version").is_file(), "missing"),
            ]
        )
    if language in {"typescript", "javascript"} or (path / "package.json").is_file():
        markers.append(_marker("package.json", True, (path / "package.json").is_file(), "missing"))
    if app_type == "python-api":
        markers.append(
            _marker("Dockerfile", True, (path / "Dockerfile").is_file(), "missing API image")
        )
    markers.extend(
        [
            _marker("tests/", True, _has_tests(path), "no test files found"),
            _marker("README.md", True, (path / "README.md").is_file(), "missing"),
        ]
    )
    if _is_brain_managed(root, path):
        markers.append(
            _marker(
                "medallion comment",
                True,
                _has_medallion_marker(path),
                "missing medallion marker in source files",
            )
        )
    return markers


def _marker(marker: str, required: bool, present: bool, gap_when_missing: str) -> MarkerResult:
    return MarkerResult(marker, required, present, "" if present else gap_when_missing)


def _has_python_project(path: Path) -> bool:
    return (path / "pyproject.toml").is_file() or (path / "requirements.txt").is_file()


def _load_toml_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"{path} must be a JSON object"
        raise ValueError(msg)
    return raw


def _toml_get(data: dict[str, Any] | None, keys: tuple[str, ...]) -> Any:
    node: Any = data
    for key in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _has_tests(path: Path) -> bool:
    for pattern in _TEST_PATTERNS:
        if any(candidate.is_file() for candidate in path.rglob(pattern)):
            return True
    return False


def _is_brain_managed(root: Path, path: Path) -> bool:
    try:
        return path.relative_to(root).parts[:2] == ("apis", "brain")
    except ValueError:
        return False


def _has_medallion_marker(path: Path) -> bool:
    for candidate in _iter_source_files(path):
        try:
            if "medallion:" in candidate.read_text(encoding="utf-8"):
                return True
        except UnicodeDecodeError:
            continue
    return False


def _iter_source_files(path: Path) -> list[Path]:
    files: list[Path] = []
    for candidate in path.rglob("*"):
        if not candidate.is_file() or candidate.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
            continue
        if any(part in _IGNORED_SIZE_DIRS or part == "tests" for part in candidate.parts):
            continue
        files.append(candidate)
    return files[:500]


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _node_dependencies(package: dict[str, Any] | None) -> set[str]:
    if package is None:
        return set()
    deps: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        raw = package.get(key)
        if isinstance(raw, dict):
            deps.update(str(name) for name in raw)
    return deps


def _python_dependency_names(path: Path) -> set[str]:
    names: set[str] = set()
    pyproject = _load_toml_if_exists(path / "pyproject.toml")
    project_deps = _toml_get(pyproject, ("project", "dependencies"))
    if isinstance(project_deps, list):
        names.update(_normalize_dependency_name(str(dep)) for dep in project_deps)
    dependency_groups = _toml_get(pyproject, ("dependency-groups",))
    if isinstance(dependency_groups, dict):
        for group in dependency_groups.values():
            if isinstance(group, list):
                names.update(_normalize_dependency_name(str(dep)) for dep in group)
    requirements = path / "requirements.txt"
    if requirements.is_file():
        names.update(
            _normalize_dependency_name(line)
            for line in requirements.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    return {name for name in names if name}


def _normalize_dependency_name(raw: str) -> str:
    token = raw.strip().split(";", 1)[0].strip()
    for separator in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
        token = token.split(separator, 1)[0]
    return token.strip().lower().replace("_", "-")


def _language_version(path: Path, language: str, root: Path) -> str:
    if language == "python":
        version_file = path / ".python-version"
        if version_file.is_file():
            return version_file.read_text(encoding="utf-8").strip()
        pyproject = _load_toml_if_exists(path / "pyproject.toml")
        requires_python = _toml_get(pyproject, ("project", "requires-python"))
        if isinstance(requires_python, str):
            return requires_python
    if language == "typescript":
        node_version = root / ".node-version"
        if node_version.is_file():
            return node_version.read_text(encoding="utf-8").strip()
        root_package = _load_json_if_exists(root / "package.json")
        engines = root_package.get("engines") if root_package else None
        if isinstance(engines, dict) and isinstance(engines.get("node"), str):
            return engines["node"]
    return "unknown"


def _package_manager(root: Path, path: Path, language: str) -> str:
    if language == "python":
        if (path / "uv.lock").is_file() or (root / "uv.lock").is_file():
            return "uv"
        if (path / "requirements.txt").is_file():
            return "pip"
    if (path / "package.json").is_file():
        if (root / "pnpm-lock.yaml").is_file():
            return "pnpm"
        return "npm"
    return "unknown"


def _test_runner(path: Path, language: str) -> str:
    if language == "python":
        return "pytest" if _has_tests(path) else "unknown"
    package = _load_json_if_exists(path / "package.json")
    scripts = package.get("scripts") if package else None
    if isinstance(scripts, dict) and "test" in scripts:
        raw = str(scripts["test"])
        if "vitest" in raw:
            return "vitest"
        if "jest" in raw:
            return "jest"
        return raw.split(" ", 1)[0]
    return "unknown"


def _linter(path: Path, language: str) -> str:
    if language == "python":
        pyproject = _load_toml_if_exists(path / "pyproject.toml")
        return "ruff" if _toml_get(pyproject, ("tool", "ruff")) else "unknown"
    if (path / "eslint.config.mjs").is_file() or (path / ".eslintrc.json").is_file():
        return "eslint"
    return "unknown"


def _formatter(path: Path, language: str) -> str:
    if language == "python":
        return "ruff format" if _linter(path, language) == "ruff" else "unknown"
    package = _load_json_if_exists(path / "package.json")
    scripts = package.get("scripts") if package else None
    if isinstance(scripts, dict) and "format" in scripts:
        return str(scripts["format"])
    return "unknown"


def _render_services(root: Path) -> dict[str, str]:
    path = root / "render.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    services = data.get("services") if isinstance(data, dict) else None
    if not isinstance(services, list):
        return {}
    result: dict[str, str] = {}
    for service in services:
        if not isinstance(service, dict):
            continue
        name = service.get("name")
        if not isinstance(name, str):
            continue
        service_type = str(service.get("type") or "")
        root_dir = service.get("rootDir")
        if isinstance(root_dir, str):
            _record_render_service(result, root_dir.rstrip("/"), name, service_type)
        for key in ("buildCommand", "preDeployCommand", "startCommand", "dockerfilePath"):
            value = service.get(key)
            if isinstance(value, str):
                for parent in ("apis", "apps"):
                    marker = f"{parent}/"
                    if marker in value:
                        rel = value[value.index(marker) :].split()[0].split("&&")[0].strip()
                        _record_render_service(result, rel.rstrip("/"), name, service_type)
                        break
        dockerfile_path = service.get("dockerfilePath")
        if isinstance(dockerfile_path, str) and dockerfile_path.endswith("/Dockerfile"):
            _record_render_service(
                result,
                dockerfile_path.removesuffix("/Dockerfile"),
                name,
                service_type,
            )
    return result


def _record_render_service(result: dict[str, str], path: str, name: str, service_type: str) -> None:
    if path not in result or service_type == "web":
        result[path] = name


def _deploy_target(
    root: Path, path: Path, render_services: dict[str, str]
) -> tuple[str, str | None]:
    relative = path.relative_to(root).as_posix()
    if relative in render_services:
        return "render", render_services[relative]
    if (path / "vercel.json").is_file() or relative.startswith("apps/"):
        return "vercel", path.name
    return "unknown", None


def _owner_persona(path: Path) -> str:
    owner_by_name = {
        "axiomfolio": "systematic-trader",
        "brain": "ops-engineer",
        "filefree": "tax-domain",
        "launchfree": "ops-engineer",
        "studio": "ops-engineer",
    }
    return owner_by_name.get(path.name, "unassigned")


def _size_signals(path: Path) -> dict[str, int]:
    py_files = 0
    ts_files = 0
    lines = 0
    for candidate in path.rglob("*"):
        if not candidate.is_file() or any(part in _IGNORED_SIZE_DIRS for part in candidate.parts):
            continue
        if candidate.suffix == ".py":
            py_files += 1
        if candidate.suffix in {".ts", ".tsx"}:
            ts_files += 1
        if candidate.suffix in {".py", ".ts", ".tsx", ".js", ".jsx"}:
            try:
                lines += len(candidate.read_text(encoding="utf-8").splitlines())
            except UnicodeDecodeError:
                continue
    return {"py_files": py_files, "ts_files": ts_files, "lines_of_code_approx": lines}


def _last_modified(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", relative],
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        mtimes = [candidate.stat().st_mtime for candidate in path.rglob("*") if candidate.is_file()]
        if not mtimes:
            return _rfc3339_now()
        return datetime.fromtimestamp(max(mtimes), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = result.stdout.strip()
    if not raw:
        return _rfc3339_now()
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M:%SZ")


def _depends_on_services(path: Path) -> list[str]:
    services: set[str] = set()
    py_deps = _python_dependency_names(path)
    package = _load_json_if_exists(path / "package.json")
    node_deps = _node_dependencies(package)
    for service, dependency_names in _PY_DEPS.items():
        if py_deps.intersection(dependency_names):
            services.add(service)
    for service, dependency_names in _NODE_DEPS.items():
        if node_deps.intersection(dependency_names):
            services.add(service)
    return sorted(services)


def _rfc3339_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

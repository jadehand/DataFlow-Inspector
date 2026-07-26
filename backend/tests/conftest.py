from __future__ import annotations

import importlib
import inspect
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"


def ensure_backend_path() -> None:
    backend_path = str(BACKEND_DIR)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)


def configure_test_environment(base_dir: Path) -> None:
    os.environ["DFI_DATA_DIR"] = str(base_dir)
    os.environ["DFI_DB_PATH"] = str(base_dir / "test.db")
    os.environ["DFI_IMPORT_DIR"] = str(base_dir / "imports")


def call_app_factory(factory):
    signature = inspect.signature(factory)
    kwargs = {}
    if "testing" in signature.parameters:
        kwargs["testing"] = True
    required = [
        name
        for name, parameter in signature.parameters.items()
        if parameter.default is inspect._empty
        and parameter.kind
        in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD, parameter.KEYWORD_ONLY)
        and name not in kwargs
    ]
    if required:
        required_args = ", ".join(required)
        raise TypeError(f"create_app 需要额外参数: {required_args}")
    return factory(**kwargs)


def load_test_app():
    ensure_backend_path()
    temp_dir = Path(tempfile.mkdtemp(prefix="dataflow-inspector-tests-"))
    configure_test_environment(temp_dir)
    importlib.invalidate_caches()
    errors: list[str] = []

    for module_name, attr_name, kind in (
        ("app.factory", "create_app", "factory"),
        ("app.main", "create_app", "factory"),
        ("app.main", "app", "instance"),
    ):
        sys.modules.pop(module_name, None)
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        except Exception as exc:  # pragma: no cover - surfaced in assertion message
            errors.append(f"{module_name}: 导入失败: {exc}")
            continue

        if not hasattr(module, attr_name):
            errors.append(f"{module_name}: 缺少 {attr_name}")
            continue

        target = getattr(module, attr_name)
        try:
            app = call_app_factory(target) if kind == "factory" else target
        except Exception as exc:  # pragma: no cover - surfaced in assertion message
            errors.append(f"{module_name}:{attr_name}: 初始化失败: {exc}")
            continue

        if getattr(app, "router", None) is None:
            errors.append(f"{module_name}:{attr_name}: 不是可用的 ASGI app")
            continue
        return app, temp_dir

    joined = "; ".join(errors) if errors else "未发现 app.factory:create_app / app.main:create_app / app.main:app"
    raise RuntimeError(f"无法加载后端应用: {joined}")


ensure_backend_path()


@pytest.fixture(scope="session")
def app_and_data_dir():
    app, temp_dir = load_test_app()
    try:
        yield app, temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def app(app_and_data_dir):
    loaded_app, _ = app_and_data_dir
    return loaded_app


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def route_methods_map(app) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = set(getattr(route, "methods", set()) or set())
        if path:
            mapping[path] = methods
    return mapping

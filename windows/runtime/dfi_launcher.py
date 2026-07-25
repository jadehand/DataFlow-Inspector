"""Start DataFlow Inspector as a local Windows application.

This module deliberately keeps process management in the Python standard
library.  FastAPI and Uvicorn are imported only by the ``serve`` child process,
so status and stop commands still work if the server cannot be imported.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Sequence


APP_NAME = "DataFlowInspector"
HOST = "127.0.0.1"
PORT_FIRST = 17600
PORT_LAST = 17699
START_TIMEOUT_SECONDS = 30.0
HEALTH_TIMEOUT_SECONDS = 1.5


def local_app_dir() -> Path:
    """Return the private per-user application directory."""
    override = os.getenv("DFI_LOCAL_APPDATA")
    if override:
        return Path(override).expanduser().resolve()
    base = os.getenv("LOCALAPPDATA")
    if not base:
        base = str(Path.home() / "AppData" / "Local")
    return Path(base) / APP_NAME


def app_paths() -> dict[str, Path]:
    base = local_app_dir()
    return {
        "base": base,
        "data": base / "data",
        "imports": base / "data" / "imports",
        "run": base / "run",
        "logs": base / "logs",
        "pid": base / "run" / "pid",
        "port": base / "run" / "port",
        "state": base / "run" / "runtime.json",
        "lock": base / "run" / "start.lock",
        "log": base / "logs" / "app.log",
    }


def ensure_app_dirs(paths: dict[str, Path]) -> None:
    for key in ("data", "imports", "run", "logs"):
        paths[key].mkdir(parents=True, exist_ok=True)


def find_install_root() -> Path:
    """Locate backend and frontend files in source and frozen layouts."""
    override = os.getenv("DFI_INSTALL_ROOT")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override))

    if getattr(sys, "frozen", False):
        candidates.extend(
            [
                Path(sys.executable).resolve().parent,
                Path(sys.executable).resolve().parent / "app",
            ]
        )
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            candidates.extend([Path(bundle_dir), Path(bundle_dir) / "app"])

    here = Path(__file__).resolve()
    candidates.extend(
        [
            here.parents[2],
            here.parents[2] / "app",
            here.parents[1],
            Path.cwd(),
            Path.cwd() / "app",
        ]
    )
    for candidate in candidates:
        root = candidate.expanduser().resolve()
        if (
            (root / "backend" / "app" / "main.py").is_file()
            and (root / "frontend" / "src" / "index.html").is_file()
        ):
            return root
    raise RuntimeError(
        "找不到程序资源，请重新安装 DataFlow Inspector，"
        "或将 DFI_INSTALL_ROOT 指向包含 backend 和 frontend 的目录。"
    )


def choose_port(first: int = PORT_FIRST, last: int = PORT_LAST) -> int:
    for port in range(first, last + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            try:
                listener.bind((HOST, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"本地端口 {first}-{last} 均已被占用。")


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            waited_pid, _status = os.waitpid(pid, os.WNOHANG)
            if waited_pid == pid:
                return False
        except ChildProcessError:
            # The process was started by a different launcher invocation.
            pass
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def read_state(paths: dict[str, Path]) -> dict[str, Any] | None:
    try:
        state = json.loads(paths["state"].read_text(encoding="utf-8"))
        state["pid"] = int(state["pid"])
        state["port"] = int(state["port"])
        return state
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def write_state(paths: dict[str, Path], pid: int, port: int) -> None:
    ensure_app_dirs(paths)
    paths["pid"].write_text(str(pid), encoding="ascii")
    paths["port"].write_text(str(port), encoding="ascii")
    state = {
        "pid": pid,
        "port": port,
        "host": HOST,
        "url": f"http://{HOST}:{port}/",
        "started_at": time.time(),
        "log": str(paths["log"]),
    }
    temporary = paths["state"].with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(paths["state"])


def clear_state(paths: dict[str, Path]) -> None:
    for key in ("pid", "port", "state"):
        try:
            paths[key].unlink()
        except FileNotFoundError:
            pass


def health_request(port: int) -> dict[str, Any] | None:
    url = f"http://{HOST}:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=HEALTH_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read().decode("utf-8"))
    except (
        OSError,
        ValueError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ):
        return None
    if payload.get("status") != "ok" or not payload.get("version"):
        return None
    return payload


def child_command(port: int) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "serve", "--port", str(port)]
    return [sys.executable, str(Path(__file__).resolve()), "serve", "--port", str(port)]


def acquire_start_lock(paths: dict[str, Path]) -> int:
    ensure_app_dirs(paths)
    try:
        return os.open(paths["lock"], os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        try:
            age = time.time() - paths["lock"].stat().st_mtime
        except OSError:
            age = 0
        if age > START_TIMEOUT_SECONDS * 2:
            paths["lock"].unlink(missing_ok=True)
            return os.open(paths["lock"], os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        raise RuntimeError("程序正在启动，请稍候。") from exc


def release_start_lock(paths: dict[str, Path], descriptor: int) -> None:
    os.close(descriptor)
    paths["lock"].unlink(missing_ok=True)


def start(open_browser: bool = True) -> int:
    paths = app_paths()
    ensure_app_dirs(paths)
    lock_descriptor = acquire_start_lock(paths)
    try:
        existing = read_state(paths)
        if existing and process_alive(existing["pid"]):
            if health_request(existing["port"]):
                if open_browser:
                    webbrowser.open(existing["url"])
                print(f"DataFlow Inspector 已在运行：{existing['url']}")
                return 0
            if time.time() - float(existing.get("started_at", 0)) < START_TIMEOUT_SECONDS:
                raise RuntimeError("程序仍在启动，请稍候再试。")
        clear_state(paths)

        install_root = find_install_root()
        port = choose_port()
        environment = os.environ.copy()
        environment.update(
            {
                "DFI_INSTALL_ROOT": str(install_root),
                "DFI_LOCAL_APPDATA": str(paths["base"]),
                "PYTHONUTF8": "1",
                "PYTHONUNBUFFERED": "1",
            }
        )
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with paths["log"].open("a", encoding="utf-8", buffering=1) as log_file:
            process = subprocess.Popen(
                child_command(port),
                cwd=install_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
                close_fds=True,
            )
        write_state(paths, process.pid, port)

        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            payload = health_request(port)
            if payload:
                url = f"http://{HOST}:{port}/"
                if open_browser:
                    webbrowser.open(url)
                print(f"DataFlow Inspector 已启动：{url}")
                return 0
            if process.poll() is not None:
                clear_state(paths)
                raise RuntimeError(f"程序启动失败，请查看日志：{paths['log']}")
            time.sleep(0.25)

        terminate_process(process.pid)
        clear_state(paths)
        raise RuntimeError(f"程序启动超时，请查看日志：{paths['log']}")
    finally:
        release_start_lock(paths, lock_descriptor)


def terminate_process(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for _ in range(20):
            if not process_alive(pid):
                return
            time.sleep(0.1)
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return


def stop() -> int:
    paths = app_paths()
    state = read_state(paths)
    if not state:
        clear_state(paths)
        print("DataFlow Inspector 当前未运行。")
        return 0

    pid, port = state["pid"], state["port"]
    if not process_alive(pid):
        clear_state(paths)
        print("DataFlow Inspector 当前未运行，已清理过期状态。")
        return 0

    # A stale PID can be reused by Windows. Only terminate a process that
    # answers as DataFlow Inspector on the recorded local port.
    if not health_request(port):
        print(
            "未停止进程：记录的端口不是健康的 DataFlow Inspector。"
            f"请检查日志：{paths['log']}",
            file=sys.stderr,
        )
        return 1

    terminate_process(pid)
    deadline = time.monotonic() + 5
    while process_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    clear_state(paths)
    if process_alive(pid):
        print("停止超时，请在任务管理器中结束 DataFlow Inspector。", file=sys.stderr)
        return 1
    print("DataFlow Inspector 已停止。")
    return 0


def health() -> int:
    paths = app_paths()
    state = read_state(paths)
    if not state or not process_alive(state["pid"]):
        print("DataFlow Inspector 未运行。")
        return 1
    payload = health_request(state["port"])
    if not payload:
        print(f"DataFlow Inspector 进程存在但服务未就绪。日志：{paths['log']}")
        return 1
    print(
        f"DataFlow Inspector 运行正常，版本 {payload['version']}："
        f"http://{HOST}:{state['port']}/"
    )
    return 0


def serve(port: int) -> int:
    if not PORT_FIRST <= port <= PORT_LAST:
        raise RuntimeError(f"本地服务端口必须在 {PORT_FIRST}-{PORT_LAST} 范围内。")
    paths = app_paths()
    ensure_app_dirs(paths)
    install_root = find_install_root()
    os.environ["DFI_DATA_DIR"] = str(paths["data"])
    os.environ["DFI_DB_PATH"] = str(paths["data"] / "dataflow.db")
    os.environ["DFI_IMPORT_DIR"] = str(paths["imports"])
    sys.path.insert(0, str(install_root / "backend"))

    import uvicorn
    from fastapi.staticfiles import StaticFiles
    from app.main import app

    app.mount(
        "/",
        StaticFiles(directory=install_root / "frontend" / "src", html=True),
        name="local-ui",
    )
    write_state(paths, os.getpid(), port)
    try:
        uvicorn.run(
            app,
            host=HOST,
            port=port,
            log_level=os.getenv("DFI_LOG_LEVEL", "info"),
            access_log=False,
        )
    finally:
        current = read_state(paths)
        if current and current["pid"] == os.getpid():
            clear_state(paths)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DataFlow Inspector 本地运行器")
    subparsers = parser.add_subparsers(dest="command")
    start_parser = subparsers.add_parser("start", help="启动并打开浏览器")
    start_parser.add_argument(
        "--no-browser", action="store_true", help="启动后不自动打开浏览器"
    )
    subparsers.add_parser("stop", help="停止本地服务")
    subparsers.add_parser("health", help="检查本地服务状态")
    serve_parser = subparsers.add_parser("serve", help=argparse.SUPPRESS)
    serve_parser.add_argument("--port", type=int, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "start"
    try:
        if command == "start":
            return start(open_browser=not getattr(args, "no_browser", False))
        if command == "stop":
            return stop()
        if command == "health":
            return health()
        if command == "serve":
            return serve(args.port)
    except (OSError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Entry point used by the desktop sidecar and PyInstaller build."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import shutil
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _configure_frozen_runtime() -> None:
    if not getattr(sys, "frozen", False):
        return
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    local_root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    data_root = Path(os.environ.setdefault("REG_FACTORY_DATA_DIR", str(local_root / "RegFactory")))
    env_path = Path(os.environ.setdefault("REG_FACTORY_ENV_FILE", str(data_root / ".env")))
    data_root.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        example = bundle_root / ".env.example"
        if example.is_file():
            shutil.copyfile(example, env_path)

    helper = bundle_root / "common" / "bundled_browser_helper.py"
    if helper.is_file():
        os.environ.setdefault("REG_FACTORY_BROWSER_HELPER", str(helper))


def _port_available(host: str, port: int) -> bool:
    bind_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((bind_host, port))
        return True
    except OSError:
        return False


def _existing_reg_factory(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1) as response:
            payload = json.load(response)
        return isinstance(payload, dict) and "browser_provider" in payload and "running" in payload
    except Exception:
        return False


def _open_when_ready(port: int) -> None:
    url = f"http://127.0.0.1:{port}/"
    for _ in range(80):
        try:
            with urllib.request.urlopen(url, timeout=1):
                pass
            webbrowser.open(url)
            return
        except Exception:
            time.sleep(0.25)


def _select_port(host: str, requested: int) -> tuple[int, bool]:
    if _port_available(host, requested):
        return requested, False
    if _existing_reg_factory(requested):
        return requested, True
    for candidate in range(requested + 1, requested + 21):
        if _port_available(host, candidate):
            print(f"[reg-factory] 端口 {requested} 已占用，自动改用 {candidate}", flush=True)
            return candidate, False
    raise RuntimeError(f"端口 {requested}-{requested + 20} 均不可用")


def _pause_after_error() -> None:
    if not getattr(sys, "frozen", False):
        return
    try:
        input("\n启动失败，请截图保存上面的错误。按回车键退出...")
    except (EOFError, KeyboardInterrupt):
        pass


def main() -> None:
    _configure_frozen_runtime()
    raw_args = list(sys.argv[1:])
    if raw_args[:1] == ["-u"]:
        raw_args = raw_args[1:]
    if raw_args and (raw_args[0] == "--task" or raw_args[0].lower().endswith(".py")):
        target = raw_args[1] if raw_args[0] == "--task" and len(raw_args) > 1 else raw_args[0]
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
        target_path = root / target
        if not target_path.is_file():
            raise SystemExit(f"task script not found: {target}")
        sys.path.insert(0, str(root))
        arg_offset = 2 if raw_args[0] == "--task" else 1
        sys.argv = [str(target_path), *raw_args[arg_offset:]]
        runpy.run_path(str(target_path), run_name="__main__")
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8799)
    args = parser.parse_args()
    port, already_running = _select_port(args.host, args.port)
    url = f"http://127.0.0.1:{port}/"
    if already_running:
        print(f"[reg-factory] 服务已在运行：{url}", flush=True)
        webbrowser.open(url)
        time.sleep(1)
        return
    print(f"[reg-factory] 正在启动：{url}", flush=True)
    threading.Thread(target=_open_when_ready, args=(port,), daemon=True).start()
    uvicorn.run("webui.server:app", host=args.host, port=port, log_level="warning")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except BaseException as exc:
        print(f"\n[reg-factory] 启动失败：{exc}", file=sys.stderr, flush=True)
        _pause_after_error()
        raise

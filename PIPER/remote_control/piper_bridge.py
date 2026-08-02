#!/usr/bin/env python3
"""Loopback-only HTTP bridge for an AgileX PIPER arm."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import platform
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse

from bridge_core import (
    BRIDGE_VERSION,
    BridgeController,
    BridgeFault,
    MockBackend,
    PiperBackend,
)


MAX_REQUEST_BYTES = 16 * 1024


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


class PiperHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, controller: BridgeController, token: str):
        super().__init__(address, PiperRequestHandler)
        self.controller = controller
        self.token = token


class PiperRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "PiperBridge/" + BRIDGE_VERSION

    @property
    def bridge_server(self) -> PiperHTTPServer:
        return self.server  # type: ignore[return-value]

    def _send(self, status: int, payload: Any) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, fault: BridgeFault) -> None:
        self._send(
            fault.http_status,
            {"ok": False, "error": {"code": fault.code, "message": fault.message}},
        )

    def _authorized(self) -> bool:
        value = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not value.startswith(prefix):
            return False
        return hmac.compare_digest(value[len(prefix) :], self.bridge_server.token)

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._send(
            401,
            {"ok": False, "error": {"code": "unauthorized", "message": "invalid bearer token"}},
        )
        return False

    def _read_json(self) -> Dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise BridgeFault("invalid_request", "invalid Content-Length") from exc
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise BridgeFault("invalid_request", "request body is too large", 413)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BridgeFault("invalid_json", "request body must be valid UTF-8 JSON") from exc
        if not isinstance(value, dict):
            raise BridgeFault("invalid_request", "JSON body must be an object")
        return value

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/v1/health":
            self._send(
                200,
                {
                    "ok": True,
                    "bridge_version": BRIDGE_VERSION,
                    "mode": "control" if self.bridge_server.controller.allow_motion else "observe",
                },
            )
            return
        if not self._require_auth():
            return
        try:
            if path == "/v1/state":
                self._send(200, {"ok": True, "state": self.bridge_server.controller.snapshot()})
                return
            prefix = "/v1/commands/"
            if path.startswith(prefix):
                command_id = path[len(prefix) :]
                command = self.bridge_server.controller.command(command_id)
                self._send(200, {"ok": True, "command": command})
                return
            raise BridgeFault("not_found", "unknown endpoint", 404)
        except BridgeFault as fault:
            self._send_error(fault)
        except Exception as exc:
            self._send_error(BridgeFault("internal_error", str(exc), 500))

    def do_POST(self) -> None:
        if not self._require_auth():
            return
        path = urlparse(self.path).path
        try:
            body = self._read_json()
            controller = self.bridge_server.controller
            if path == "/v1/prepare":
                self._send(200, {"ok": True, "arm": controller.prepare()})
                return
            if path == "/v1/enable":
                self._send(200, {"ok": True, "arm": controller.enable()})
                return
            if path == "/v1/move-joints":
                command = controller.submit_move(body)
                self._send(202, {"ok": True, "command": command})
                return
            if path == "/v1/gripper/calibrate":
                self._send(200, {"ok": True, "arm": controller.calibrate_gripper(body)})
                return
            if path == "/v1/gripper/move-width":
                command = controller.submit_gripper_move(body)
                self._send(202, {"ok": True, "command": command})
                return
            if path == "/v1/gripper/disable":
                self._send(200, {"ok": True, "arm": controller.disable_gripper()})
                return
            if path == "/v1/stop":
                self._send(200, {"ok": True, "arm": controller.stop("remote stop")})
                return
            raise BridgeFault("not_found", "unknown endpoint", 404)
        except BridgeFault as fault:
            self._send_error(fault)
        except Exception as exc:
            self._send_error(BridgeFault("internal_error", str(exc), 500))

    def log_message(self, fmt: str, *args) -> None:
        print(f"HTTP {self.client_address[0]} - {fmt % args}")


def _read_token(args) -> str:
    token = os.environ.get("PIPER_BRIDGE_TOKEN", "")
    token_path = (
        Path(args.token_file).expanduser()
        if args.token_file
        else Path(__file__).resolve().with_name("session-token.txt")
    )
    if not token and token_path.is_file():
        token = token_path.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SystemExit(
            "PIPER_BRIDGE_TOKEN must contain at least 32 characters "
            "(or provide --token-file)"
        )
    return token


def _default_interface() -> str:
    return "agx_cando" if platform.system() == "Windows" else "socketcan"


def _default_channel(interface: str) -> str:
    return "0" if interface == "agx_cando" else "can0"


def _console_loop(controller: BridgeController) -> None:
    print()
    print("Local safety console commands:")
    print("  ARM WORKSPACE CLEAR  permit remote control until DISARM, STOP, or exit")
    print("  DISARM               reject future enable/move requests")
    print("  STOP                 send a damped electronic emergency stop")
    print("  STATE                print current state")
    print("Keep this window visible while remote control is permitted.")
    while True:
        try:
            command = input("PIPER(local)> ").strip().upper()
        except EOFError:
            return
        try:
            if command == "ARM WORKSPACE CLEAR":
                seconds = controller.grant_operator_permit()
                if seconds is None:
                    print("Remote control permitted for this bridge session.")
                else:
                    print(f"Remote control permitted for {seconds:.0f} seconds.")
            elif command == "DISARM":
                controller.revoke_operator_permit()
                print("Remote enable/move permission revoked. The arm was not disabled.")
            elif command == "STOP":
                controller.stop("local console stop")
                print("Electronic stop sent; remote motion permission revoked.")
            elif command == "STATE":
                print(json.dumps(controller.snapshot(), ensure_ascii=False, indent=2, default=str))
            elif command:
                print("Unknown command. Use ARM WORKSPACE CLEAR, DISARM, STOP, or STATE.")
        except Exception as exc:
            print(f"Local command failed: {exc}")


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("mock", "real"), default="mock")
    parser.add_argument("--mode", choices=("observe", "control"), default="observe")
    parser.add_argument(
        "--model",
        choices=("piper", "piper_h", "piper_l", "piper_x"),
        default="piper",
    )
    parser.add_argument(
        "--firmware",
        choices=("default", "v183", "v188", "v189"),
        default="default",
    )
    parser.add_argument(
        "--gripper",
        choices=("none", "agx"),
        default="none",
        help="initialize the original AgileX gripper driver",
    )
    parser.add_argument("--interface", default=None)
    parser.add_argument("--channel", default=None)
    parser.add_argument(
        "--permit-duration-s",
        type=float,
        default=None,
        help="optional timed permit; default is until DISARM, STOP, or bridge exit",
    )
    parser.add_argument(
        "--max-speed-percent",
        type=int,
        choices=range(1, 101),
        default=5,
        metavar="1..100",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="local loopback port; 0 asks Windows to choose an available port",
    )
    parser.add_argument("--token-file", default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    token = _read_token(args)
    interface = args.interface or _default_interface()
    channel = args.channel or _default_channel(interface)
    if args.backend == "mock":
        backend = MockBackend(model=args.model, gripper=args.gripper)
    else:
        backend = PiperBackend(
            model=args.model,
            firmware=args.firmware,
            interface=interface,
            channel=channel,
            gripper=args.gripper,
        )
    controller = BridgeController(
        backend,
        allow_motion=args.mode == "control",
        permit_duration_s=args.permit_duration_s,
        max_speed_percent=args.max_speed_percent,
    )
    server = None
    try:
        print(
            f"Connecting backend={args.backend}, model={args.model}, "
            f"firmware={args.firmware}, gripper={args.gripper}, "
            f"interface={interface}, channel={channel} ..."
        )
        controller.connect()
        initial = controller.snapshot()
        print(json.dumps(initial, ensure_ascii=False, indent=2, default=str))
        server = PiperHTTPServer(("127.0.0.1", args.port), controller, token)
        actual_port = server.server_address[1]
        if args.mode == "control":
            threading.Thread(target=_console_loop, args=(controller,), daemon=True).start()
        print(f"PIPER bridge ready on http://127.0.0.1:{actual_port} ({args.mode} mode)")
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nBridge shutdown requested.")
    finally:
        if server is not None:
            server.server_close()
        controller.close()
        print("CAN connection closed. Joint enable state was not changed automatically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

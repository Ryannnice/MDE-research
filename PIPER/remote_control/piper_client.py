#!/usr/bin/env python3
"""Server-side client for the loopback PIPER bridge."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TERMINAL_STATES = {"completed", "stopped", "fault", "timed_out", "error"}
MAX_SEQUENCE_WAYPOINT_STEP_DEG = 2.0
SEQUENCE_DWELL_S = 0.5


class ClientError(RuntimeError):
    pass


class PiperClient:
    def __init__(self, base_url: str, token: str, timeout_s: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout_s = timeout_s

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        authenticated: bool = True,
    ) -> Dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body, allow_nan=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                payload = json.loads(exc.read().decode("utf-8"))
                detail = payload.get("error", {})
                message = f"{detail.get('code', exc.code)}: {detail.get('message', exc.reason)}"
            except Exception:
                message = f"HTTP {exc.code}: {exc.reason}"
            raise ClientError(message) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ClientError(str(exc)) from exc
        if not payload.get("ok"):
            raise ClientError(str(payload))
        return payload

    def health(self):
        return self.request("GET", "/v1/health", authenticated=False)

    def state(self):
        return self.request("GET", "/v1/state")["state"]

    def prepare(self):
        return self.request("POST", "/v1/prepare", {})

    def enable(self):
        return self.request("POST", "/v1/enable", {})

    def stop(self):
        return self.request("POST", "/v1/stop", {})

    def calibrate_gripper(self, expected_current_m):
        return self.request(
            "POST",
            "/v1/gripper/calibrate",
            {
                "confirm_fully_closed": True,
                "expected_current_width_m": expected_current_m,
            },
        )

    def disable_gripper(self):
        return self.request("POST", "/v1/gripper/disable", {})

    def move_gripper_width(self, target_m, expected_current_m, force_n):
        command_id = uuid.uuid4().hex
        payload = {
            "command_id": command_id,
            "target_width_m": target_m,
            "expected_current_width_m": expected_current_m,
            "force_n": force_n,
        }
        return self.request("POST", "/v1/gripper/move-width", payload)["command"]

    def move_joints(self, target_rad, expected_current_rad, speed_percent: int):
        command_id = uuid.uuid4().hex
        payload = {
            "command_id": command_id,
            "target_rad": target_rad,
            "expected_current_rad": expected_current_rad,
            "speed_percent": speed_percent,
        }
        return self.request("POST", "/v1/move-joints", payload)["command"]

    def command(self, command_id: str):
        return self.request("GET", f"/v1/commands/{command_id}")["command"]

    def wait_command(self, command_id: str, timeout_s: float = 15.0):
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            command = self.command(command_id)
            if command["status"] in TERMINAL_STATES:
                return command
            time.sleep(0.1)
        raise ClientError(f"client timed out waiting for command {command_id}")


def _default_token_file() -> Path:
    return Path(__file__).resolve().with_name("session-token.txt")


def _read_token(path: Optional[str]) -> str:
    token = os.environ.get("PIPER_BRIDGE_TOKEN", "")
    token_path = Path(path).expanduser() if path else _default_token_file()
    if not token and token_path.is_file():
        token = token_path.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise SystemExit(
            "No valid token. Set PIPER_BRIDGE_TOKEN or create session-token.txt "
            "beside this script."
        )
    return token


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _joint_values(state: Dict[str, Any]):
    values = state.get("arm", {}).get("joint_angles_rad")
    if not isinstance(values, list) or len(values) != 6:
        raise ClientError("bridge did not return six joint angles")
    return [float(value) for value in values]


def _gripper_width(state: Dict[str, Any]) -> float:
    gripper = state.get("arm", {}).get("gripper", {})
    value = gripper.get("value")
    if (
        not gripper.get("configured")
        or not gripper.get("feedback_present")
        or gripper.get("mode") != "width"
        or isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise ClientError("bridge did not return valid AGX gripper width feedback")
    return float(value)


def _validate_gripper_request(
    state: Dict[str, Any], target_m: float, force_n: float
) -> None:
    bridge = state.get("bridge", {})
    width_limits = bridge.get("gripper_width_limits_m")
    force_limits = bridge.get("gripper_force_limits_n")
    if (
        not isinstance(width_limits, list)
        or len(width_limits) != 2
        or not all(isinstance(value, (int, float)) for value in width_limits)
    ):
        raise ClientError("bridge does not expose gripper limits; install bridge v0.5.0")
    if (
        not isinstance(force_limits, list)
        or len(force_limits) != 2
        or not all(isinstance(value, (int, float)) for value in force_limits)
    ):
        raise ClientError("bridge does not expose gripper force limits")
    if not math.isfinite(target_m) or not width_limits[0] <= target_m <= width_limits[1]:
        raise ClientError(
            f"target gripper width must be within {width_limits} meters"
        )
    if not math.isfinite(force_n) or not force_limits[0] <= force_n <= force_limits[1]:
        raise ClientError(f"gripper force must be within {force_limits} newtons")


def _validate_motion_request(
    state: Dict[str, Any], target: List[float], speed_percent: int
) -> int:
    if len(target) != 6 or not all(math.isfinite(value) for value in target):
        raise ClientError("target must contain six finite joint angles")

    bridge = state.get("bridge", {})
    limits = bridge.get("joint_limits_rad")
    if (
        not isinstance(limits, list)
        or len(limits) != 6
        or any(not isinstance(pair, list) or len(pair) != 2 for pair in limits)
    ):
        raise ClientError(
            "bridge does not expose joint limits; install bridge v0.3.0 or newer"
        )
    for index, (value, pair) in enumerate(zip(target, limits), start=1):
        low, high = pair
        if not all(isinstance(bound, (int, float)) and math.isfinite(bound) for bound in pair):
            raise ClientError(f"bridge returned invalid limits for joint {index}")
        if not low <= value <= high:
            raise ClientError(
                f"joint {index} target {value:.6f} rad is outside [{low}, {high}]"
            )

    max_speed = bridge.get("max_speed_percent")
    if isinstance(max_speed, bool) or not isinstance(max_speed, int):
        raise ClientError("bridge did not return a valid max_speed_percent")
    if isinstance(speed_percent, bool) or not 1 <= speed_percent <= max_speed:
        raise ClientError(f"speed_percent must be between 1 and {max_speed}")
    return max_speed


def _joint_waypoints(start: List[float], target: List[float]) -> List[List[float]]:
    if len(start) != 6 or len(target) != 6:
        raise ClientError("start and target must each contain six joint angles")
    if not all(math.isfinite(value) for value in start + target):
        raise ClientError("start and target joint angles must be finite")
    max_delta = max(abs(b - a) for a, b in zip(start, target))
    if max_delta == 0.0:
        return []
    max_step = math.radians(MAX_SEQUENCE_WAYPOINT_STEP_DEG)
    count = math.ceil(max_delta / max_step)
    return [
        [a + (b - a) * index / count for a, b in zip(start, target)]
        for index in range(1, count + 1)
    ]


def _run_joint_leg(client: PiperClient, target: List[float], speed: int, label: str) -> int:
    leg_start = _joint_values(client.state())
    waypoints = _joint_waypoints(leg_start, target)
    total = len(waypoints)
    for index, waypoint in enumerate(waypoints, start=1):
        current = _joint_values(client.state())
        command = client.move_joints(waypoint, current, speed)
        result = client.wait_command(command["command_id"])
        if result["status"] != "completed":
            raise ClientError(
                f"{label} waypoint {index}/{total} ended as {result['status']}: "
                f"{result.get('detail')}"
            )
        if index == 1 or index % 10 == 0 or index == total:
            print(f"{label}: waypoint {index}/{total} completed", flush=True)
    return total


def _run_joint_cycles(client: PiperClient, args) -> int:
    initial_state = client.state()
    start = _joint_values(initial_state)
    target = [float(value) for value in args.target_rad]
    max_speed = _validate_motion_request(initial_state, target, args.speed_percent)
    up_count = len(_joint_waypoints(start, target))
    down_count = len(_joint_waypoints(target, start))
    preview = {
        "start_rad": start,
        "target_rad": target,
        "delta_deg": [round(math.degrees(b - a), 6) for a, b in zip(start, target)],
        "cycles": args.cycles,
        "max_waypoint_step_deg": MAX_SEQUENCE_WAYPOINT_STEP_DEG,
        "planned_waypoints": args.cycles * (up_count + down_count),
        "speed_percent": args.speed_percent,
        "bridge_max_speed_percent": max_speed,
    }
    _print(preview)
    if not args.execute:
        print("Preview only. Add --execute after the on-site operator approves this sequence.")
        return 2

    for cycle in range(1, args.cycles + 1):
        _run_joint_leg(client, target, args.speed_percent, f"cycle {cycle} up")
        time.sleep(SEQUENCE_DWELL_S)
        _run_joint_leg(client, start, args.speed_percent, f"cycle {cycle} return")
        if cycle != args.cycles:
            time.sleep(SEQUENCE_DWELL_S)

    final_state = client.state()
    final = _joint_values(final_state)
    _print(
        {
            "status": "completed",
            "cycles": args.cycles,
            "final_rad": final,
            "return_error_deg": [
                round(math.degrees(actual - expected), 6)
                for actual, expected in zip(final, start)
            ],
            "arm_status": final_state["arm"].get("arm_status"),
            "err_code": final_state["arm"].get("err_code"),
        }
    )
    return 0


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("PIPER_BRIDGE_URL", "http://127.0.0.1:8765"),
    )
    parser.add_argument("--token-file", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("health")
    subparsers.add_parser("state")
    subparsers.add_parser("prepare")
    subparsers.add_parser("enable")
    subparsers.add_parser("stop")

    relative = subparsers.add_parser("move-relative")
    relative.add_argument("--joint", type=int, choices=range(1, 7), required=True)
    relative.add_argument("--degrees", type=float, required=True)
    relative.add_argument("--speed-percent", type=int, default=5)
    relative.add_argument("--execute", action="store_true")

    absolute = subparsers.add_parser("move-absolute")
    absolute.add_argument("--target-rad", type=float, nargs=6, required=True)
    absolute.add_argument("--speed-percent", type=int, default=5)
    absolute.add_argument("--execute", action="store_true")

    cycle = subparsers.add_parser("cycle-absolute")
    cycle.add_argument("--target-rad", type=float, nargs=6, required=True)
    cycle.add_argument("--cycles", type=_positive_int, default=1)
    cycle.add_argument("--speed-percent", type=int, default=5)
    cycle.add_argument("--execute", action="store_true")

    gripper_calibrate = subparsers.add_parser("gripper-calibrate")
    gripper_calibrate.add_argument("--confirm-fully-closed", action="store_true")
    gripper_calibrate.add_argument("--execute", action="store_true")

    gripper_move = subparsers.add_parser("gripper-move")
    gripper_move.add_argument("--width-mm", type=float, required=True)
    gripper_move.add_argument("--force-n", type=float, default=0.5)
    gripper_move.add_argument("--execute", action="store_true")

    gripper_disable = subparsers.add_parser("gripper-disable")
    gripper_disable.add_argument("--execute", action="store_true")

    command_status = subparsers.add_parser("command-status")
    command_status.add_argument("command_id")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    token = _read_token(args.token_file)
    client = PiperClient(args.url, token)

    if args.command == "health":
        _print(client.health())
        return 0
    if args.command == "state":
        _print(client.state())
        return 0
    if args.command == "prepare":
        _print(client.prepare())
        return 0
    if args.command == "enable":
        _print(client.enable())
        return 0
    if args.command == "stop":
        _print(client.stop())
        return 0
    if args.command == "command-status":
        _print(client.command(args.command_id))
        return 0
    if args.command == "cycle-absolute":
        return _run_joint_cycles(client, args)

    if args.command == "gripper-calibrate":
        state = client.state()
        gripper = state.get("arm", {}).get("gripper", {})
        current_m = _gripper_width(state)
        _print(
            {
                "operation": "set the current fully closed gripper position to zero",
                "current_gripper": gripper,
                "requires_driver_disabled": True,
                "confirmed_fully_closed": args.confirm_fully_closed,
            }
        )
        if not args.execute:
            print(
                "Preview only. Manually close the disabled gripper, then add "
                "--confirm-fully-closed --execute."
            )
            return 2
        if not args.confirm_fully_closed:
            raise ClientError("--confirm-fully-closed is required for calibration")
        _print(client.calibrate_gripper(current_m))
        return 0

    if args.command == "gripper-disable":
        state = client.state()
        _print(
            {
                "operation": "disable gripper driver",
                "current_gripper": state["arm"].get("gripper"),
            }
        )
        if not args.execute:
            print("Preview only. Add --execute to disable the gripper driver.")
            return 2
        _print(client.disable_gripper())
        return 0

    if args.command == "gripper-move":
        state = client.state()
        current_m = _gripper_width(state)
        target_m = args.width_mm / 1000.0
        _validate_gripper_request(state, target_m, args.force_n)
        _print(
            {
                "current_width_mm": current_m * 1000.0,
                "target_width_mm": args.width_mm,
                "force_n": args.force_n,
            }
        )
        if not args.execute:
            print("Preview only. Add --execute to move the gripper.")
            return 2
        command = client.move_gripper_width(target_m, current_m, args.force_n)
        result = client.wait_command(command["command_id"])
        _print({"command": result, "gripper": client.state()["arm"].get("gripper")})
        if result["status"] != "completed":
            raise ClientError(
                f"gripper command ended as {result['status']}: {result.get('detail')}"
            )
        return 0

    state = client.state()
    current = _joint_values(state)
    if args.command == "move-relative":
        if not math.isfinite(args.degrees):
            raise ClientError("degrees must be finite")
        target = list(current)
        target[args.joint - 1] += math.radians(args.degrees)
    else:
        target = list(args.target_rad)

    max_speed = _validate_motion_request(state, target, args.speed_percent)
    planned_waypoints = len(_joint_waypoints(current, target))
    preview = {
        "current_rad": current,
        "target_rad": target,
        "delta_deg": [round(math.degrees(b - a), 6) for a, b in zip(current, target)],
        "planned_waypoints": planned_waypoints,
        "max_waypoint_step_deg": MAX_SEQUENCE_WAYPOINT_STEP_DEG,
        "speed_percent": args.speed_percent,
        "bridge_max_speed_percent": max_speed,
    }
    _print(preview)
    if not args.execute:
        print("Preview only. Add --execute after the on-site operator approves this target.")
        return 2

    _run_joint_leg(client, target, args.speed_percent, "move")
    final_state = client.state()
    final = _joint_values(final_state)
    _print(
        {
            "status": "completed",
            "final_rad": final,
            "target_error_deg": [
                round(math.degrees(actual - expected), 6)
                for actual, expected in zip(final, target)
            ],
            "arm_status": final_state["arm"].get("arm_status"),
            "err_code": final_state["arm"].get("err_code"),
        }
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ClientError as exc:
        raise SystemExit(f"PIPER client error: {exc}") from exc

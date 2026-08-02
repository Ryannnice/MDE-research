"""Safety boundary and hardware adapters for remote PIPER control.

CAN access, joint-limit validation, operator permission, and command monitoring
remain on the computer beside the robot.
"""

from __future__ import annotations

import math
import platform
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional


BRIDGE_VERSION = "0.5.1"

GRIPPER_MIN_WIDTH_M = 0.0
GRIPPER_MAX_WIDTH_M = 0.07
GRIPPER_MAX_FORCE_N = 3.0


GRIPPER_FAULT_FIELDS = (
    "voltage_too_low",
    "motor_overheating",
    "driver_overcurrent",
    "driver_overheating",
    "sensor_status",
    "driver_error_status",
)


JOINT_LIMITS_RAD = {
    "piper": [
        [-2.617994, 2.617994],
        [0.0, 3.141593],
        [-2.967060, 0.0],
        [-1.745330, 1.745330],
        [-1.221730, 1.221730],
        [-2.094396, 2.094396],
    ],
    "piper_h": [
        [-2.617994, 2.617994],
        [0.0, 3.141593],
        [-2.967060, 0.0],
        [-2.356195, 2.356195],
        [-1.562070, 1.562070],
        [-3.141593, 3.141593],
    ],
    "piper_l": [
        [-2.617994, 2.617994],
        [0.0, 3.141593],
        [-2.967060, 0.0],
        [-2.216569, 2.216569],
        [-1.562070, 1.562070],
        [-3.141593, 3.141593],
    ],
    "piper_x": [
        [-2.617994, 2.617994],
        [0.0, 3.141593],
        [-2.967060, 0.0],
        [-1.553344, 1.553344],
        [-1.553344, 1.553344],
        [-3.141593, 3.141593],
    ],
}


class BridgeFault(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _enum_payload(value: Any) -> Dict[str, Any]:
    try:
        code = int(value)
    except (TypeError, ValueError):
        code = None
    return {"code": code, "name": getattr(value, "name", str(value))}


def _finite_float_list(value: Any, field: str, length: int = 6) -> List[float]:
    if not isinstance(value, list) or len(value) != length:
        raise BridgeFault("invalid_request", f"{field} must contain {length} numbers")
    result = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise BridgeFault("invalid_request", f"{field} must contain only numbers")
        number = float(item)
        if not math.isfinite(number):
            raise BridgeFault("invalid_request", f"{field} contains a non-finite number")
        result.append(number)
    return result


def _finite_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BridgeFault("invalid_request", f"{field} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise BridgeFault("invalid_request", f"{field} must be finite")
    return result


def _gripper_snapshot(gripper: Any) -> Dict[str, Any]:
    """Return AGX gripper telemetry without issuing any effector command."""
    result = {
        "configured": gripper is not None,
        "driver": "agx_gripper" if gripper is not None else None,
        "feedback_present": False,
        "healthy": False,
        "driver_ok": False,
        "value": None,
        "unit": None,
        "mode": None,
        "force_n": None,
        "feedback_hz": 0.0,
        "feedback_age_s": None,
        "status_code": None,
        "driver_enabled": None,
        "homed": None,
        "faults": {name: None for name in GRIPPER_FAULT_FIELDS},
        "read_error": None,
    }
    if gripper is None:
        return result

    try:
        result["driver_ok"] = bool(gripper.is_ok())
        status_msg = gripper.get_gripper_status()
    except Exception as exc:
        result["read_error"] = str(exc)
        return result
    if status_msg is None:
        return result

    try:
        status = status_msg.msg
        mode = str(status.mode)
        foc_status = status.foc_status
        faults = {
            name: bool(getattr(foc_status, name)) for name in GRIPPER_FAULT_FIELDS
        }
        timestamp = getattr(status_msg, "timestamp", None)
        result.update(
            {
                "feedback_present": True,
                "healthy": bool(result["driver_ok"] and not any(faults.values())),
                "value": float(status.value),
                "unit": "m" if mode == "width" else "deg" if mode == "angle" else None,
                "mode": mode,
                "force_n": float(status.force),
                "feedback_hz": float(getattr(status_msg, "hz", 0.0)),
                "feedback_age_s": (
                    max(0.0, time.time() - float(timestamp)) if timestamp else None
                ),
                "status_code": int(status.status_code),
                "driver_enabled": bool(foc_status.driver_enable_status),
                "homed": bool(foc_status.homing_status),
                "faults": faults,
            }
        )
    except Exception as exc:
        result["read_error"] = str(exc)
    return result


class MockBackend:
    """Deterministic backend used to verify the complete bridge without hardware."""

    def __init__(self, model: str = "piper", gripper: str = "none"):
        if gripper not in {"none", "agx"}:
            raise ValueError(f"unsupported gripper profile: {gripper}")
        self.model = model
        self.gripper_profile = gripper
        self.joint_limits = JOINT_LIMITS_RAD[model]
        self._lock = threading.RLock()
        self._connected = False
        self._enabled = False
        self._stopped = False
        self._joints = [0.0, 1.0, -1.2, 0.0, 0.0, 0.0]
        self._gripper_value = 0.07
        self._gripper_force = 0.0
        self._gripper_enabled = gripper == "agx"
        self._gripper_homed = gripper == "agx"

    def connect(self) -> None:
        with self._lock:
            self._connected = True

    def close(self) -> None:
        with self._lock:
            self._connected = False

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            arm_status = 1 if self._stopped else 0
            return {
                "connected": self._connected,
                "healthy": self._connected,
                "model": self.model,
                "firmware_profile": "mock",
                "firmware": {"software_version": "MOCK"},
                "joint_angles_rad": list(self._joints),
                "joint_feedback_hz": 200.0,
                "feedback_age_s": 0.0,
                "joints_enabled": [self._enabled] * 6,
                "enabled": self._enabled,
                "arm_status": {
                    "code": arm_status,
                    "name": "EMERGENCY_STOP" if arm_status else "NORMAL",
                },
                "motion_status": {"code": 0, "name": "REACHED"},
                "ctrl_mode": {"code": 1, "name": "CAN_CTRL"},
                "mode_feedback": {"code": 1, "name": "MOVE_J"},
                "teach_status": {"code": 0, "name": "DISABLED"},
                "err_code": 0,
                "comm_error": None,
                "gripper": (
                    {
                        "configured": True,
                        "driver": "agx_gripper",
                        "feedback_present": True,
                        "healthy": True,
                        "driver_ok": True,
                        "value": self._gripper_value,
                        "unit": "m",
                        "mode": "width",
                        "force_n": self._gripper_force,
                        "feedback_hz": 200.0,
                        "feedback_age_s": 0.0,
                        "status_code": (
                            (64 if self._gripper_enabled else 0)
                            | (128 if self._gripper_homed else 0)
                        ),
                        "driver_enabled": self._gripper_enabled,
                        "homed": self._gripper_homed,
                        "faults": {name: False for name in GRIPPER_FAULT_FIELDS},
                        "read_error": None,
                    }
                    if self.gripper_profile == "agx"
                    else _gripper_snapshot(None)
                ),
            }

    def enable(self, timeout_s: float = 5.0) -> bool:
        del timeout_s
        with self._lock:
            if self._stopped:
                return False
            self._enabled = True
            return True

    def enter_can_control(self, speed_percent: int, timeout_s: float = 2.0) -> bool:
        del speed_percent, timeout_s
        with self._lock:
            return self._connected and not self._stopped

    def move_joints(self, target_rad: List[float], speed_percent: int) -> None:
        del speed_percent
        with self._lock:
            if not self._enabled or self._stopped:
                raise RuntimeError("mock arm is not enabled")
            self._joints = list(target_rad)

    def calibrate_gripper(self, timeout_s: float = 2.0) -> bool:
        del timeout_s
        with self._lock:
            if self.gripper_profile != "agx" or self._gripper_enabled:
                return False
            self._gripper_value = 0.0
            self._gripper_homed = True
            return True

    def move_gripper_width(self, target_m: float, force_n: float) -> None:
        with self._lock:
            if self.gripper_profile != "agx" or not self._gripper_homed:
                raise RuntimeError("mock gripper is unavailable or not homed")
            self._gripper_enabled = True
            self._gripper_value = target_m
            self._gripper_force = force_n

    def disable_gripper(self) -> bool:
        with self._lock:
            if self.gripper_profile != "agx":
                return False
            self._gripper_enabled = False
            return True

    def stop(self) -> None:
        with self._lock:
            self._stopped = True


class PiperBackend:
    """Thin adapter around AgileX's official pyAgxArm SDK."""

    def __init__(
        self,
        model: str,
        firmware: str,
        interface: str,
        channel: str,
        bitrate: int = 1_000_000,
        gripper: str = "none",
    ):
        if model not in JOINT_LIMITS_RAD:
            raise ValueError(f"unsupported PIPER model: {model}")
        if firmware not in {"default", "v183", "v188", "v189"}:
            raise ValueError(f"unsupported firmware profile: {firmware}")
        if gripper not in {"none", "agx"}:
            raise ValueError(f"unsupported gripper profile: {gripper}")
        self.model = model
        self.firmware_profile = firmware
        self.gripper_profile = gripper
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self.joint_limits = JOINT_LIMITS_RAD[model]
        self._lock = threading.RLock()
        self._robot = None
        self._gripper = None
        self._firmware_info = None

    def connect(self) -> None:
        try:
            from pyAgxArm import AgxArmFactory, create_agx_arm_config
        except ImportError as exc:
            raise RuntimeError(
                "pyAgxArm is not installed; run setup_windows.ps1 first"
            ) from exc

        config = create_agx_arm_config(
            robot=self.model,
            firmeware_version=self.firmware_profile,
            interface=self.interface,
            channel=self.channel,
            bitrate=self.bitrate,
            enable_check_can=False,
            auto_connect=False,
        )
        robot = AgxArmFactory.create_arm(config)
        gripper = None
        if self.gripper_profile == "agx":
            gripper = robot.init_effector(robot.OPTIONS.EFFECTOR.AGX_GRIPPER)
        robot.connect()
        robot.set_joint_limits_enabled(True)
        self.joint_limits = [list(pair) for pair in config["joint_limits"].values()]
        self._robot = robot
        self._gripper = gripper

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if robot.get_joint_angles() is not None and robot.get_arm_status() is not None:
                break
            time.sleep(0.05)
        else:
            self.close()
            raise RuntimeError(
                "CAN opened but no PIPER feedback arrived within 5 seconds; "
                "check the official USB-CAN adapter, CAN_H/CAN_L, arm mode, and power"
            )

        try:
            self._firmware_info = robot.get_firmware(timeout=1.0)
        except Exception as exc:  # Firmware is useful metadata, not a safety gate.
            self._firmware_info = {"read_error": str(exc)}

    def _require_robot(self):
        if self._robot is None:
            raise RuntimeError("PIPER backend is not connected")
        return self._robot

    def _require_gripper(self):
        if self._gripper is None:
            raise RuntimeError("AGX gripper is not configured")
        return self._gripper

    def close(self) -> None:
        with self._lock:
            robot, self._robot = self._robot, None
            self._gripper = None
            if robot is not None:
                robot.disconnect()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            robot = self._require_robot()
            joint_msg = robot.get_joint_angles()
            status_msg = robot.get_arm_status()
            joint_angles = list(joint_msg.msg) if joint_msg is not None else None
            status = status_msg.msg if status_msg is not None else None
            enabled_list = list(robot.get_joints_enable_status_list())
            now = time.time()
            feedback_age = None
            if joint_msg is not None and joint_msg.timestamp:
                feedback_age = max(0.0, now - float(joint_msg.timestamp))

            if status is None:
                arm_status = {"code": None, "name": "NO_FEEDBACK"}
                motion_status = {"code": None, "name": "NO_FEEDBACK"}
                ctrl_mode = {"code": None, "name": "NO_FEEDBACK"}
                mode_feedback = {"code": None, "name": "NO_FEEDBACK"}
                teach_status = {"code": None, "name": "NO_FEEDBACK"}
                err_code = None
            else:
                arm_status = _enum_payload(status.arm_status)
                motion_status = _enum_payload(status.motion_status)
                ctrl_mode = _enum_payload(status.ctrl_mode)
                mode_feedback = _enum_payload(status.mode_feedback)
                teach_status = _enum_payload(status.teach_status)
                err_code = int(status.err_code)

            comm_error = robot.get_comm_error()
            connected = bool(robot.is_connected())
            return {
                "connected": connected,
                "healthy": bool(connected and robot.is_ok() and joint_angles is not None),
                "platform": platform.system(),
                "model": self.model,
                "firmware_profile": self.firmware_profile,
                "firmware": self._firmware_info,
                "joint_angles_rad": joint_angles,
                "joint_feedback_hz": (
                    float(joint_msg.hz) if joint_msg is not None else 0.0
                ),
                "feedback_age_s": feedback_age,
                "joints_enabled": enabled_list,
                "enabled": bool(enabled_list and all(enabled_list)),
                "arm_status": arm_status,
                "motion_status": motion_status,
                "ctrl_mode": ctrl_mode,
                "mode_feedback": mode_feedback,
                "teach_status": teach_status,
                "err_code": err_code,
                "comm_error": str(comm_error) if comm_error is not None else None,
                "gripper": _gripper_snapshot(self._gripper),
            }

    def enable(self, timeout_s: float = 5.0) -> bool:
        with self._lock:
            robot = self._require_robot()
            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                if robot.enable():
                    return True
                time.sleep(0.1)
            return False

    def enter_can_control(self, speed_percent: int, timeout_s: float = 2.0) -> bool:
        """Select low-speed MOVE J/CAN control without sending a joint target."""
        with self._lock:
            robot = self._require_robot()
            robot.set_speed_percent(speed_percent)
            robot.set_motion_mode(robot.OPTIONS.MOTION_MODE.J)
            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                status_msg = robot.get_arm_status()
                status = status_msg.msg if status_msg is not None else None
                if status is not None:
                    ctrl_mode = int(status.ctrl_mode)
                    teach_status = int(status.teach_status)
                    if ctrl_mode == 1 and teach_status in (0, 2):
                        return True
                time.sleep(0.05)
            return False

    def move_joints(self, target_rad: List[float], speed_percent: int) -> None:
        with self._lock:
            robot = self._require_robot()
            robot.set_speed_percent(speed_percent)
            robot.move_j(list(target_rad))

    def calibrate_gripper(self, timeout_s: float = 2.0) -> bool:
        with self._lock:
            return bool(self._require_gripper().calibrate_gripper(timeout=timeout_s))

    def move_gripper_width(self, target_m: float, force_n: float) -> None:
        with self._lock:
            self._require_gripper().move_gripper_m(value=target_m, force=force_n)

    def disable_gripper(self) -> bool:
        with self._lock:
            return bool(self._require_gripper().disable_gripper())

    def stop(self) -> None:
        with self._lock:
            self._require_robot().electronic_emergency_stop()


class BridgeController:
    """Local safety state machine.  It is the only caller of motion APIs."""

    TERMINAL_COMMAND_STATES = {"completed", "stopped", "fault", "timed_out", "error"}

    def __init__(
        self,
        backend,
        allow_motion: bool = False,
        permit_duration_s: Optional[float] = None,
        max_feedback_age_s: float = 0.5,
        max_joint_step_deg: float = 3.0,
        max_speed_percent: int = 5,
        expected_state_tolerance_deg: float = 1.0,
        target_tolerance_deg: float = 0.5,
        command_timeout_s: float = 10.0,
        expected_gripper_tolerance_m: float = 0.002,
        target_gripper_tolerance_m: float = 0.001,
        gripper_timeout_s: float = 5.0,
    ):
        self.backend = backend
        self.allow_motion = allow_motion
        if permit_duration_s is not None and permit_duration_s <= 0:
            raise ValueError("permit_duration_s must be positive or None")
        self.permit_duration_s = permit_duration_s
        self.max_feedback_age_s = max_feedback_age_s
        self.max_joint_step_rad = math.radians(max_joint_step_deg)
        self.max_speed_percent = max_speed_percent
        self.expected_state_tolerance_rad = math.radians(expected_state_tolerance_deg)
        self.target_tolerance_rad = math.radians(target_tolerance_deg)
        self.command_timeout_s = command_timeout_s
        self.expected_gripper_tolerance_m = expected_gripper_tolerance_m
        self.target_gripper_tolerance_m = target_gripper_tolerance_m
        self.gripper_timeout_s = gripper_timeout_s
        self._operator_permit_active = False
        self._operator_permit_until: Optional[float] = None
        self._state_lock = threading.RLock()
        self._command_lock = threading.Lock()
        self._commands: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._active_command_id: Optional[str] = None
        self._gripper_zero_confirmed_this_session = False
        self._closed = False

    def connect(self) -> None:
        self.backend.connect()

    def grant_operator_permit(self) -> Optional[float]:
        if not self.allow_motion:
            raise BridgeFault("observe_only", "bridge was started in observe-only mode", 403)
        with self._state_lock:
            self._operator_permit_active = True
            self._operator_permit_until = (
                None
                if self.permit_duration_s is None
                else time.monotonic() + self.permit_duration_s
            )
            return self.permit_duration_s

    def revoke_operator_permit(self) -> None:
        with self._state_lock:
            self._operator_permit_active = False
            self._operator_permit_until = None

    def _permit_remaining_s(self) -> Optional[float]:
        with self._state_lock:
            if not self._operator_permit_active:
                return 0.0
            if self._operator_permit_until is None:
                return None
            remaining = max(0.0, self._operator_permit_until - time.monotonic())
            if remaining == 0.0:
                self._operator_permit_active = False
                self._operator_permit_until = None
            return remaining

    def _has_operator_permit(self) -> bool:
        remaining = self._permit_remaining_s()
        return remaining is None or remaining > 0.0

    def _require_operator_permit(self) -> None:
        if not self.allow_motion:
            raise BridgeFault("observe_only", "bridge is observe-only; motion is disabled", 403)
        if not self._has_operator_permit():
            raise BridgeFault(
                "operator_permit_required",
                "type ARM WORKSPACE CLEAR in the local bridge console before "
                "preparing, enabling, or moving",
                403,
            )

    def _active_running(self) -> bool:
        with self._state_lock:
            if self._active_command_id is None:
                return False
            record = self._commands.get(self._active_command_id)
            return bool(record and record["status"] not in self.TERMINAL_COMMAND_STATES)

    def snapshot(self) -> Dict[str, Any]:
        hardware = self.backend.snapshot()
        permit_remaining_s = self._permit_remaining_s()
        with self._state_lock:
            active = None
            if self._active_command_id is not None:
                active = dict(self._commands[self._active_command_id])
        return {
            "bridge": {
                "version": BRIDGE_VERSION,
                "mode": "control" if self.allow_motion else "observe",
                "operator_permit": permit_remaining_s is None or permit_remaining_s > 0.0,
                "operator_permit_remaining_s": (
                    None if permit_remaining_s is None else round(permit_remaining_s, 3)
                ),
                "operator_permit_scope": (
                    "session"
                    if permit_remaining_s is None
                    else "timed"
                    if permit_remaining_s > 0.0
                    else "none"
                ),
                "max_joint_step_deg": round(math.degrees(self.max_joint_step_rad), 3),
                "max_speed_percent": self.max_speed_percent,
                "joint_limits_rad": [list(limits) for limits in self.backend.joint_limits],
                "gripper_width_limits_m": [
                    GRIPPER_MIN_WIDTH_M,
                    GRIPPER_MAX_WIDTH_M,
                ],
                "gripper_force_limits_n": [0.0, GRIPPER_MAX_FORCE_N],
                "gripper_zero_confirmed_this_session": (
                    self._gripper_zero_confirmed_this_session
                ),
                "active_command": active,
            },
            "arm": hardware,
        }

    def _require_base_feedback(self, snapshot: Dict[str, Any]) -> None:
        if not snapshot.get("connected"):
            raise BridgeFault("not_connected", "PIPER is not connected", 503)
        if not snapshot.get("healthy"):
            raise BridgeFault("unhealthy_feedback", "PIPER feedback is not healthy", 409)
        joints = snapshot.get("joint_angles_rad")
        if not isinstance(joints, list) or len(joints) != 6:
            raise BridgeFault("missing_joint_feedback", "six joint angles are required", 409)
        age = snapshot.get("feedback_age_s")
        if age is None or age > self.max_feedback_age_s:
            raise BridgeFault(
                "stale_feedback",
                f"joint feedback is older than {self.max_feedback_age_s:.3f}s",
                409,
            )
        arm_status = snapshot.get("arm_status", {}).get("code")
        if arm_status != 0:
            raise BridgeFault(
                "arm_not_normal",
                f"arm status must be NORMAL (0), got {arm_status}",
                409,
            )
        if snapshot.get("err_code") != 0:
            raise BridgeFault(
                "arm_error",
                f"arm err_code must be 0, got {snapshot.get('err_code')}",
                409,
            )
        if snapshot.get("comm_error"):
            raise BridgeFault("can_error", str(snapshot["comm_error"]), 409)

    def _require_safe_feedback(
        self,
        snapshot: Dict[str, Any],
        require_enabled: bool,
        require_can_control: bool = False,
    ) -> None:
        self._require_base_feedback(snapshot)
        ctrl_mode = snapshot.get("ctrl_mode", {}).get("code")
        allowed_ctrl_modes = (1,) if require_can_control else (0, 1)
        if ctrl_mode not in allowed_ctrl_modes:
            required = "CAN_CTRL (1)" if require_can_control else "STANDBY (0) or CAN_CTRL (1)"
            raise BridgeFault(
                "unsafe_control_mode",
                f"ctrl_mode must be {required}, got {ctrl_mode}",
                409,
            )
        teach_status = snapshot.get("teach_status", {}).get("code", 0)
        if teach_status not in (0, 2):
            raise BridgeFault(
                "teaching_active",
                "teach_status must be DISABLED (0) or STOP_RECORDING (2), "
                f"got {teach_status}",
                409,
            )
        if require_enabled and not snapshot.get("enabled"):
            raise BridgeFault("not_enabled", "all six joints must be enabled", 409)

    def _require_gripper_feedback(
        self, snapshot: Dict[str, Any], require_homed: bool
    ) -> Dict[str, Any]:
        gripper = snapshot.get("gripper")
        if not isinstance(gripper, dict) or not gripper.get("configured"):
            raise BridgeFault("gripper_not_configured", "AGX gripper is not configured", 409)
        if not gripper.get("feedback_present") or not gripper.get("driver_ok"):
            raise BridgeFault("gripper_no_feedback", "AGX gripper feedback is unavailable", 409)
        if gripper.get("read_error"):
            raise BridgeFault("gripper_read_error", str(gripper["read_error"]), 409)
        age = gripper.get("feedback_age_s")
        if age is None or age > self.max_feedback_age_s:
            raise BridgeFault(
                "stale_gripper_feedback",
                f"gripper feedback is older than {self.max_feedback_age_s:.3f}s",
                409,
            )
        faults = gripper.get("faults")
        if not isinstance(faults, dict) or any(value is not False for value in faults.values()):
            raise BridgeFault("gripper_fault", f"gripper faults are not clear: {faults}", 409)
        if gripper.get("mode") != "width" or gripper.get("unit") != "m":
            raise BridgeFault("gripper_mode", "gripper must report width mode in meters", 409)
        if (
            require_homed
            and not gripper.get("homed")
            and not self._gripper_zero_confirmed_this_session
        ):
            raise BridgeFault(
                "gripper_not_homed",
                "fully close the disabled gripper and calibrate it before moving",
                409,
            )
        return gripper

    def prepare(self) -> Dict[str, Any]:
        """Enter low-speed CAN/MOVE J control without sending a target."""
        self._require_operator_permit()
        if self._active_running():
            raise BridgeFault("command_busy", "a motion command is still active", 409)
        with self._command_lock:
            snapshot = self.backend.snapshot()
            self._require_base_feedback(snapshot)
            ctrl_mode = snapshot.get("ctrl_mode", {}).get("code")
            if ctrl_mode not in (0, 1, 2):
                raise BridgeFault(
                    "unsafe_control_mode",
                    "prepare requires STANDBY (0), CAN_CTRL (1), or "
                    f"TEACHING_MODE (2); got {ctrl_mode}",
                    409,
                )
            teach_status = snapshot.get("teach_status", {}).get("code", 0)
            if teach_status not in (0, 2):
                raise BridgeFault(
                    "teaching_active",
                    "prepare requires DISABLED (0) or STOP_RECORDING (2); "
                    f"got {teach_status}",
                    409,
                )
            try:
                confirmed = self.backend.enter_can_control(
                    speed_percent=self.max_speed_percent,
                    timeout_s=2.0,
                )
            except Exception as exc:
                raise BridgeFault("prepare_failed", str(exc), 502) from exc
            if not confirmed:
                raise BridgeFault(
                    "prepare_unconfirmed",
                    "PIPER feedback did not confirm CAN_CTRL (1) within 2 seconds",
                    502,
                )
            result = self.backend.snapshot()
            self._require_safe_feedback(
                result,
                require_enabled=False,
                require_can_control=True,
            )
            return result

    def enable(self) -> Dict[str, Any]:
        self._require_operator_permit()
        if self._active_running():
            raise BridgeFault("command_busy", "a motion command is still active", 409)
        with self._command_lock:
            snapshot = self.backend.snapshot()
            self._require_safe_feedback(snapshot, require_enabled=False)
            if not snapshot.get("enabled") and not self.backend.enable(timeout_s=5.0):
                raise BridgeFault("enable_failed", "not all joints enabled within 5 seconds", 502)
            result = self.backend.snapshot()
            if not result.get("enabled"):
                raise BridgeFault("enable_unconfirmed", "joint feedback did not confirm enable", 502)
            return result

    def calibrate_gripper(self, body: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(body, dict) or body.get("confirm_fully_closed") is not True:
            raise BridgeFault(
                "confirmation_required",
                "confirm_fully_closed must be true after manually closing the disabled gripper",
            )
        self._require_operator_permit()
        with self._command_lock:
            if self._active_running():
                raise BridgeFault("command_busy", "a motion command is still active", 409)
            snapshot = self.backend.snapshot()
            self._require_safe_feedback(
                snapshot,
                require_enabled=False,
                require_can_control=True,
            )
            gripper = self._require_gripper_feedback(snapshot, require_homed=False)
            if gripper.get("driver_enabled") is not False:
                raise BridgeFault(
                    "gripper_must_be_disabled",
                    "disable the gripper before manually closing and calibrating it",
                    409,
                )
            expected = _finite_float(
                body.get("expected_current_width_m"),
                "expected_current_width_m",
            )
            current = gripper.get("value")
            if not isinstance(current, (int, float)):
                raise BridgeFault("gripper_no_position", "gripper width is unavailable", 409)
            if abs(float(current) - expected) > self.expected_gripper_tolerance_m:
                raise BridgeFault(
                    "gripper_state_changed",
                    "gripper width changed since calibration was planned",
                    409,
                )
            try:
                acknowledged = self.backend.calibrate_gripper(timeout_s=2.0)
            except Exception as exc:
                raise BridgeFault("gripper_calibration_failed", str(exc), 502) from exc
            if not acknowledged:
                raise BridgeFault(
                    "gripper_calibration_unconfirmed",
                    "gripper did not acknowledge zero calibration",
                    502,
                )

            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                result = self.backend.snapshot()
                calibrated = self._require_gripper_feedback(result, require_homed=False)
                value = calibrated.get("value")
                if isinstance(value, (int, float)):
                    if abs(float(value)) <= self.target_gripper_tolerance_m:
                        self._gripper_zero_confirmed_this_session = True
                        return result
                time.sleep(0.05)
            raise BridgeFault(
                "gripper_calibration_unconfirmed",
                "gripper feedback did not confirm a zeroed, fully closed position",
                502,
            )

    def disable_gripper(self) -> Dict[str, Any]:
        self._require_operator_permit()
        with self._command_lock:
            if self._active_running():
                raise BridgeFault("command_busy", "a motion command is still active", 409)
            snapshot = self.backend.snapshot()
            self._require_base_feedback(snapshot)
            self._require_gripper_feedback(snapshot, require_homed=False)
            try:
                self.backend.disable_gripper()
            except Exception as exc:
                raise BridgeFault("gripper_disable_failed", str(exc), 502) from exc

            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                result = self.backend.snapshot()
                gripper = self._require_gripper_feedback(result, require_homed=False)
                if gripper.get("driver_enabled") is False:
                    return result
                time.sleep(0.05)
            raise BridgeFault(
                "gripper_disable_unconfirmed",
                "gripper feedback did not confirm driver disable",
                502,
            )

    def _validate_command_id(self, body: Dict[str, Any]) -> str:
        command_id = body.get("command_id")
        if not isinstance(command_id, str) or not (8 <= len(command_id) <= 128):
            raise BridgeFault("invalid_request", "command_id must be an 8-128 character string")
        if any(
            ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
            for ch in command_id
        ):
            raise BridgeFault("invalid_request", "command_id contains unsupported characters")
        return command_id

    def _validate_move(self, body: Dict[str, Any], snapshot: Dict[str, Any]):
        command_id = self._validate_command_id(body)

        target = _finite_float_list(body.get("target_rad"), "target_rad")
        expected = _finite_float_list(body.get("expected_current_rad"), "expected_current_rad")
        speed = body.get("speed_percent")
        if isinstance(speed, bool) or not isinstance(speed, int):
            raise BridgeFault("invalid_request", "speed_percent must be an integer")
        if not 1 <= speed <= self.max_speed_percent:
            raise BridgeFault(
                "speed_limit",
                f"speed_percent must be between 1 and {self.max_speed_percent}",
            )

        current = snapshot["joint_angles_rad"]
        for index, (actual, expected_value) in enumerate(zip(current, expected), start=1):
            if abs(actual - expected_value) > self.expected_state_tolerance_rad:
                raise BridgeFault(
                    "state_changed",
                    f"joint {index} changed since planning; read state and plan again",
                    409,
                )
        for index, (value, actual, limits) in enumerate(
            zip(target, current, self.backend.joint_limits), start=1
        ):
            if not limits[0] <= value <= limits[1]:
                raise BridgeFault(
                    "joint_limit",
                    f"joint {index} target {value:.6f} rad is outside {limits}",
                )
            delta = abs(value - actual)
            if delta > self.max_joint_step_rad:
                raise BridgeFault(
                    "step_limit",
                    f"joint {index} step {math.degrees(delta):.3f} deg exceeds "
                    f"{math.degrees(self.max_joint_step_rad):.3f} deg",
                )
        return command_id, target, expected, speed

    def submit_move(self, body: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(body, dict):
            raise BridgeFault("invalid_request", "JSON body must be an object")
        self._require_operator_permit()
        with self._command_lock:
            if self._active_running():
                raise BridgeFault("command_busy", "a motion command is still active", 409)
            snapshot = self.backend.snapshot()
            self._require_safe_feedback(
                snapshot,
                require_enabled=True,
                require_can_control=True,
            )
            command_id, target, expected, speed = self._validate_move(body, snapshot)
            with self._state_lock:
                if command_id in self._commands:
                    raise BridgeFault("duplicate_command", "command_id was already used", 409)
                record = {
                    "command_id": command_id,
                    "kind": "joint_move",
                    "status": "sending",
                    "target_rad": target,
                    "expected_current_rad": expected,
                    "speed_percent": speed,
                    "started_at_unix_s": time.time(),
                    "finished_at_unix_s": None,
                    "max_error_rad": None,
                    "detail": None,
                }
                self._commands[command_id] = record
                self._active_command_id = command_id
                while len(self._commands) > 128:
                    self._commands.popitem(last=False)
            try:
                self.backend.move_joints(target, speed)
            except Exception as exc:
                self._finish_command(command_id, "error", f"SDK move failed: {exc}")
                raise BridgeFault("move_failed", str(exc), 502) from exc
            with self._state_lock:
                self._commands[command_id]["status"] = "running"

        monitor = threading.Thread(
            target=self._monitor_move,
            args=(command_id, target),
            name=f"piper-command-{command_id[:12]}",
            daemon=True,
        )
        monitor.start()
        return self.command(command_id)

    def submit_gripper_move(self, body: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(body, dict):
            raise BridgeFault("invalid_request", "JSON body must be an object")
        self._require_operator_permit()
        with self._command_lock:
            if self._active_running():
                raise BridgeFault("command_busy", "a motion command is still active", 409)
            snapshot = self.backend.snapshot()
            self._require_safe_feedback(
                snapshot,
                require_enabled=False,
                require_can_control=True,
            )
            gripper = self._require_gripper_feedback(snapshot, require_homed=True)
            command_id = self._validate_command_id(body)
            target = _finite_float(body.get("target_width_m"), "target_width_m")
            expected = _finite_float(
                body.get("expected_current_width_m"),
                "expected_current_width_m",
            )
            force = _finite_float(body.get("force_n"), "force_n")
            if not GRIPPER_MIN_WIDTH_M <= target <= GRIPPER_MAX_WIDTH_M:
                raise BridgeFault(
                    "gripper_width_limit",
                    f"target_width_m must be between {GRIPPER_MIN_WIDTH_M} "
                    f"and {GRIPPER_MAX_WIDTH_M}",
                )
            if not 0.0 <= force <= GRIPPER_MAX_FORCE_N:
                raise BridgeFault(
                    "gripper_force_limit",
                    f"force_n must be between 0.0 and {GRIPPER_MAX_FORCE_N}",
                )
            current = gripper.get("value")
            if not isinstance(current, (int, float)):
                raise BridgeFault("gripper_no_position", "gripper width is unavailable", 409)
            if abs(float(current) - expected) > self.expected_gripper_tolerance_m:
                raise BridgeFault(
                    "gripper_state_changed",
                    "gripper width changed since planning; read state and plan again",
                    409,
                )
            with self._state_lock:
                if command_id in self._commands:
                    raise BridgeFault("duplicate_command", "command_id was already used", 409)
                record = {
                    "command_id": command_id,
                    "kind": "gripper_width",
                    "status": "sending",
                    "target_width_m": target,
                    "expected_current_width_m": expected,
                    "force_n": force,
                    "started_at_unix_s": time.time(),
                    "finished_at_unix_s": None,
                    "actual_width_m": float(current),
                    "max_error_m": abs(float(current) - target),
                    "detail": None,
                }
                self._commands[command_id] = record
                self._active_command_id = command_id
                while len(self._commands) > 128:
                    self._commands.popitem(last=False)
            try:
                self.backend.move_gripper_width(target, force)
            except Exception as exc:
                self._finish_command(command_id, "error", f"SDK gripper move failed: {exc}")
                raise BridgeFault("gripper_move_failed", str(exc), 502) from exc
            with self._state_lock:
                self._commands[command_id]["status"] = "running"

        monitor = threading.Thread(
            target=self._monitor_gripper_move,
            args=(command_id, target),
            name=f"piper-gripper-{command_id[:12]}",
            daemon=True,
        )
        monitor.start()
        return self.command(command_id)

    def _finish_command(self, command_id: str, status: str, detail: Optional[str]) -> None:
        with self._state_lock:
            record = self._commands.get(command_id)
            if record is None or record["status"] in self.TERMINAL_COMMAND_STATES:
                return
            record["status"] = status
            record["detail"] = detail
            record["finished_at_unix_s"] = time.time()

    def _monitor_move(self, command_id: str, target: List[float]) -> None:
        started = time.monotonic()
        while True:
            with self._state_lock:
                record = self._commands.get(command_id)
                if record is None or record["status"] in self.TERMINAL_COMMAND_STATES:
                    return
            try:
                snapshot = self.backend.snapshot()
                arm_status = snapshot.get("arm_status", {}).get("code")
                err_code = snapshot.get("err_code")
                ctrl_mode = snapshot.get("ctrl_mode", {}).get("code")
                teach_status = snapshot.get("teach_status", {}).get("code", 0)
                if (
                    arm_status != 0
                    or err_code != 0
                    or snapshot.get("comm_error")
                    or ctrl_mode != 1
                    or teach_status not in (0, 2)
                ):
                    self._safety_stop(
                        command_id,
                        "fault",
                        f"arm_status={arm_status}, err_code={err_code}, "
                        f"comm_error={snapshot.get('comm_error')}, "
                        f"ctrl_mode={ctrl_mode}, teach_status={teach_status}",
                    )
                    return
                joints = snapshot.get("joint_angles_rad")
                age = snapshot.get("feedback_age_s")
                if not isinstance(joints, list) or age is None or age > self.max_feedback_age_s:
                    raise RuntimeError("joint feedback became missing or stale")
                max_error = max(abs(a - b) for a, b in zip(joints, target))
                with self._state_lock:
                    self._commands[command_id]["max_error_rad"] = max_error
                if time.monotonic() - started >= 0.15 and max_error <= self.target_tolerance_rad:
                    self._finish_command(command_id, "completed", None)
                    return
            except Exception as exc:
                self._safety_stop(command_id, "fault", f"monitor failed: {exc}")
                return

            if time.monotonic() - started > self.command_timeout_s:
                self._safety_stop(
                    command_id,
                    "timed_out",
                    f"target not reached within {self.command_timeout_s:.1f}s",
                )
                return
            time.sleep(0.05)

    def _monitor_gripper_move(self, command_id: str, target_m: float) -> None:
        started = time.monotonic()
        while True:
            with self._state_lock:
                record = self._commands.get(command_id)
                if record is None or record["status"] in self.TERMINAL_COMMAND_STATES:
                    return
            try:
                snapshot = self.backend.snapshot()
                self._require_safe_feedback(
                    snapshot,
                    require_enabled=False,
                    require_can_control=True,
                )
                gripper = self._require_gripper_feedback(snapshot, require_homed=True)
                width = gripper.get("value")
                if not isinstance(width, (int, float)):
                    raise RuntimeError("gripper width feedback became unavailable")
                error = abs(float(width) - target_m)
                with self._state_lock:
                    self._commands[command_id]["actual_width_m"] = float(width)
                    self._commands[command_id]["max_error_m"] = error
                elapsed = time.monotonic() - started
                if elapsed >= 0.5 and not gripper.get("driver_enabled"):
                    raise RuntimeError("gripper driver did not enable")
                if (
                    elapsed >= 0.15
                    and gripper.get("driver_enabled")
                    and error <= self.target_gripper_tolerance_m
                ):
                    self._finish_command(command_id, "completed", None)
                    return
            except Exception as exc:
                self._gripper_safety_stop(command_id, "fault", f"monitor failed: {exc}")
                return

            if time.monotonic() - started > self.gripper_timeout_s:
                self._gripper_safety_stop(
                    command_id,
                    "timed_out",
                    f"target not reached within {self.gripper_timeout_s:.1f}s",
                )
                return
            time.sleep(0.05)

    def _safety_stop(self, command_id: str, status: str, detail: str) -> None:
        stop_error = None
        try:
            with self._command_lock:
                self.backend.stop()
        except Exception as exc:
            stop_error = str(exc)
        if stop_error:
            detail = f"{detail}; electronic stop also failed: {stop_error}"
        self._finish_command(command_id, status, detail)

    def _gripper_safety_stop(self, command_id: str, status: str, detail: str) -> None:
        disable_error = None
        try:
            with self._command_lock:
                self.backend.disable_gripper()
        except Exception as exc:
            disable_error = str(exc)
        if disable_error:
            detail = f"{detail}; gripper disable also failed: {disable_error}"
        self._finish_command(command_id, status, detail)

    def stop(self, reason: str = "requested") -> Dict[str, Any]:
        if not self.allow_motion:
            raise BridgeFault("observe_only", "stop is disabled in observe-only mode", 403)
        with self._state_lock:
            active = (
                self._commands.get(self._active_command_id)
                if self._active_command_id
                else None
            )
            active_kind = (
                active.get("kind")
                if active and active.get("status") not in self.TERMINAL_COMMAND_STATES
                else None
            )
        with self._command_lock:
            if active_kind == "gripper_width":
                self.backend.disable_gripper()
            else:
                self.backend.stop()
        with self._state_lock:
            if self._active_command_id is not None:
                self._finish_command(self._active_command_id, "stopped", reason)
        self.revoke_operator_permit()
        return self.backend.snapshot()

    def command(self, command_id: str) -> Dict[str, Any]:
        with self._state_lock:
            record = self._commands.get(command_id)
            if record is None:
                raise BridgeFault("command_not_found", "unknown command_id", 404)
            return dict(record)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._active_running() and self.allow_motion:
            try:
                self.stop(reason="bridge shutting down during active command")
            except Exception:
                pass
        self.backend.close()

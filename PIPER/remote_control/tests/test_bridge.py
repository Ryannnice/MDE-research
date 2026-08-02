import json
import math
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bridge_core import (
    BridgeController,
    BridgeFault,
    MockBackend,
    PiperBackend,
    _gripper_snapshot,
)
from piper_client import (
    MAX_SEQUENCE_WAYPOINT_STEP_DEG,
    ClientError,
    _gripper_width,
    _joint_waypoints,
    _validate_gripper_request,
    _validate_motion_request,
)
from piper_bridge import PiperHTTPServer


TOKEN = "test-token-0123456789abcdef-0123456789abcdef"


def wait_terminal(controller, command_id, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        command = controller.command(command_id)
        if command["status"] in controller.TERMINAL_COMMAND_STATES:
            return command
        time.sleep(0.01)
    raise AssertionError("command did not reach a terminal state")


class NonMovingBackend(MockBackend):
    def __init__(self):
        super().__init__()
        self.stop_calls = 0

    def move_joints(self, target_rad, speed_percent):
        del target_rad, speed_percent

    def stop(self):
        self.stop_calls += 1
        super().stop()


class NonMovingGripperBackend(MockBackend):
    def __init__(self):
        super().__init__(gripper="agx")
        self.disable_calls = 0

    def move_gripper_width(self, target_m, force_n):
        del target_m
        self._gripper_enabled = True
        self._gripper_force = force_n

    def disable_gripper(self):
        self.disable_calls += 1
        return super().disable_gripper()


class NoHomingBitBackend(MockBackend):
    def __init__(self):
        super().__init__(gripper="agx")
        self._gripper_enabled = False
        self._gripper_homed = False
        self._gripper_value = -0.0005

    def calibrate_gripper(self, timeout_s=2.0):
        del timeout_s
        self._gripper_value = 0.0
        return True

    def move_gripper_width(self, target_m, force_n):
        self._gripper_enabled = True
        self._gripper_value = target_m
        self._gripper_force = force_n


class TeachingModeBackend(MockBackend):
    def snapshot(self):
        state = super().snapshot()
        state["ctrl_mode"] = {"code": 2, "name": "TEACHING_MODE"}
        return state


class TransitioningTeachingBackend(MockBackend):
    def __init__(self, teach_status=2, confirm_transition=True):
        super().__init__()
        self.ctrl_mode = 2
        self.teach_status = teach_status
        self.confirm_transition = confirm_transition
        self.enter_can_control_calls = 0
        self.enter_can_control_speed = None

    def snapshot(self):
        state = super().snapshot()
        state["ctrl_mode"] = {
            "code": self.ctrl_mode,
            "name": "CAN_CTRL" if self.ctrl_mode == 1 else "TEACHING_MODE",
        }
        state["teach_status"] = {
            "code": self.teach_status,
            "name": "STOP_RECORDING" if self.teach_status == 2 else "START_RECORDING",
        }
        return state

    def enter_can_control(self, speed_percent, timeout_s=2.0):
        del timeout_s
        self.enter_can_control_calls += 1
        self.enter_can_control_speed = speed_percent
        if self.confirm_transition:
            self.ctrl_mode = 1
        return self.confirm_transition


class OffsetJointBackend(MockBackend):
    def __init__(self):
        super().__init__()
        self._joints[1] = -0.014
        self._joints[2] = 0.024


class ModeLossBackend(MockBackend):
    def __init__(self):
        super().__init__()
        self.ctrl_mode = 1
        self.stop_calls = 0

    def snapshot(self):
        state = super().snapshot()
        state["ctrl_mode"] = {
            "code": self.ctrl_mode,
            "name": "CAN_CTRL" if self.ctrl_mode == 1 else "TEACHING_MODE",
        }
        return state

    def move_joints(self, target_rad, speed_percent):
        super().move_joints(target_rad, speed_percent)
        self.ctrl_mode = 2

    def stop(self):
        self.stop_calls += 1
        super().stop()


class FakeGripper:
    def __init__(self, status=None, ok=True):
        self.status = status
        self.ok = ok
        self.calls = []

    def is_ok(self):
        return self.ok

    def get_gripper_status(self):
        return self.status

    def calibrate_gripper(self, timeout):
        self.calls.append(("calibrate", timeout))
        return True

    def move_gripper_m(self, value, force):
        self.calls.append(("move", value, force))

    def disable_gripper(self):
        self.calls.append(("disable",))
        return True


class GripperTelemetryTests(unittest.TestCase):
    def test_unconfigured_gripper_is_explicit(self):
        state = _gripper_snapshot(None)

        self.assertFalse(state["configured"])
        self.assertFalse(state["feedback_present"])
        self.assertFalse(state["healthy"])

    def test_agx_feedback_is_serialized_without_a_command(self):
        foc = SimpleNamespace(
            voltage_too_low=False,
            motor_overheating=False,
            driver_overcurrent=False,
            driver_overheating=False,
            sensor_status=False,
            driver_error_status=False,
            driver_enable_status=True,
            homing_status=True,
        )
        message = SimpleNamespace(
            msg=SimpleNamespace(
                value=0.064,
                force=0.25,
                mode="width",
                status_code=192,
                foc_status=foc,
            ),
            hz=100.0,
            timestamp=time.time(),
        )

        state = _gripper_snapshot(FakeGripper(message))

        self.assertTrue(state["configured"])
        self.assertTrue(state["feedback_present"])
        self.assertTrue(state["healthy"])
        self.assertEqual(state["unit"], "m")
        self.assertEqual(state["value"], 0.064)
        self.assertTrue(state["driver_enabled"])
        self.assertTrue(state["homed"])
        self.assertFalse(any(state["faults"].values()))

    def test_reported_fault_makes_gripper_unhealthy(self):
        foc = SimpleNamespace(
            voltage_too_low=True,
            motor_overheating=False,
            driver_overcurrent=False,
            driver_overheating=False,
            sensor_status=False,
            driver_error_status=False,
            driver_enable_status=True,
            homing_status=True,
        )
        message = SimpleNamespace(
            msg=SimpleNamespace(
                value=10.0,
                force=0.0,
                mode="angle",
                status_code=193,
                foc_status=foc,
            ),
            hz=100.0,
            timestamp=time.time(),
        )

        state = _gripper_snapshot(FakeGripper(message))

        self.assertFalse(state["healthy"])
        self.assertEqual(state["unit"], "deg")
        self.assertTrue(state["faults"]["voltage_too_low"])

    def test_piper_initializes_gripper_before_connecting_can(self):
        events = []
        fake_gripper = FakeGripper()

        class FakeRobot:
            OPTIONS = SimpleNamespace(
                EFFECTOR=SimpleNamespace(AGX_GRIPPER="agx_gripper")
            )

            def init_effector(self, profile):
                self.assert_profile = profile
                events.append("init_effector")
                return fake_gripper

            def connect(self):
                events.append("connect")

            def set_joint_limits_enabled(self, enabled):
                self.joint_limits_enabled = enabled

            def get_joint_angles(self):
                return SimpleNamespace(msg=[0.0] * 6)

            def get_arm_status(self):
                return SimpleNamespace(msg=object())

            def get_firmware(self, timeout):
                return {"software_version": "TEST", "timeout": timeout}

            def disconnect(self):
                events.append("disconnect")

        robot = FakeRobot()
        sdk = SimpleNamespace(
            AgxArmFactory=SimpleNamespace(create_arm=lambda config: robot),
            create_agx_arm_config=lambda **kwargs: {
                "joint_limits": {f"joint_{index}": [-1.0, 1.0] for index in range(6)},
                "options": kwargs,
            },
        )
        backend = PiperBackend(
            model="piper",
            firmware="v189",
            interface="agx_cando",
            channel="0",
            gripper="agx",
        )

        with patch.dict(sys.modules, {"pyAgxArm": sdk}):
            backend.connect()
            self.addCleanup(backend.close)

        self.assertEqual(events[:2], ["init_effector", "connect"])
        self.assertIs(backend._gripper, fake_gripper)
        self.assertTrue(robot.joint_limits_enabled)
        self.assertTrue(backend.calibrate_gripper(timeout_s=1.5))
        backend.move_gripper_width(0.01, 0.5)
        self.assertTrue(backend.disable_gripper())
        self.assertEqual(
            fake_gripper.calls,
            [("calibrate", 1.5), ("move", 0.01, 0.5), ("disable",)],
        )


class BridgeControllerTests(unittest.TestCase):
    def make_controller(self, allow_motion=True, backend=None, **kwargs):
        backend = backend or MockBackend()
        controller = BridgeController(backend, allow_motion=allow_motion, **kwargs)
        controller.connect()
        self.addCleanup(controller.close)
        return controller

    def arm_and_enable(self, controller):
        controller.grant_operator_permit()
        result = controller.enable()
        self.assertTrue(result["enabled"])

    def safe_body(self, controller, command_id="command-0001", delta_deg=1.0):
        current = controller.snapshot()["arm"]["joint_angles_rad"]
        target = list(current)
        target[5] += math.radians(delta_deg)
        return {
            "command_id": command_id,
            "target_rad": target,
            "expected_current_rad": current,
            "speed_percent": 5,
        }

    def test_observe_mode_rejects_enable_and_motion(self):
        controller = self.make_controller(allow_motion=False)
        with self.assertRaisesRegex(BridgeFault, "observe-only"):
            controller.enable()
        with self.assertRaisesRegex(BridgeFault, "observe-only"):
            controller.submit_move(self.safe_body(controller))

    def test_control_requires_local_operator_permit(self):
        controller = self.make_controller()
        with self.assertRaisesRegex(BridgeFault, "ARM WORKSPACE CLEAR"):
            controller.enable()

    def test_default_operator_permit_lasts_for_bridge_session(self):
        controller = self.make_controller()

        self.assertIsNone(controller.grant_operator_permit())
        time.sleep(0.01)
        state = controller.snapshot()["bridge"]
        self.assertTrue(state["operator_permit"])
        self.assertIsNone(state["operator_permit_remaining_s"])
        self.assertEqual(state["operator_permit_scope"], "session")

        controller.revoke_operator_permit()
        state = controller.snapshot()["bridge"]
        self.assertFalse(state["operator_permit"])
        self.assertEqual(state["operator_permit_scope"], "none")

    def test_optional_timed_operator_permit_expires(self):
        controller = self.make_controller(permit_duration_s=0.01)
        self.assertEqual(controller.grant_operator_permit(), 0.01)
        time.sleep(0.02)
        self.assertFalse(controller.snapshot()["bridge"]["operator_permit"])

    def test_teaching_mode_rejects_remote_control(self):
        controller = self.make_controller(backend=TeachingModeBackend())
        controller.grant_operator_permit()
        with self.assertRaisesRegex(BridgeFault, "STANDBY.*CAN_CTRL"):
            controller.enable()

    def test_prepare_requires_local_operator_permit(self):
        backend = TransitioningTeachingBackend()
        controller = self.make_controller(backend=backend)
        with self.assertRaisesRegex(BridgeFault, "ARM WORKSPACE CLEAR"):
            controller.prepare()
        self.assertEqual(backend.enter_can_control_calls, 0)

    def test_prepare_switches_stopped_teaching_to_can_without_motion(self):
        backend = TransitioningTeachingBackend()
        controller = self.make_controller(backend=backend)
        before = backend.snapshot()["joint_angles_rad"]
        controller.grant_operator_permit()

        result = controller.prepare()

        self.assertEqual(result["ctrl_mode"]["code"], 1)
        self.assertEqual(result["joint_angles_rad"], before)
        self.assertEqual(backend.enter_can_control_calls, 1)
        self.assertEqual(backend.enter_can_control_speed, 5)
        self.assertTrue(controller.enable()["enabled"])

    def test_prepare_rejects_active_teaching_recording(self):
        backend = TransitioningTeachingBackend(teach_status=1)
        controller = self.make_controller(backend=backend)
        controller.grant_operator_permit()
        with self.assertRaisesRegex(BridgeFault, "STOP_RECORDING"):
            controller.prepare()
        self.assertEqual(backend.enter_can_control_calls, 0)

    def test_prepare_requires_confirmed_can_control_feedback(self):
        backend = TransitioningTeachingBackend(confirm_transition=False)
        controller = self.make_controller(backend=backend)
        controller.grant_operator_permit()
        with self.assertRaisesRegex(BridgeFault, "CAN_CTRL"):
            controller.prepare()

    def test_safe_return_from_small_joint_limit_offsets(self):
        controller = self.make_controller(backend=OffsetJointBackend())
        self.arm_and_enable(controller)
        current = controller.snapshot()["arm"]["joint_angles_rad"]

        unsafe_target = list(current)
        unsafe_target[5] += math.radians(1.0)
        unsafe_body = {
            "command_id": "outside-limit",
            "target_rad": unsafe_target,
            "expected_current_rad": current,
            "speed_percent": 5,
        }
        with self.assertRaisesRegex(BridgeFault, "joint 2 target"):
            controller.submit_move(unsafe_body)

        safe_target = list(current)
        safe_target[1] = 0.0
        safe_target[2] = 0.0
        safe_body = {
            "command_id": "safe-return",
            "target_rad": safe_target,
            "expected_current_rad": current,
            "speed_percent": 5,
        }
        result = wait_terminal(
            controller,
            controller.submit_move(safe_body)["command_id"],
        )
        self.assertEqual(result["status"], "completed")

    def test_safe_move_completes(self):
        controller = self.make_controller()
        self.arm_and_enable(controller)
        submitted = controller.submit_move(self.safe_body(controller))
        result = wait_terminal(controller, submitted["command_id"])
        self.assertEqual(result["status"], "completed")
        self.assertLessEqual(result["max_error_rad"], math.radians(0.5))

    def test_step_limit_is_rejected(self):
        controller = self.make_controller()
        self.arm_and_enable(controller)
        with self.assertRaisesRegex(BridgeFault, "exceeds"):
            controller.submit_move(self.safe_body(controller, delta_deg=3.1))

    def test_changed_state_is_rejected(self):
        controller = self.make_controller()
        self.arm_and_enable(controller)
        body = self.safe_body(controller)
        body["expected_current_rad"][0] += math.radians(2.0)
        with self.assertRaisesRegex(BridgeFault, "changed since planning"):
            controller.submit_move(body)

    def test_duplicate_command_is_rejected(self):
        controller = self.make_controller()
        self.arm_and_enable(controller)
        body = self.safe_body(controller)
        result = wait_terminal(controller, controller.submit_move(body)["command_id"])
        self.assertEqual(result["status"], "completed")
        body = self.safe_body(controller)
        with self.assertRaisesRegex(BridgeFault, "already used"):
            controller.submit_move(body)

    def test_timeout_sends_electronic_stop(self):
        backend = NonMovingBackend()
        controller = self.make_controller(
            backend=backend,
            command_timeout_s=0.1,
            target_tolerance_deg=0.01,
        )
        self.arm_and_enable(controller)
        submitted = controller.submit_move(self.safe_body(controller))
        result = wait_terminal(controller, submitted["command_id"])
        self.assertEqual(result["status"], "timed_out")
        self.assertEqual(backend.stop_calls, 1)

    def test_losing_can_control_during_motion_sends_stop(self):
        backend = ModeLossBackend()
        controller = self.make_controller(backend=backend)
        self.arm_and_enable(controller)
        submitted = controller.submit_move(self.safe_body(controller))
        result = wait_terminal(controller, submitted["command_id"])
        self.assertEqual(result["status"], "fault")
        self.assertIn("ctrl_mode", result["detail"])
        self.assertEqual(backend.stop_calls, 1)


class GripperControllerTests(unittest.TestCase):
    def make_controller(self, backend=None, allow_motion=True, **kwargs):
        backend = backend or MockBackend(gripper="agx")
        controller = BridgeController(backend, allow_motion=allow_motion, **kwargs)
        controller.connect()
        self.addCleanup(controller.close)
        return controller, backend

    def move_body(self, controller, command_id="gripper-command-1"):
        current = controller.snapshot()["arm"]["gripper"]["value"]
        return {
            "command_id": command_id,
            "target_width_m": 0.05,
            "expected_current_width_m": current,
            "force_n": 0.5,
        }

    def test_observe_mode_rejects_all_gripper_changes(self):
        controller, backend = self.make_controller(allow_motion=False)
        backend._gripper_enabled = False
        with self.assertRaisesRegex(BridgeFault, "observe-only"):
            controller.calibrate_gripper(
                {
                    "confirm_fully_closed": True,
                    "expected_current_width_m": 0.07,
                }
            )
        with self.assertRaisesRegex(BridgeFault, "observe-only"):
            controller.disable_gripper()
        with self.assertRaisesRegex(BridgeFault, "observe-only"):
            controller.submit_gripper_move(self.move_body(controller))

    def test_gripper_move_requires_local_operator_permit(self):
        controller, _ = self.make_controller()
        with self.assertRaisesRegex(BridgeFault, "ARM WORKSPACE CLEAR"):
            controller.submit_gripper_move(self.move_body(controller))

    def test_unhomed_gripper_cannot_move(self):
        controller, backend = self.make_controller()
        backend._gripper_homed = False
        controller.grant_operator_permit()
        with self.assertRaisesRegex(BridgeFault, "calibrate"):
            controller.submit_gripper_move(self.move_body(controller))

    def test_calibration_requires_confirmation_and_disabled_driver(self):
        controller, backend = self.make_controller()
        controller.grant_operator_permit()
        with self.assertRaisesRegex(BridgeFault, "confirm_fully_closed"):
            controller.calibrate_gripper({})
        with self.assertRaisesRegex(BridgeFault, "disable"):
            controller.calibrate_gripper(
                {
                    "confirm_fully_closed": True,
                    "expected_current_width_m": 0.07,
                }
            )

        backend._gripper_enabled = False
        backend._gripper_homed = False
        backend._gripper_value = 0.0256
        with self.assertRaisesRegex(BridgeFault, "changed since calibration"):
            controller.calibrate_gripper(
                {
                    "confirm_fully_closed": True,
                    "expected_current_width_m": 0.01,
                }
            )
        result = controller.calibrate_gripper(
            {
                "confirm_fully_closed": True,
                "expected_current_width_m": 0.0256,
            }
        )
        self.assertTrue(result["gripper"]["homed"])
        self.assertEqual(result["gripper"]["value"], 0.0)

    def test_gripper_width_move_completes_and_enables_driver(self):
        controller, _ = self.make_controller()
        controller.grant_operator_permit()
        command = controller.submit_gripper_move(self.move_body(controller))

        result = wait_terminal(controller, command["command_id"])

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["kind"], "gripper_width")
        self.assertAlmostEqual(result["actual_width_m"], 0.05)
        self.assertTrue(controller.snapshot()["arm"]["gripper"]["driver_enabled"])

    def test_calibration_ack_and_zero_readback_latch_missing_homing_bit(self):
        controller, _ = self.make_controller(backend=NoHomingBitBackend())
        controller.grant_operator_permit()

        calibrated = controller.calibrate_gripper(
            {
                "confirm_fully_closed": True,
                "expected_current_width_m": -0.0005,
            }
        )

        self.assertFalse(calibrated["gripper"]["homed"])
        self.assertTrue(
            controller.snapshot()["bridge"]["gripper_zero_confirmed_this_session"]
        )
        command = controller.submit_gripper_move(self.move_body(controller))
        result = wait_terminal(controller, command["command_id"])
        self.assertEqual(result["status"], "completed")

    def test_gripper_rejects_stale_expected_width_and_limits(self):
        controller, _ = self.make_controller()
        controller.grant_operator_permit()
        stale = self.move_body(controller, "gripper-stale")
        stale["expected_current_width_m"] = 0.01
        with self.assertRaisesRegex(BridgeFault, "changed since planning"):
            controller.submit_gripper_move(stale)

        too_wide = self.move_body(controller, "gripper-too-wide")
        too_wide["target_width_m"] = 0.071
        with self.assertRaisesRegex(BridgeFault, "target_width_m"):
            controller.submit_gripper_move(too_wide)

        too_forceful = self.move_body(controller, "gripper-too-forceful")
        too_forceful["force_n"] = 3.1
        with self.assertRaisesRegex(BridgeFault, "force_n"):
            controller.submit_gripper_move(too_forceful)

    def test_gripper_timeout_disables_driver(self):
        backend = NonMovingGripperBackend()
        controller, _ = self.make_controller(
            backend=backend,
            gripper_timeout_s=0.1,
        )
        controller.grant_operator_permit()
        command = controller.submit_gripper_move(self.move_body(controller))

        result = wait_terminal(controller, command["command_id"])

        self.assertEqual(result["status"], "timed_out")
        self.assertEqual(backend.disable_calls, 1)
        self.assertFalse(controller.snapshot()["arm"]["gripper"]["driver_enabled"])


class ClientTrajectoryTests(unittest.TestCase):
    def test_large_joint_move_is_split_into_bounded_waypoints(self):
        start = [0.0] * 6
        target = [0.0, math.radians(60), math.radians(-123), 0.0, 0.0, 0.0]

        waypoints = _joint_waypoints(start, target)

        self.assertEqual(waypoints[-1], target)
        previous = start
        for waypoint in waypoints:
            max_step = max(abs(b - a) for a, b in zip(previous, waypoint))
            self.assertLessEqual(
                max_step,
                math.radians(MAX_SEQUENCE_WAYPOINT_STEP_DEG) + 1e-12,
            )
            previous = waypoint

    def test_waypoint_generation_rejects_non_finite_targets(self):
        with self.assertRaisesRegex(ClientError, "finite"):
            _joint_waypoints([0.0] * 6, [0.0, 0.0, math.nan, 0.0, 0.0, 0.0])

    def test_client_preflights_full_target_against_bridge_limits(self):
        controller = BridgeController(MockBackend(), allow_motion=False)
        controller.connect()
        self.addCleanup(controller.close)
        state = controller.snapshot()

        self.assertEqual(_validate_motion_request(state, [0.0] * 6, 5), 5)
        target = [0.0] * 6
        target[1] = math.radians(-1.0)
        with self.assertRaisesRegex(ClientError, "joint 2 target"):
            _validate_motion_request(state, target, 5)

    def test_client_uses_bridge_configured_speed_limit(self):
        controller = BridgeController(
            MockBackend(), allow_motion=False, max_speed_percent=25
        )
        controller.connect()
        self.addCleanup(controller.close)
        state = controller.snapshot()

        self.assertEqual(_validate_motion_request(state, [0.0] * 6, 25), 25)
        with self.assertRaisesRegex(ClientError, "between 1 and 25"):
            _validate_motion_request(state, [0.0] * 6, 26)

    def test_client_validates_gripper_feedback_and_limits(self):
        controller = BridgeController(MockBackend(gripper="agx"), allow_motion=False)
        controller.connect()
        self.addCleanup(controller.close)
        state = controller.snapshot()

        self.assertEqual(_gripper_width(state), 0.07)
        _validate_gripper_request(state, 0.035, 0.5)
        with self.assertRaisesRegex(ClientError, "width"):
            _validate_gripper_request(state, 0.071, 0.5)
        with self.assertRaisesRegex(ClientError, "force"):
            _validate_gripper_request(state, 0.035, 3.1)


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.controller = BridgeController(MockBackend(), allow_motion=False)
        self.controller.connect()
        self.server = PiperHTTPServer(("127.0.0.1", 0), self.controller, TOKEN)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.controller.close()
        self.thread.join(timeout=1.0)

    def request(self, path, token=None, method="GET", body=None):
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        with urlopen(request, timeout=2.0) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_health_does_not_require_token(self):
        status, payload = self.request("/v1/health")
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])

    def test_state_requires_token(self):
        with self.assertRaises(HTTPError) as raised:
            self.request("/v1/state")
        self.assertEqual(raised.exception.code, 401)
        status, payload = self.request("/v1/state", TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"]["bridge"]["mode"], "observe")

    def test_prepare_endpoint_is_disabled_in_observe_mode(self):
        with self.assertRaises(HTTPError) as raised:
            self.request("/v1/prepare", TOKEN, method="POST", body={})
        self.assertEqual(raised.exception.code, 403)

    def test_gripper_motion_endpoint_is_disabled_in_observe_mode(self):
        with self.assertRaises(HTTPError) as raised:
            self.request(
                "/v1/gripper/move-width",
                TOKEN,
                method="POST",
                body={},
            )
        self.assertEqual(raised.exception.code, 403)


if __name__ == "__main__":
    unittest.main()

"""Native payment owner/lifecycle admission; synthetic identities, no browser."""

import contextvars
import json
import unittest
from unittest.mock import patch
from gateway.session_context import set_session_vars, clear_session_vars
from hermes_constants import get_hermes_home, profile_name_for_home
from secure_entry.service import Service
from secure_entry.payment import LocalPayment
from secure_entry.native import owner
from tools import browser_tool


class PaymentAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tokens = set_session_vars(
            platform="photon",
            chat_type="dm",
            chat_id="synthetic-chat",
            user_id="synthetic-owner",
            session_key="synthetic-key",
            session_id="synthetic-session",
            profile=profile_name_for_home(get_hermes_home()) or "",
            cron_session="",
        )
        self.addCleanup(clear_session_vars, self.tokens)
        self.service = Service(
            "https://example.invalid", str(get_hermes_home()), port=0
        )
        self.addCleanup(self.service.close)
        self.facility = LocalPayment(
            self.service,
            ["synthetic-cli"],
            retrieve=lambda *a: self.fail("must not retrieve"),
        )
        self.args = {
            "parent": "synthetic-target",
            "frame": "synthetic-frame",
            "merchant_origin": "https://merchant.test",
            "frame_origin": "https://provider.test",
            "spend_request_id": "lsrq_synthetic",
        }
        self.key = browser_tool._last_session_key("synthetic-payment")

    def test_existing_public_capture_needs_no_legacy_local_metadata(self):
        from types import SimpleNamespace

        with (
            patch.dict(browser_tool._active_sessions, {}, clear=True),
            patch(
                "tools.browser_supervisor.SUPERVISOR_REGISTRY.capture",
                return_value=SimpleNamespace(is_valid=lambda: True),
            ) as capture,
            patch(
                "secure_entry.payment.Target",
                side_effect=ValueError("stop before consent"),
            ) as target,
        ):
            result = json.loads(
                self.facility.fill(self.args, task_id="synthetic-payment")
            )
        capture.assert_called_once_with("synthetic-payment")
        target.assert_called_once()
        self.assertFalse(result["success"])

    def test_lifecycle_during_owner_acquisition_prevents_capture(self):
        def acquire(home):
            bound = owner(home)
            self.service.stopped(session_id="synthetic-session")
            return bound

        with (
            patch("secure_entry.payment.owner", side_effect=acquire),
            patch.dict(
                browser_tool._active_sessions, {self.key: {"features": {"local": True}}}
            ),
            patch("tools.browser_supervisor.SUPERVISOR_REGISTRY.capture") as capture,
        ):
            result = json.loads(
                self.facility.fill(self.args, task_id="synthetic-payment")
            )
        capture.assert_not_called()
        self.assertFalse(result["success"])

    def test_active_native_takeover_prevents_capture_without_metadata(self):
        from tools.bot_desktop import lease

        lease.acquire("synthetic-viewer")
        self.addCleanup(lease.release, "synthetic-viewer")
        with patch("tools.browser_supervisor.SUPERVISOR_REGISTRY.capture") as capture:
            result = json.loads(
                self.facility.fill(self.args, task_id="synthetic-payment")
            )
        capture.assert_not_called()
        self.assertFalse(result["success"])

    def test_native_takeover_during_capture_prevents_target(self):
        from tools.bot_desktop import lease
        from types import SimpleNamespace

        self.addCleanup(lease.release, "synthetic-viewer")

        def acquire(task):
            lease.acquire("synthetic-viewer")
            return SimpleNamespace(is_valid=lambda: True)

        with (
            patch(
                "tools.browser_supervisor.SUPERVISOR_REGISTRY.capture",
                side_effect=acquire,
            ),
            patch("secure_entry.payment.Target") as target,
        ):
            result = json.loads(
                self.facility.fill(self.args, task_id="synthetic-payment")
            )
        target.assert_not_called()
        self.assertFalse(result["success"])

    def test_takeover_then_handback_during_capture_still_invalidates_operation(self):
        from tools.bot_desktop import lease
        from types import SimpleNamespace

        self.addCleanup(lease.release, "synthetic-viewer")

        def acquire(task):
            lease.acquire("synthetic-viewer")
            lease.release("synthetic-viewer")
            return SimpleNamespace(is_valid=lambda: True)

        with (
            patch(
                "tools.browser_supervisor.SUPERVISOR_REGISTRY.capture",
                side_effect=acquire,
            ),
            patch("secure_entry.payment.Target") as target,
        ):
            result = json.loads(
                self.facility.fill(self.args, task_id="synthetic-payment")
            )
        target.assert_not_called()
        self.assertFalse(result["success"])

    def test_invalidated_capture_refuses_before_target(self):
        from types import SimpleNamespace

        with (
            patch(
                "tools.browser_supervisor.SUPERVISOR_REGISTRY.capture",
                return_value=SimpleNamespace(is_valid=lambda: False),
            ),
            patch("secure_entry.payment.Target") as target,
        ):
            result = json.loads(
                self.facility.fill(self.args, task_id="synthetic-payment")
            )
        target.assert_not_called()
        self.assertFalse(result["success"])

    def test_concurrent_stop_while_capture_pending_refuses_before_target(self):
        import threading
        from types import SimpleNamespace

        entered, resume = threading.Event(), threading.Event()
        results = []
        context = contextvars.copy_context()

        def acquire(task):
            entered.set()
            if not resume.wait(5):
                raise TimeoutError("test capture barrier")
            return SimpleNamespace(is_valid=lambda: True)

        with (
            patch(
                "tools.browser_supervisor.SUPERVISOR_REGISTRY.capture",
                side_effect=acquire,
            ),
            patch("secure_entry.payment.Target") as target,
        ):
            worker = threading.Thread(
                target=lambda: results.append(
                    context.run(
                        self.facility.fill, self.args, task_id="synthetic-payment"
                    )
                )
            )
            worker.start()
            try:
                self.assertTrue(entered.wait(5))
                self.service.stopped(session_id="synthetic-session")
            finally:
                resume.set()
                worker.join(5)
            self.assertFalse(worker.is_alive())
        target.assert_not_called()
        self.assertFalse(json.loads(results[0])["success"])

    def test_absent_capture_never_resolves_endpoint_or_starts_browser(self):
        from tools.browser_supervisor_capture import CapturedCDPInvalid

        with (
            patch(
                "tools.browser_supervisor.SUPERVISOR_REGISTRY.capture",
                side_effect=CapturedCDPInvalid("no synthetic route"),
            ),
            patch("tools.browser_supervisor.SUPERVISOR_REGISTRY.get_or_start") as start,
            patch("tools.browser_use_cli._resolve_backend_cdp") as resolve,
            patch("secure_entry.payment.Target") as target,
        ):
            result = json.loads(
                self.facility.fill(self.args, task_id="synthetic-payment")
            )
        start.assert_not_called()
        resolve.assert_not_called()
        target.assert_not_called()
        self.assertFalse(result["success"])

    def test_missing_task_local_identity_rejected_before_capture(self):
        with patch("tools.browser_supervisor.SUPERVISOR_REGISTRY.capture") as capture:
            result = contextvars.Context().run(
                self.facility.fill, self.args, task_id="synthetic-payment"
            )
        capture.assert_not_called()
        self.assertFalse(json.loads(result)["success"])


if __name__ == "__main__":
    unittest.main()

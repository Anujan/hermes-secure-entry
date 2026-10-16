import threading
import unittest
from secure_entry.payment_browser import Target


class AcquisitionTests(unittest.TestCase):
    def test_late_attachment_reply_is_detached_on_original_capture(self):
        release, detached = threading.Event(), threading.Event()

        class Capture:
            def call(self, method, params, **kwargs):
                if method == "Target.attachToTarget":
                    release.wait(2)
                    return {"result": {"sessionId": "synthetic-late-session"}}
                if method == "Target.detachFromTarget":
                    assert params == {"sessionId": "synthetic-late-session"}
                    detached.set()
                    return {"result": {}}
                raise AssertionError("unexpected command")

        target = object.__new__(Target)
        target.capture = Capture()
        target.guard = lambda: None
        target.closed = False
        try:
            with self.assertRaises(TimeoutError):
                target.attach_frame("synthetic-frame", timeout=0.01)
        finally:
            release.set()
        self.assertTrue(detached.wait(2))


if __name__ == "__main__":
    unittest.main()

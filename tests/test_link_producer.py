"""Exercise the actual subprocess producer adapter, no Link API or wallet."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from secure_entry import payment


class LinkProducerTests(unittest.TestCase):
    def test_retrieve_exact_approved_id_argv_private_file_without_stdout(self):
        with tempfile.TemporaryDirectory() as root:
            script = Path(root) / "synthetic_cli.py"
            script.write_text(
                'import json,sys,pathlib\na=sys.argv[1:]\nassert a[:3]==["spend-request","retrieve","lsrq_synthetic"]\nassert a[3:5]==["--include","card"]\nassert a[-2:]==["--format","json"]\npathlib.Path(a[6]).write_text("synthetic-private-data")\nprint(json.dumps({"id":"lsrq_synthetic","status":"approved"}))\n'
            )
            output = Path(root) / "card.json"
            self.assertIsNone(
                payment.retrieve_card(
                    [sys.executable, str(script)], "lsrq_synthetic", output
                )
            )
            self.assertEqual(output.read_text(), "synthetic-private-data")

    def test_nonapproved_or_mismatched_request_never_accepted(self):
        for data in (
            {"id": "lsrq_synthetic", "status": "pending_approval"},
            {"id": "lsrq_other", "status": "approved"},
            {"status": "approved"},
            [],
        ):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as root:
                output = Path(root) / "card.json"
                with self.assertRaises(ValueError):
                    payment.retrieve_card(
                        [sys.executable, "-c", "print(" + repr(json.dumps(data)) + ")"],
                        "lsrq_synthetic",
                        output,
                    )


if __name__ == "__main__":
    unittest.main()

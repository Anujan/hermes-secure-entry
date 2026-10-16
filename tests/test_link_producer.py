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

    def test_fixed_producer_diagnostics_never_include_process_output(self):
        cases = [
            (
                'import sys; print("SYNTHETIC_PRIVATE"); sys.exit(7)',
                "subprocess_exit",
                7,
            ),
            ('print("SYNTHETIC_PRIVATE")', "output_json_invalid", None),
            ('print("[]")', "output_envelope_mismatch", None),
            (
                'print(\'{"id":"lsrq_other","status":"approved"}\')',
                "output_id_mismatch",
                None,
            ),
            (
                'print(\'{"id":"lsrq_synthetic","status":"pending"}\')',
                "output_status_mismatch",
                None,
            ),
            ('print("x" * 65537)', "output_too_large", None),
        ]
        for script, reason, exit_status in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError) as caught:
                    payment.retrieve_card(
                        [sys.executable, "-c", script],
                        "lsrq_synthetic",
                        Path(root) / "card",
                    )
                self.assertEqual(getattr(caught.exception, "category", None), reason)
                self.assertEqual(
                    getattr(caught.exception, "exit_status", None), exit_status
                )
                self.assertEqual(str(caught.exception), "link_retrieval_refused")
                self.assertNotIn("SYNTHETIC_PRIVATE", repr(caught.exception))

    def test_singleton_approved_list_from_cli_0274_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "card.json"
            self.assertIsNone(
                payment.retrieve_card(
                    [
                        sys.executable,
                        "-c",
                        'print(\'[{"id":"lsrq_synthetic","status":"approved"}]\')',
                    ],
                    "lsrq_synthetic",
                    output,
                )
            )

    def test_cli_0274_schema_subprocess_to_private_consumer(self):
        from secure_entry.payment_file import PrivateCard

        # applyOutputFile in installed 0.27.4 dist/cli.js writes an object,
        # removes card from stdout, then yields metadata (a singleton array).
        artifact = {
            "spend_request_id": "lsrq_synthetic",
            "merchant_name": "Synthetic Merchant",
            "merchant_url": "https://merchant.invalid/checkout",
            "context": "Synthetic schema fixture only",
            "created_at": 1800000000,
            "card": {
                "number": "4242424242424242",
                "cvc": "123",
                "exp_month": 12,
                "exp_year": 2030,
                "billing_address": {
                    "name": "Synthetic Person",
                    "line1": "1 Test St",
                    "country": "US",
                },
            },
        }
        with tempfile.TemporaryDirectory() as root:
            script = Path(root) / "synthetic_cli.py"
            script.write_text(
                "import json,sys,pathlib\na=sys.argv[1:]\n"
                'assert a[:3]==["spend-request","retrieve","lsrq_synthetic"]\n'
                'assert a[3:5]==["--include","card"]\n'
                'assert a[5]=="--output-file"\n'
                'assert a[-2:]==["--format","json"]\n'
                f"artifact={artifact!r}\n"
                "pathlib.Path(a[6]).write_text(json.dumps(artifact))\n"
                'print(json.dumps([{"id":artifact["spend_request_id"],'
                '"status":"approved","card_output_file":a[6]}]))\n'
            )
            with PrivateCard(root) as inbox:
                self.assertIsNone(
                    payment.retrieve_card(
                        [sys.executable, str(script)], "lsrq_synthetic", inbox.path
                    )
                )
                self.assertEqual(
                    inbox.consume("lsrq_synthetic", "https://merchant.invalid"),
                    artifact["card"],
                )
                self.assertFalse(inbox.path.exists())

    def test_nonapproved_or_mismatched_request_never_accepted(self):
        for data in (
            {"id": "lsrq_synthetic", "status": "pending_approval"},
            {"id": "lsrq_other", "status": "approved"},
            {"status": "approved"},
            [],
            [{"id": "lsrq_synthetic", "status": "approved"}] * 2,
            [
                {"id": "lsrq_synthetic", "status": "approved"},
                {"id": "lsrq_other", "status": "approved"},
            ],
            [{"id": "lsrq_synthetic", "status": "pending_approval"}],
            [{"id": "lsrq_other", "status": "approved"}],
            [{"status": "approved"}],
            [None],
            [False],
            [1],
            ["approved"],
            [[{"id": "lsrq_synthetic", "status": "approved"}]],
            None,
            "approved",
        ):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as root:
                output = Path(root) / "card.json"
                with self.assertRaisesRegex(ValueError, "^link_retrieval_refused$"):
                    payment.retrieve_card(
                        [sys.executable, "-c", "print(" + repr(json.dumps(data)) + ")"],
                        "lsrq_synthetic",
                        output,
                    )


if __name__ == "__main__":
    unittest.main()

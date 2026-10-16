"""Only synthetic credentials; Windows kernel ACL and handle tests."""

import json
import tempfile
import unittest
from pathlib import Path
from secure_entry import payment_file

CARD = {
    "spend_request_id": "lsrq_synthetic",
    "merchant_url": "https://merchant.invalid",
    "card": {
        "number": "4242424242424242",
        "cvc": "123",
        "exp_month": 12,
        "exp_year": 2030,
    },
}


class PaymentFileTests(unittest.TestCase):
    def test_issued_billing_and_optional_cvc_preserved(self):
        data = json.loads(json.dumps(CARD))
        del data["card"]["cvc"]
        data["card"]["billing_address"] = dict(
            name="Synthetic Person", line1="1 Test St", country="US"
        )
        with (
            tempfile.TemporaryDirectory() as root,
            payment_file.PrivateCard(root) as inbox,
        ):
            inbox.path.write_text(json.dumps(data))
            self.assertEqual(
                inbox.consume("lsrq_synthetic", "https://merchant.invalid"),
                data["card"],
            )

    def test_world_readable_acl_rejected_and_file_deleted(self):
        import win32security as sec

        with tempfile.TemporaryDirectory() as root:
            with payment_file.PrivateCard(root) as inbox:
                inbox.path.write_text(json.dumps(CARD))
                sd = sec.GetFileSecurity(str(inbox.path), sec.DACL_SECURITY_INFORMATION)
                acl = sd.GetSecurityDescriptorDacl()
                acl.AddAccessAllowedAce(
                    sec.ACL_REVISION, 0x120089, sec.ConvertStringSidToSid("S-1-1-0")
                )
                sd.SetSecurityDescriptorDacl(True, acl, False)
                sec.SetFileSecurity(str(inbox.path), sec.DACL_SECURITY_INFORMATION, sd)
                with self.assertRaisesRegex(ValueError, "^private_file_refused$"):
                    inbox.consume("lsrq_synthetic", "https://merchant.invalid")
                self.assertFalse(inbox.path.exists())

    def test_hardlink_refused(self):
        import os

        with tempfile.TemporaryDirectory() as root:
            with payment_file.PrivateCard(root) as inbox:
                inbox.path.write_text(json.dumps(CARD))
                os.link(inbox.path, Path(root) / "other-link.json")
                with self.assertRaisesRegex(ValueError, "^private_file_refused$"):
                    inbox.consume("lsrq_synthetic", "https://merchant.invalid")
                self.assertFalse(inbox.path.exists())

    def test_wrong_merchant_id_malformed_and_oversized_are_secret_free(self):
        for raw, rid, origin in (
            (json.dumps(CARD), "lsrq_other", "https://merchant.invalid"),
            (json.dumps(CARD), "lsrq_synthetic", "https://other.invalid"),
            ("secret-invalid-json", "lsrq_synthetic", "https://merchant.invalid"),
            ("x" * 16385, "lsrq_synthetic", "https://merchant.invalid"),
        ):
            with (
                self.subTest(rid=rid, origin=origin),
                tempfile.TemporaryDirectory() as root,
            ):
                with payment_file.PrivateCard(root) as inbox:
                    inbox.path.write_text(raw)
                    with self.assertRaisesRegex(ValueError, "^private_file_refused$"):
                        inbox.consume(rid, origin)
                    self.assertFalse(inbox.path.exists())

    def test_private_directory_and_one_use_handle_cleanup(self):
        with tempfile.TemporaryDirectory() as root:
            with payment_file.PrivateCard(root) as inbox:
                p = inbox.path
                p.write_text(json.dumps(CARD), encoding="utf-8")
                self.assertEqual(
                    inbox.consume("lsrq_synthetic", "https://merchant.invalid")[
                        "number"
                    ],
                    CARD["card"]["number"],
                )
                self.assertFalse(p.exists())
                with self.assertRaises(ValueError):
                    inbox.consume("lsrq_synthetic", "https://merchant.invalid")
            self.assertFalse(p.parent.exists())


if __name__ == "__main__":
    unittest.main()

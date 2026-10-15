import tempfile
import unittest
from pathlib import Path


class InstallTests(unittest.TestCase):
    def test_stages_only_plugin_source_and_refuses_overwrite(self):
        from secure_entry.install import stage
        with tempfile.TemporaryDirectory() as home:
            target = stage(Path(__file__).resolve().parents[1], Path(home))
            self.assertTrue((target/'plugin.yaml').is_file())
            self.assertTrue((target/'secure_entry'/'broker.py').is_file())
            self.assertFalse((target/'.git').exists())
            self.assertFalse((target/'tests').exists())
            with self.assertRaises(FileExistsError): stage(Path(__file__).resolve().parents[1], Path(home))

import tempfile
import unittest
from pathlib import Path

from codex.tools import Workspace, write_file, edit_file, glob_files, grep, list_dir

class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_edit_read_search(self):
        write_file(self.ws, "src/a.py", "hello world\nhello codex\n")
        edit_file(self.ws, "src/a.py", "hello world", "hello tater")
        self.assertEqual(grep(self.ws, "tater"), "src/a.py:1:hello tater")
        self.assertIn("src/a.py", glob_files(self.ws, "**/*.py"))
        self.assertIn("src", list_dir(self.ws, "."))

if __name__ == "__main__":
    unittest.main()

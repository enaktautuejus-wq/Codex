import io
import unittest
from unittest.mock import patch
from codex.ui import mask_key, _read_masked

class UITests(unittest.TestCase):
    def test_mask_key(self):
        self.assertEqual(mask_key("12345678"), "********")
        self.assertEqual(mask_key("1234567890"), "1234**7890")

    def test_masked_reader_non_tty_fallback(self):
        fake_stdin = io.StringIO("secret-value\n")
        fake_stdout = io.StringIO()
        with patch("sys.stdin", fake_stdin), patch("sys.stdout", fake_stdout):
            self.assertEqual(_read_masked("api: "), "secret-value")
        self.assertIn("api: ", fake_stdout.getvalue())

if __name__ == "__main__":
    unittest.main()

import os
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


def test_workspace_path():
    from tempfile import TemporaryDirectory
    from codex.tools import Workspace, ToolError
    with TemporaryDirectory() as d:
        ws = Workspace(d)
        assert ws.path("a.txt").parent == ws.root
        try:
            ws.path("../outside.txt")
        except ToolError:
            pass
        else:
            raise AssertionError("workspace escape was not blocked")

class WorkspacePathTest(unittest.TestCase):
    def test_workspace_is_absolute(self):
        from codex.tools import Workspace
        with tempfile.TemporaryDirectory() as td:
            self.assertTrue(os.path.isabs(Workspace(td).root))

class AgentProtocolTest(unittest.TestCase):
    def test_tool_call_parser(self):
        from codex.agent import Agent
        self.assertEqual(Agent._parse_tool_call('{"tool":"list","args":{"path":"."}}')["tool"], "list")
        self.assertIsNone(Agent._parse_tool_call('{"answer":"ok"}'))

    def test_destructive_detection(self):
        from codex.agent import Agent
        self.assertTrue(Agent._looks_destructive("rm -rf build"))
        self.assertTrue(Agent._looks_destructive("git reset --hard HEAD"))
        self.assertFalse(Agent._looks_destructive("python -m unittest"))

    def test_native_schema(self):
        from codex.agent import Agent
        class DummyRegistry:
            def specs(self):
                return [{
                    "name": "read",
                    "description": "Read a file",
                    "parameters": {"path": "string", "start_line": "integer|null"},
                }]
        from codex.config import Config
        agent = Agent(Config("https://example.com/v1", "x", "model", os.getcwd()), DummyRegistry())
        tools = agent._native_tool_specs()
        fn = tools[0]["function"]
        self.assertEqual(fn["name"], "read")
        self.assertEqual(fn["parameters"]["type"], "object")
        self.assertIn("path", fn["parameters"]["required"])

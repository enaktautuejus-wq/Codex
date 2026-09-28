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

class TestRenderer(unittest.TestCase):
    def test_separates_and_highlights_fenced_code(self):
        from codex.renderer import render_markdown
        out = render_markdown("Penjelasan\n\n```python\ndef hello():\n    return 42\n```\n\nSelesai.")
        self.assertIn("Penjelasan", out)
        self.assertIn("python", out)
        self.assertIn("def", out)
        self.assertIn("Selesai.", out)
        self.assertIn("\033[", out)

    def test_language_alias(self):
        from codex.renderer import normalize_language
        self.assertEqual(normalize_language("py"), "python")
        self.assertEqual(normalize_language("js"), "javascript")

class ExtendedCapabilityTests(unittest.TestCase):
    def test_registry_has_project_memory_git_checkpoint_doctor_background(self):
        from codex.tools import ToolRegistry
        with tempfile.TemporaryDirectory() as td:
            names={x['name'] for x in ToolRegistry(td).specs()}
            for name in {'project_scan','memory','git','checkpoint','doctor','background'}:
                self.assertIn(name,names)

    def test_project_scan_does_not_sample_secret_named_files(self):
        from codex.project import ProjectIndex
        with tempfile.TemporaryDirectory() as td:
            Path(td,'app.py').write_text('print(1)')
            Path(td,'.env').write_text('SECRET=do-not-index')
            data=ProjectIndex(td).scan()
            self.assertEqual(data['files'],2)
            self.assertNotIn('.env', [x['path'] for x in data['samples']])

    def test_memory_roundtrip(self):
        from codex.memory import MemoryStore
        with tempfile.TemporaryDirectory() as td:
            m=MemoryStore(td); m.add('decision','Use Gradle Kotlin DSL')
            self.assertTrue(m.search('Gradle Kotlin'))

    def test_checkpoint_create(self):
        from codex.checkpoint import Checkpoints
        with tempfile.TemporaryDirectory() as td:
            Path(td,'a.txt').write_text('one')
            c=Checkpoints(td); path=c.create('test')
            self.assertTrue(Path(path).is_dir())


class RendererRobustnessTests(unittest.TestCase):
    def test_html_css_js_blocks_are_separated(self):
        from codex.renderer import render_markdown
        text = """Berikut contoh:

```html
<!doctype html>
<html>
  <body><h1>Hello</h1></body>
</html>
```

```css
body { margin: 0; }
```

```js
const app = () => console.log('ok');
```

Selesai."""
        out = render_markdown(text)
        self.assertIn("┌─ html", out)
        self.assertIn("┌─ css", out)
        self.assertIn("┌─ javascript", out)
        self.assertIn("<!doctype html>", out)
        self.assertIn("Selesai.", out)
        self.assertGreaterEqual(out.count("┌─"), 3)

    def test_crlf_and_following_text(self):
        from codex.renderer import render_markdown
        out = render_markdown("```html\r\n<div>ok</div>\r\n```\r\nTeks sesudahnya")
        plain = __import__('re').sub(r"\x1b\[[0-9;]*m", "", out)
        self.assertIn("<div>ok</div>", plain)
        self.assertIn("Teks sesudahnya", out)
        self.assertIn("┌─ html", out)

    def test_unclosed_fence(self):
        from codex.renderer import render_markdown
        out = render_markdown("Penjelasan\n\n```html\n<div>belum selesai")
        plain = __import__('re').sub(r"\x1b\[[0-9;]*m", "", out)
        self.assertIn("┌─ html", plain)
        self.assertIn("<div>belum selesai", plain)


class FinalUpgradeTests(unittest.TestCase):
    def test_auto_detect_html_and_line_numbers(self):
        from codex.renderer import render_markdown
        import re
        out = render_markdown("```\n<!doctype html>\n<html><body>OK</body></html>\n```")
        plain = re.sub(r"\x1b\[[0-9;]*m", "", out)
        self.assertIn("┌─ html", plain)
        self.assertIn(" 1 │", plain)

    def test_live_renderer_buffers_code(self):
        from codex.renderer import LiveMarkdownRenderer
        import io, contextlib, re
        live = LiveMarkdownRenderer()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            live.feed("Intro\n```html\n<div>")
            self.assertIn("Intro", buf.getvalue())
            self.assertNotIn("<div>", buf.getvalue())
            live.feed("ok</div>\n```\nDone")
            live.finish()
        plain = re.sub(r"\x1b\[[0-9;]*m", "", buf.getvalue())
        self.assertIn("<div>ok</div>", plain)
        self.assertIn("Done", buf.getvalue())

    def test_registry_has_verify_and_diff(self):
        from codex.tools import ToolRegistry
        with tempfile.TemporaryDirectory() as td:
            names={x['name'] for x in ToolRegistry(td).specs()}
            self.assertIn('verify', names)
            self.assertIn('diff', names)

    def test_verify_compile(self):
        from codex.tools import ToolRegistry
        with tempfile.TemporaryDirectory() as td:
            Path(td,'ok.py').write_text('x = 1\n')
            result=ToolRegistry(td).call('verify', {})
            self.assertTrue(result['ok'])

class V5FixTests(unittest.TestCase):
    def test_delete_absolute_file_requires_confirmation(self):
        from codex.tools import delete_path, ToolError
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / 'remove-me.txt'
            p.write_text('x')
            with self.assertRaises(ToolError):
                delete_path(str(p), confirm='')
            self.assertTrue(p.exists())
            result = delete_path(str(p), confirm='DELETE')
            self.assertIn('deleted', result)
            self.assertFalse(p.exists())

    def test_delete_recursive_directory(self):
        from codex.tools import delete_path
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / 'folder'
            d.mkdir(); (d / 'a.txt').write_text('x')
            result = delete_path(str(d), recursive=True, confirm='DELETE')
            self.assertIn('deleted directory', result)
            self.assertFalse(d.exists())

    def test_registry_exposes_delete_tool(self):
        from codex.tools import ToolRegistry
        with tempfile.TemporaryDirectory() as td:
            spec = {x['name']: x for x in ToolRegistry(td).specs()}
            self.assertIn('delete', spec)
            self.assertIn('confirm', spec['delete']['parameters'])

    def test_actionable_file_request_detection(self):
        from codex.agent import Agent
        self.assertTrue(Agent._is_actionable_request('buat file index.html'))
        self.assertTrue(Agent._is_actionable_request('hapus folder build'))
        self.assertFalse(Agent._is_actionable_request('apa itu python?'))

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from fastapi.testclient import TestClient

from biomni_ui import providers as ui_providers
from biomni_ui import server as srv
from biomni_ui.models import ModelStore
from biomni_ui.providers import ProviderStore, clean_base_url, fetch_model_ids, is_local_url


class FakeOpenAI(BaseHTTPRequestHandler):
    """A tiny OpenAI-compatible server: GET /v1/models and POST /v1/chat/completions."""

    require_key: str | None = None
    seen_auth: list[str] = []

    def log_message(self, *a):  # keep the test output quiet
        pass

    def _send(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authorised(self):
        FakeOpenAI.seen_auth.append(self.headers.get("Authorization", ""))
        return FakeOpenAI.require_key is None or self.headers.get("Authorization") == f"Bearer {FakeOpenAI.require_key}"

    def do_GET(self):
        if not self._authorised():
            return self._send(401, {"error": "bad key"})
        if self.path == "/v1/models":
            return self._send(200, {"data": [{"id": "fake-model-1"}, {"id": "llama3.2:3b"}, {"id": "gpt-4o"}, {"id": "fake-coder"}]})
        self._send(404, {"error": "no"})

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if not self._authorised():
            return self._send(401, {"error": "bad key"})
        if self.path == "/v1/chat/completions":
            return self._send(200, {"id": "c1", "object": "chat.completion", "model": "fake-model-1",
                                    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                                    "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4}})
        self._send(404, {"error": "no"})


class FakeServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = HTTPServer(("127.0.0.1", 0), FakeOpenAI)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}/v1"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        FakeOpenAI.require_key = None
        FakeOpenAI.seen_auth = []


class ProviderStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ProviderStore(Path(self.tmp.name) / "p.json", env_base_url=lambda: "https://openrouter.ai/api/v1", env_api_key=lambda: "sk-env")

    def test_builtin_openrouter_comes_from_env_and_hides_its_key(self):
        rows = self.store.list()
        self.assertEqual(rows[0]["id"], "openrouter")
        self.assertTrue(rows[0]["has_key"] and rows[0]["builtin"])
        self.assertNotIn("api_key", json.dumps(rows))

    def test_no_env_connection_means_no_builtin(self):
        self.assertEqual(ProviderStore(Path(self.tmp.name) / "q.json").list(), [])

    def test_add_requires_key_unless_local(self):
        with self.assertRaises(ValueError):
            self.store.add("DeepSeek", "https://api.deepseek.com/v1", "")
        p = self.store.add("Ollama", "http://localhost:11434/v1", "")
        self.assertTrue(p["local"] and p["ready"])
        self.assertEqual(self.store.credentials(p["id"])[0], "http://localhost:11434/v1")

    def test_key_is_kept_out_of_the_public_view_but_used_for_calls(self):
        p = self.store.add("DeepSeek", "https://api.deepseek.com/v1/", "sk-secret", preset="deepseek")
        self.assertEqual(p["id"], "deepseek")
        self.assertNotIn("sk-secret", json.dumps(self.store.list()))
        self.assertEqual(self.store.credentials("deepseek"), ("https://api.deepseek.com/v1", "sk-secret"))

    def test_duplicate_address_and_bad_address_are_refused(self):
        self.store.add("A", "https://api.deepseek.com/v1", "k")
        with self.assertRaises(ValueError):
            self.store.add("B", "https://api.deepseek.com/v1/", "k")
        with self.assertRaises(ValueError):
            self.store.add("C", "not a url", "k")
        with self.assertRaises(ValueError):
            self.store.add("D", "ftp://x.example/v1", "k")

    def test_update_keeps_the_saved_key_when_the_field_is_empty(self):
        self.store.add("A", "https://a.example/v1", "key-1")
        self.store.update("a", api_key="")
        self.assertEqual(self.store.credentials("a")[1], "key-1")
        self.store.update("a", api_key="key-2", name="新名字")
        self.assertEqual(self.store.credentials("a")[1], "key-2")
        self.assertEqual(self.store.get("a")["name"], "新名字")

    def test_delete_and_unique_ids(self):
        self.store.add("Same", "https://a.example/v1", "k")
        second = self.store.add("Same", "https://b.example/v1", "k")
        self.assertEqual(second["id"], "same-2")
        self.assertTrue(self.store.delete("same"))
        self.assertFalse(self.store.delete("openrouter"))  # built-in is not stored, so it cannot be deleted here

    def test_local_detection(self):
        self.assertTrue(is_local_url("http://localhost:1/v1") and is_local_url("http://127.0.0.1/v1"))
        self.assertFalse(is_local_url("https://api.deepseek.com/v1"))
        self.assertEqual(clean_base_url(" https://x.example/v1/ "), "https://x.example/v1")


class FetchModelsTests(FakeServerCase):
    def test_lists_ids(self):
        self.assertEqual(fetch_model_ids(self.base, None), ["fake-coder", "fake-model-1", "gpt-4o", "llama3.2:3b"])

    def test_wrong_key_is_explained(self):
        FakeOpenAI.require_key = "right"
        with self.assertRaisesRegex(RuntimeError, "key is invalid"):
            fetch_model_ids(self.base, "wrong")
        self.assertEqual(len(fetch_model_ids(self.base, "right")), 4)

    def test_wrong_address_is_explained(self):
        with self.assertRaisesRegex(RuntimeError, "Wrong address"):
            fetch_model_ids(self.base.replace("/v1", "/nope"), None)

    def test_nothing_listening_on_a_local_address(self):
        with self.assertRaisesRegex(RuntimeError, "Cannot reach"):
            fetch_model_ids("http://127.0.0.1:1/v1", None, timeout=3)


class ServerWithAnotherProvider(FakeServerCase):
    """The whole path for a provider that is not OpenRouter: add it, find a model, add it, call it for real."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self._saved = (srv.providers, srv.models, srv.SETTINGS_FILE, dict(srv._provider_models))
        srv.providers = ProviderStore(d / "providers.json")  # no OpenRouter here: only what the test adds
        srv.models = ModelStore(d / "models.json", local_providers=srv.providers.local_ids)
        srv.SETTINGS_FILE = d / "settings.json"
        srv._provider_models.clear()
        self.addCleanup(self._restore)
        self.client = TestClient(srv.app)

    def _restore(self):
        srv.providers, srv.models, srv.SETTINGS_FILE = self._saved[:3]
        srv._provider_models.clear()
        srv._provider_models.update(self._saved[3])

    def _add_provider(self, key=""):
        r = self.client.post("/api/providers", json={"name": "Fake", "base_url": self.base, "api_key": key})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["id"]

    def test_add_provider_test_it_and_browse_its_models(self):
        pid = self._add_provider()
        self.assertTrue(self.client.post(f"/api/providers/{pid}/test").json()["ok"])
        res = self.client.get(f"/api/providers/{pid}/models?q=fake").json()
        self.assertEqual([m["id"] for m in res["results"]], ["fake-coder", "fake-model-1"])
        all_ids = [m["id"] for m in self.client.get(f"/api/providers/{pid}/models").json()["results"]]
        self.assertNotIn("gpt-4o", all_ids)  # GPT models are never offered, whichever provider lists them

    def test_only_models_the_provider_really_lists_can_be_added(self):
        pid = self._add_provider()
        bad = self.client.post("/api/models", json={"model": "not-there", "provider": pid})
        self.assertEqual(bad.status_code, 400)
        gpt = self.client.post("/api/models", json={"model": "gpt-4o", "provider": pid})
        self.assertEqual(gpt.status_code, 400)
        ok = self.client.post("/api/models", json={"model": "fake-model-1", "provider": pid})
        self.assertEqual(ok.status_code, 200, ok.text)
        added = ok.json()["added"]
        self.assertEqual(added["cost"], "local")  # a local server costs nothing
        row = next(m for m in ok.json()["models"] if m["id"] == added["id"])
        self.assertEqual((row["provider"], row["effort_options"]), (pid, []))  # no effort control we cannot back up

    def test_the_model_really_answers_through_that_provider(self):
        pid = self._add_provider()
        mid = self.client.post("/api/models", json={"model": "fake-model-1", "provider": pid}).json()["added"]["id"]
        res = self.client.post(f"/api/models/{mid}/test").json()
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["reply"], "ok")

    def test_deleting_a_provider_removes_its_models_and_refuses_while_in_use(self):
        pid = self._add_provider()
        mid = self.client.post("/api/models", json={"model": "fake-model-1", "provider": pid}).json()["added"]["id"]
        self.client.put("/api/active", json={"id": mid})
        busy = self.client.delete(f"/api/providers/{pid}")
        self.assertEqual(busy.status_code, 409)
        self.client.put("/api/active", json={"id": "chatgpt-luna"})
        done = self.client.delete(f"/api/providers/{pid}")
        self.assertEqual(done.status_code, 200)
        self.assertEqual(done.json()["models_removed"], 1)
        self.assertFalse(any(m["id"] == mid for m in done.json()["models"]))


if __name__ == "__main__":
    unittest.main()

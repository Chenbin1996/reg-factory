import asyncio
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import config
from webui import server


class FakeJSONRequest:
    def __init__(self, data=None):
        self._data = data or {}
        self.headers = {}
        self.client = SimpleNamespace(host="127.0.0.1")

    async def json(self):
        return self._data


class WebUIEnvReloadTests(unittest.TestCase):
    def _env_file(self, value):
        tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        tmp.write(f"DYNAMIC_TEST_KEY={value}\n")
        tmp.close()
        self.addCleanup(lambda: os.path.exists(tmp.name) and os.unlink(tmp.name))
        return tmp.name

    def test_child_env_uses_latest_dotenv_value_without_restart(self):
        path = self._env_file("new-value")
        with patch.object(server, "ENV_PATH", path):
            with patch.object(server, "BOOT_ENV", {}):
                with patch.dict(os.environ, {"DYNAMIC_TEST_KEY": "stale-value"}):
                    child = server._child_env()
        self.assertEqual(child["DYNAMIC_TEST_KEY"], "new-value")

    def test_global_config_honors_explicit_env_file(self):
        path = self._env_file("portable-value")
        with patch.dict(os.environ, {"REG_FACTORY_ENV_FILE": path}, clear=False):
            os.environ.pop("DYNAMIC_TEST_KEY", None)
            config._load_dotenv()
            self.assertEqual(os.environ.get("DYNAMIC_TEST_KEY"), "portable-value")
            os.environ.pop("DYNAMIC_TEST_KEY", None)

    def test_explicit_startup_environment_keeps_precedence(self):
        path = self._env_file("dotenv-value")
        with patch.object(server, "ENV_PATH", path):
            with patch.object(server, "BOOT_ENV", {"DYNAMIC_TEST_KEY": "system-value"}):
                with patch.dict(os.environ, {"DYNAMIC_TEST_KEY": "system-value"}):
                    child = server._child_env()
        self.assertEqual(child["DYNAMIC_TEST_KEY"], "system-value")

    def test_child_env_uses_clash_proxy_in_auto_mode(self):
        path = self._env_file("unused")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("PROXY_MODE=clash_auto\nCLASH_PROXY=http://127.0.0.1:7897\n")
        with patch.object(server, "ENV_PATH", path), patch.object(server, "BOOT_ENV", {}):
            child = server._child_env()
        self.assertEqual(child["HTTPS_PROXY"], "http://127.0.0.1:7897")

    def test_child_env_uses_residential_proxy(self):
        path = self._env_file("unused")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("PROXY_MODE=residential\nREG_FACTORY_PROXY=http://home.test:9000\n")
        with patch.object(server, "ENV_PATH", path), patch.object(server, "BOOT_ENV", {}):
            child = server._child_env()
        self.assertEqual(child["HTTPS_PROXY"], "http://home.test:9000")

    def test_status_exposes_loaded_version_and_process_id(self):
        with patch.object(server, "_fingerprint_provider", return_value="bitbrowser"):
            with patch.object(server, "_read_config_val", side_effect=lambda _key, default="": default):
                with patch.object(server, "_http_alive", return_value=True):
                    with patch.object(server, "_k12_alive", return_value=False):
                        with patch("common.proxy_switch.current_node", return_value="test-node"):
                            status = server.api_status()
        self.assertEqual(status["pid"], os.getpid())
        self.assertEqual(status["version"], server.WEBUI_VERSION)
        self.assertEqual(status["root"], server.ROOT)

    def test_residential_proxy_test_retries_with_fresh_connections(self):
        response = MagicMock()
        response.json.return_value = {"ip": "203.0.113.9"}
        response.text = ""
        failures = [RuntimeError("first exit timeout"), RuntimeError("second exit timeout"), response]

        async def run_test():
            with patch("common.proxy_switch.effective_proxy_url", return_value="http://user:pass@home.test:9000"):
                with patch("common.proxy_switch.proxy_mode", return_value="residential"):
                    with patch("common.proxy_switch.current_node", return_value="http://home.test:9000"):
                        with patch("curl_cffi.requests.get", side_effect=failures) as request:
                            result = await server.api_proxy_test()
            return result, request

        result, request = asyncio.run(run_test())
        self.assertTrue(result["ok"])
        self.assertEqual(result["ip"], "203.0.113.9")
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(request.call_count, 3)

    def test_residential_proxy_test_redacts_credentials_from_errors(self):
        async def run_test():
            with patch("common.proxy_switch.effective_proxy_url", return_value="http://user:pass@home.test:9000"):
                with patch("common.proxy_switch.proxy_mode", return_value="residential"):
                    with patch(
                        "curl_cffi.requests.get",
                        side_effect=RuntimeError("proxy user:pass rejected at http://user:pass@home.test:9000"),
                    ):
                        return await server.api_proxy_test()

        response = asyncio.run(run_test())
        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("user", payload["error"])
        self.assertNotIn("pass", payload["error"])

    def test_asset_api_without_key_is_loopback_only(self):
        local = SimpleNamespace(headers={}, client=SimpleNamespace(host="127.0.0.1"))
        remote = SimpleNamespace(headers={}, client=SimpleNamespace(host="192.0.2.10"))
        with patch.object(server, "_read_config_val", return_value=""):
            self.assertIsNone(server._asset_api_denied(local))
            self.assertEqual(server._asset_api_denied(remote).status_code, 403)

    def test_asset_api_accepts_header_or_bearer_key(self):
        by_header = SimpleNamespace(
            headers={"x-api-key": "asset-secret"}, client=SimpleNamespace(host="192.0.2.10")
        )
        by_bearer = SimpleNamespace(
            headers={"authorization": "Bearer asset-secret"},
            client=SimpleNamespace(host="192.0.2.10"),
        )
        denied = SimpleNamespace(
            headers={"x-api-key": "wrong"}, client=SimpleNamespace(host="127.0.0.1")
        )
        with patch.object(server, "_read_config_val", return_value="asset-secret"):
            self.assertIsNone(server._asset_api_denied(by_header))
            self.assertIsNone(server._asset_api_denied(by_bearer))
            self.assertEqual(server._asset_api_denied(denied).status_code, 401)


class WebUIRunStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_done_event_exposes_exit_code_and_stop_state(self):
        run_id = "test-result-event"
        server.RUNS[run_id] = {
            "lines": ["finished"],
            "done": True,
            "returncode": 7,
            "stopped": False,
        }
        self.addCleanup(server.RUNS.pop, run_id, None)

        response = await server.api_logs(run_id)
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
        body = "".join(chunks)

        self.assertIn("event: done", body)
        payload = body.split("event: done\ndata: ", 1)[1].split("\n", 1)[0]
        self.assertEqual(
            json.loads(payload),
            {"returncode": 7, "stopped": False},
        )


class WebUIAssetScanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        server.ASSET_SCAN_TASK = None
        server.ASSET_SCAN_STATE.update({
            "running": False,
            "started_at": "",
            "finished_at": "",
            "error": "",
            "progress": {"completed": 0, "total": 0, "current": ""},
        })

    async def test_asset_scan_runs_in_background_and_exposes_progress(self):
        from common import asset_scanner

        report = {
            "schema_version": 1,
            "finished_at": "2026-07-28T09:00:00Z",
            "last_scan_at": "2026-07-28T09:00:00Z",
            "items": [{"id": "one", "platform": "outlook", "status": "normal"}],
            "summary": {"total": 1, "statuses": {"normal": 1}, "platforms": {}},
        }

        def scan_pool(**kwargs):
            kwargs["progress"]({"completed": 1, "total": 1, "current": "mail@example.com"})
            return report

        with patch.object(asset_scanner, "get_report", return_value=report):
            with patch.object(asset_scanner, "scan_pool", side_effect=scan_pool):
                started = await server.api_asset_scan_start(
                    FakeJSONRequest({"platforms": ["outlook"], "concurrency": 2})
                )
                task = server.ASSET_SCAN_TASK
                self.assertTrue(started["ok"])
                self.assertTrue(started["scan"]["running"])
                await task
                current = server.api_asset_scan_get(FakeJSONRequest())

        self.assertFalse(current["scan"]["running"])
        self.assertEqual(current["scan"]["progress"]["completed"], 1)
        self.assertEqual(current["summary"]["statuses"]["normal"], 1)

    async def test_asset_scan_rejects_unknown_platform(self):
        response = await server.api_asset_scan_start(FakeJSONRequest({"platforms": ["unknown"]}))
        self.assertEqual(response.status_code, 400)



if __name__ == "__main__":
    unittest.main()

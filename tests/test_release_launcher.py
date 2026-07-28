import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reg-factory-server.py"
SPEC = importlib.util.spec_from_file_location("reg_factory_release_launcher", SCRIPT)
launcher = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = launcher
SPEC.loader.exec_module(launcher)


class ReleaseLauncherTests(unittest.TestCase):
    def test_reuses_service_only_when_version_matches(self):
        availability = {8799: False, 8800: False}

        def status(port):
            versions = {8799: "1.2.0", 8800: "1.2.1"}
            return {"version": versions[port], "browser_provider": "bitbrowser", "running": 0}

        with patch.object(
            launcher,
            "_port_available",
            side_effect=lambda _host, port: availability.get(port, True),
        ):
            with patch.object(launcher, "_existing_reg_factory", side_effect=status):
                self.assertEqual(
                    launcher._select_port("127.0.0.1", 8799, "1.2.1"),
                    (8800, True),
                )

    def test_old_service_moves_new_version_to_first_free_port(self):
        with patch.object(launcher, "_port_available", side_effect=lambda _host, port: port != 8799):
            with patch.object(
                launcher,
                "_existing_reg_factory",
                return_value={"version": "1.2.0", "browser_provider": "bitbrowser", "running": 0},
            ):
                self.assertEqual(
                    launcher._select_port("127.0.0.1", 8799, "1.2.1"),
                    (8800, False),
                )

    def test_free_requested_port_starts_current_version(self):
        with patch.object(launcher, "_port_available", return_value=True):
            with patch.object(launcher, "_existing_reg_factory") as existing:
                self.assertEqual(
                    launcher._select_port("127.0.0.1", 8799, "1.2.1"),
                    (8799, False),
                )
        existing.assert_not_called()

    def test_proxy_test_applies_current_form_before_request(self):
        source = (ROOT / "webui" / "static" / "app.js").read_text(encoding="utf-8")
        function = source.split("async function testProxy(){", 1)[1].split("\n}", 1)[0]
        self.assertLess(function.index("applyProxyConfig()"), function.index("'/api/proxy/test'"))


if __name__ == "__main__":
    unittest.main()

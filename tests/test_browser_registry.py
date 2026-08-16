import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from common import browser_registry


class BrowserRegistryTests(unittest.TestCase):
    def test_register_and_unregister_are_cross_process_safe_records(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "active.json"
            with patch.object(browser_registry, "_path", return_value=path), \
                    patch.dict(os.environ, {"REG_FACTORY_RUN_ID": "test-run"}, clear=False):
                browser_registry.register("profile-1", name="chatgpt_test", api_base="http://127.0.0.1:54345")
                self.assertEqual(browser_registry.active_profiles(owner="test-run")[0]["name"], "chatgpt_test")
                browser_registry.unregister("profile-1")
                self.assertEqual(browser_registry.active_profiles(), [])


if __name__ == "__main__":
    unittest.main()

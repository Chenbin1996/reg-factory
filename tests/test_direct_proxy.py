import os
import tempfile
import unittest
from unittest.mock import patch

from bitbrowser import BitBrowser
from common import direct_proxy
from common import proxy_switch


class DirectProxyTests(unittest.TestCase):
    def test_parse_proxy_preserves_authenticated_url(self):
        proxy = direct_proxy.parse_proxy("socks5://user:pass@proxy.test:1080")
        self.assertEqual(proxy.server, "socks5://proxy.test:1080")
        self.assertEqual(proxy.url, "socks5://user:pass@proxy.test:1080")

    def test_pool_rotation_persists_active_proxy(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {
                "REG_FACTORY_PROXY_POOL": "http://one.test:8001,http://two.test:8002",
                "REG_FACTORY_PROXY_STATE_FILE": os.path.join(directory, "index.txt"),
            }
            self.assertEqual(direct_proxy.configured_proxy(environ=env).host, "one.test")
            self.assertEqual(direct_proxy.rotate_proxy_pool(environ=env).host, "two.test")
            self.assertEqual(direct_proxy.configured_proxy(environ=env).host, "two.test")
            self.assertEqual(direct_proxy.rotate_proxy_pool(environ=env).host, "one.test")

    def test_pool_takes_precedence_over_single_proxy(self):
        env = {
            "REG_FACTORY_PROXY": "http://single.test:8080",
            "REG_FACTORY_PROXY_POOL": "http://pool.test:8081",
        }
        self.assertEqual(direct_proxy.configured_proxy(environ=env).host, "pool.test")

    def test_bitbrowser_create_payload_receives_residential_proxy(self):
        env = {
            "PROXY_MODE": "residential",
            "REG_FACTORY_PROXY": "socks5://user:pass@proxy.test:1080",
            "FINGERPRINT_BROWSER": "bitbrowser",
        }
        with patch.dict(os.environ, env, clear=True):
            browser = BitBrowser(api_base="http://127.0.0.1:54345")
            with patch.object(browser, "_post", return_value={"data": {"id": "profile-1"}}) as post:
                profile_id = browser.create_browser(
                    name="residential-test",
                    **proxy_switch.browser_proxy_fields(),
                )
        self.assertEqual(profile_id, "profile-1")
        payload = post.call_args.args[1]
        self.assertEqual(payload["proxyType"], "socks5")
        self.assertEqual(payload["host"], "proxy.test")
        self.assertEqual(payload["port"], "1080")
        self.assertEqual(payload["proxyUserName"], "user")
        self.assertEqual(payload["proxyPassword"], "pass")


if __name__ == "__main__":
    unittest.main()

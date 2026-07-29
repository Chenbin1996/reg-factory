import argparse
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import register_three_platforms
from common import asset_scanner, asset_store
from common.kiro_crypto import FingerprintBuilder, _xxtea_decrypt, _xxtea_encrypt, encrypt_password
from common.session_export import save_kiro_token
from webui.scripts import ENV_SCHEMA, SCRIPTS


class KiroCryptoTests(unittest.TestCase):
    def test_xxtea_roundtrip(self):
        builder = FingerprintBuilder()
        raw = "fingerprint payload with unicode-free content"
        encrypted = _xxtea_encrypt(raw, builder.key)
        self.assertEqual(_xxtea_decrypt(encrypted, builder.key), raw)

    def test_fingerprint_has_expected_envelope(self):
        value = FingerprintBuilder().encrypted(
            "https://us-east-1.signin.aws/platform/directory/login",
            "https://view.awsapps.com/", "signin", "first_load",
        )
        identifier, encoded = value.split(":", 1)
        self.assertTrue(identifier)
        self.assertGreater(len(encoded), 100)

    def test_jwe_compact_serialization(self):
        # A 512-bit key is intentionally not accepted by RSA-OAEP-256; use a
        # generated test key and only verify the wire shape here.
        from cryptography.hazmat.primitives.asymmetric import rsa
        import base64
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key().public_numbers()
        enc = encrypt_password(
            "Aa1!test-password", {
                "kid": "test", "n": base64.urlsafe_b64encode(key.n.to_bytes((key.n.bit_length() + 7) // 8, "big")).decode().rstrip("="),
                "e": base64.urlsafe_b64encode(key.e.to_bytes((key.e.bit_length() + 7) // 8, "big")).decode().rstrip("="),
            },
        )
        self.assertEqual(len(enc.split(".")), 5)


class KiroIntegrationTests(unittest.TestCase):
    def test_orchestrator_builds_kiro_command(self):
        args = argparse.Namespace(timeout=600, node="auto", kiro_account_password="")
        command = register_three_platforms.build_command("kiro", args, ("user@example.com", "mail-pass", "rt", "cid"))
        self.assertIn("register_kiro.py", command)
        self.assertIn("--refresh-token", command)
        self.assertIn("--client-id", command)

    def test_schema_and_proxy_route_expose_kiro(self):
        task = next(item for item in SCRIPTS if item["id"] == "register_kiro")
        self.assertEqual(task["file"], "register_kiro.py")
        keys = {item["key"] for group in ENV_SCHEMA for item in group["items"]}
        self.assertIn("KIRO_PROXY_MODE", keys)

    def test_save_and_read_kiro_account_asset(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            "TOKEN_OUTPUT_DIR": "tokens", "REG_FACTORY_DATA_DIR": root,
        }, clear=False):
            with patch("common.session_export.TOKEN_OUTPUT_DIR", str(Path(root) / "tokens")):
                self.assertTrue(save_kiro_token({
                    "email": "user@example.com", "refreshToken": "rt", "clientId": "cid",
                    "clientSecret": "secret", "provider": "BuilderId",
                }, "user@example.com"))
            path = Path(root) / "tokens" / "kiro" / "user@example.com.account.json"
            self.assertTrue(path.is_file())
            with patch.object(asset_store, "_data_root", return_value=Path(root)):
                with patch.object(asset_store, "_token_root", return_value=Path(root) / "tokens"):
                    result = asset_store.get_platform_asset("kiro", "session", index=0)
            self.assertEqual(result["data"]["clientId"], "cid")

    def test_scanner_includes_kiro_platform(self):
        self.assertIn("kiro", asset_scanner._SCANNERS)


if __name__ == "__main__":
    unittest.main()

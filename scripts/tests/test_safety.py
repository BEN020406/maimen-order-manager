"""脱敏与能力发现测试（对应安全回归项）。"""

import json
import pathlib
import sys
import unittest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from common import mcp_client, redact  # noqa: E402

FIXTURES = SCRIPTS_DIR / "fixtures"


def load_json(name):
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)


class TestMasking(unittest.TestCase):
    def test_tax_id_mask_shape(self):
        self.assertEqual(redact.mask_tax_id("91350100M000100Y43"), "9135**********0Y43")

    def test_tax_id_mask_empty(self):
        self.assertEqual(redact.mask_tax_id(""), "未知")
        self.assertEqual(redact.mask_tax_id(None), "未知")

    def test_email_mask(self):
        self.assertEqual(redact.mask_email("zhangsan@example.com"), "z***@example.com")

    def test_email_invalid(self):
        self.assertEqual(redact.mask_email("not-an-email"), "******")

    def test_order_id_mask(self):
        self.assertEqual(redact.mask_order_id("DD20261020001"), "DD2*******001")

    def test_token_mask(self):
        masked = redact.mask_token("abcdefghijklmnop")
        self.assertTrue(masked.startswith("abcd"))
        self.assertNotIn("efgh", masked)

    def test_redact_authorization_header(self):
        text = redact.redact_text("Authorization: Bearer sk-live-1234567890abcdef")
        self.assertNotIn("sk-live-1234567890abcdef", text)
        self.assertIn("Bearer", text)

    def test_redact_payload_nested(self):
        payload = {
            "company": "示例",
            "tax_id": "91350100M000100Y43",
            "email": "a@b.com",
            "nested": {"mcp_token": "supersecrettoken123456"},
            "list": [{"taxId": "91350100M000100Y43"}],
        }
        cleaned = redact.redact_payload(payload)
        dumped = json.dumps(cleaned, ensure_ascii=False)
        self.assertNotIn("91350100M000100Y43", dumped)
        self.assertNotIn("a@b.com", dumped)
        self.assertNotIn("supersecrettoken123456", dumped)
        self.assertIn("示例", dumped)

    def test_assert_no_secret_leak(self):
        self.assertTrue(redact.assert_no_secret_leak("税号 9135**********Y43"))
        self.assertFalse(
            redact.assert_no_secret_leak("税号 91350100M000100Y43", ["91350100M000100Y43"])
        )


class TestCapabilityDiscovery(unittest.TestCase):
    def test_public_toolset(self):
        report = mcp_client.discover(load_json("tools_public.json"))
        self.assertEqual(report["modules"]["orders"]["mode"], "full")
        self.assertEqual(report["modules"]["invoice"]["mode"], "full")
        self.assertEqual(report["modules"]["lottery"]["mode"], "full")
        self.assertTrue(report["handoff"]["invoice"])
        self.assertTrue(report["handoff"]["review"])

    def test_missing_order_list_is_unsupported(self):
        report = mcp_client.discover(load_json("tools_empty.json"))
        self.assertEqual(report["modules"]["orders"]["mode"], "unsupported")
        self.assertIn("order-list", mcp_client.missing_tools_summary(report))

    def test_policy_blocked_tools_reported(self):
        report = mcp_client.discover(load_json("tools_public.json"))
        blocked = {item["tool"] for item in report["policy_blocked"]}
        self.assertIn("create-order", blocked)

    def test_bare_name_list_supported(self):
        report = mcp_client.discover(["order-list", "query-lottery-info", "draw-lottery"])
        self.assertEqual(report["modules"]["lottery"]["mode"], "degraded")
        self.assertIn("query-my-prizes", report["modules"]["lottery"]["missing"])

    def test_render_matrix_is_readable(self):
        text = mcp_client.render_matrix(mcp_client.discover(load_json("tools_public.json")))
        self.assertIn("待评价订单：完整", text)
        self.assertIn("交接模式", text)


if __name__ == "__main__":
    unittest.main()

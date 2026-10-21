"""CLI / 首页快照集成测试：卡片聚合、脱敏、口径一致。"""

import json
import pathlib
import subprocess
import sys
import unittest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import cli  # noqa: E402

FIXTURES = SCRIPTS_DIR / "fixtures"


def load_json(name):
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)


class TestSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = cli.build_snapshot(
            load_json("orders.json"),
            lottery_raw=load_json("lottery_info.json"),
            profile=load_json("invoice_profile.json"),
            tools_raw=load_json("tools_public.json"),
            city="上海",
        )

    def test_three_module_cards(self):
        cards = self.snapshot["home"]["cards"]
        self.assertEqual([c["module"] for c in cards], ["orders", "invoice", "lottery"])
        self.assertEqual(cards[0]["value"], "4 笔")
        self.assertEqual(cards[1]["value"], "5 笔")

    def test_pending_total_is_deduped_union(self):
        review_ids = {o["order_id"] for o in self.snapshot["review"]["candidates"]}
        invoice_ids = {o["order_id"] for o in self.snapshot["invoice"]["candidates"]}
        self.assertEqual(self.snapshot["home"]["pending_total"], len(review_ids | invoice_ids))

    def test_snapshot_has_no_plaintext_tax_id(self):
        dumped = json.dumps(self.snapshot, ensure_ascii=False)
        self.assertNotIn("91350100M000100Y43", dumped)
        self.assertNotIn("finance@example.com", dumped)

    def test_capabilities_embedded(self):
        caps = self.snapshot["capabilities"]
        self.assertEqual(caps["modules"]["orders"]["mode"], "full")
        self.assertTrue(caps["handoff"]["invoice"])

    def test_timeline_sorted_desc(self):
        dates = [item["date"] for item in self.snapshot["home"]["timeline"]]
        self.assertEqual(dates, sorted(dates, reverse=True))


class TestCliProcess(unittest.TestCase):
    """真实跑一次进程，确认退出码与输出编码正常。"""

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "cli.py"), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(SCRIPTS_DIR),
        )

    def test_orders_command(self):
        proc = self.run_cli("orders", "--input", str(FIXTURES / "orders.json"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("待评价候选：4 笔", proc.stdout)

    def test_lottery_preview_command(self):
        proc = self.run_cli("lottery-preview", "--input", str(FIXTURES / "lottery_info.json"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("本次操作：抽奖 1 次", proc.stdout)

    def test_capabilities_json(self):
        proc = self.run_cli(
            "capabilities", "--tools", str(FIXTURES / "tools_empty.json"), "--format", "json"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["modules"]["orders"]["mode"], "unsupported")

    def test_missing_file_exit_code(self):
        proc = self.run_cli("orders", "--input", str(FIXTURES / "does_not_exist.json"))
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()

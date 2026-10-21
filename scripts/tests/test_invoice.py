"""发票助手测试：真实订单筛选、金额合计、资料校验、脱敏与交接。"""

import json
import pathlib
import sys
import unittest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from operations.invoice import (  # noqa: E402
    build_invoice_card,
    filter_candidates,
    plan_reimbursement,
    validate_profile,
    validate_uscc,
)

FIXTURES = SCRIPTS_DIR / "fixtures"


def load_json(name):
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)


class TestUsccValidation(unittest.TestCase):
    def test_known_valid_codes(self):
        self.assertTrue(validate_uscc("91350100M000100Y43")["valid"])
        self.assertTrue(validate_uscc("9131000063116937XG")["valid"])

    def test_wrong_length_reports_but_not_crash(self):
        result = validate_uscc("91350100M000100Y4")
        self.assertFalse(result["valid"])
        self.assertIn("18 位", result["issues"][0])

    def test_illegal_chars(self):
        result = validate_uscc("91350100M000100Y4I")
        self.assertFalse(result["valid"])

    def test_wrong_check_digit(self):
        result = validate_uscc("91350100M000100Y44")
        self.assertFalse(result["valid"])
        self.assertIn("校验位", result["issues"][0])

    def test_lowercase_accepted(self):
        self.assertTrue(validate_uscc("91350100m000100y43")["valid"])


class TestCandidateFilter(unittest.TestCase):
    def setUp(self):
        self.orders = load_json("orders.json")

    def test_shanghai_total_from_real_orders(self):
        result = filter_candidates(self.orders, city="上海")
        self.assertEqual(result["count"], 5)
        self.assertAlmostEqual(result["total_amount"], 196.5, places=2)

    def test_cancelled_and_unpaid_excluded(self):
        result = filter_candidates(self.orders)
        ids = {order["order_id"] for order in result["candidates"]}
        self.assertNotIn("DD20261015006", ids)  # 已取消
        self.assertNotIn("DD20261014007", ids)  # 待支付
        self.assertNotIn("DD20261013008", ids)  # 配送中
        self.assertEqual(result["count"], 7)

    def test_city_unknown_is_excluded_not_guessed(self):
        orders = [
            {"orderId": "X1", "orderStatus": "订单已完成", "realTotalAmount": "10"},
        ]
        result = filter_candidates(orders, city="上海")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["city_unknown_excluded"], 1)
        self.assertIn("不做猜测归类", result["excluded"][0]["reason"])

    def test_city_inferred_flagged(self):
        result = filter_candidates(self.orders, city="上海")
        self.assertTrue(result["city_inferred"])

    def test_store_filter(self):
        result = filter_candidates(self.orders, store="陆家嘴")
        self.assertTrue(all("陆家嘴" in o["store_name"] for o in result["candidates"]))

    def test_amount_range(self):
        result = filter_candidates(self.orders, min_amount=40, max_amount=45)
        amounts = [o["paid_amount"] for o in result["candidates"]]
        self.assertTrue(amounts)
        self.assertTrue(all(40 <= a <= 45 for a in amounts))

    def test_date_range(self):
        result = filter_candidates(self.orders, date_from="2026-10-18", date_to="2026-10-20")
        for order in result["candidates"]:
            self.assertGreaterEqual(order["created_at"][:10], "2026-10-18")
            self.assertLessEqual(order["created_at"][:10], "2026-10-20")

    def test_amount_missing_not_counted_as_zero(self):
        orders = [{"orderId": "X1", "orderStatus": "订单已完成", "storeName": "麦当劳·上海店"}]
        result = filter_candidates(orders)
        self.assertEqual(result["total_amount"], 0.0)
        self.assertEqual(result["amount_missing"], ["X1"])


class TestInvoiceCard(unittest.TestCase):
    def setUp(self):
        self.orders = load_json("orders.json")
        self.profile = load_json("invoice_profile.json")

    def test_card_contains_totals_and_handoff(self):
        card = build_invoice_card(self.orders, self.profile, city="上海")
        self.assertEqual(card["state"], "HANDOFF")
        self.assertTrue(card["ready"])
        self.assertIn("找到 5 笔上海订单", card["text"])
        self.assertIn("¥196.50", card["text"])
        self.assertIn("官方 App", card["text"])
        self.assertFalse(card["handoff"]["auto_submit"])

    def test_tax_id_never_appears_in_plaintext(self):
        card = build_invoice_card(self.orders, self.profile, city="上海")
        raw_tax = self.profile["tax_id"]
        self.assertNotIn(raw_tax, card["text"])
        self.assertNotIn(raw_tax, json.dumps(card, ensure_ascii=False))
        self.assertIn("9135**********0Y43", card["text"])

    def test_missing_company_blocks_ready(self):
        card = build_invoice_card(self.orders, {"company_name": "", "tax_id": "91350100M000100Y43"})
        self.assertFalse(card["ready"])
        self.assertIn("公司抬头不能为空", card["profile"]["errors"])

    def test_bad_email_warns_only(self):
        profile = dict(self.profile, email="not-an-email")
        card = build_invoice_card(self.orders, profile)
        self.assertTrue(card["profile"]["ok"])
        self.assertTrue(any("邮箱" in w for w in card["warnings"]))

    def test_invalid_tax_id_warns_but_does_not_block(self):
        profile = {"company_name": "示例公司", "tax_id": "91350100M000100Y4"}
        card = build_invoice_card(self.orders, profile)
        self.assertTrue(card["profile"]["ok"])
        self.assertTrue(any("18 位" in w for w in card["warnings"]))

    def test_no_candidate_keeps_honest_copy(self):
        card = build_invoice_card(self.orders, self.profile, city="拉萨")
        self.assertEqual(card["count"], 0)
        self.assertIn("没有可开票订单", card["text"])

    def test_profile_validation_standalone(self):
        result = validate_profile("上海示例科技有限公司", "91350100M000100Y43", "a@b.com")
        self.assertTrue(result["ok"])
        self.assertEqual(result["tax_id_masked"], "9135**********0Y43")
        self.assertEqual(result["email_masked"], "a***@b.com")


class TestReimbursement(unittest.TestCase):
    """报销门槛凑单：只组合真实订单，优先超出最少、其次单数最少。"""

    def test_picks_minimal_overshoot(self):
        candidates = [
            {"order_id": "A", "paid_amount": 60.0},
            {"order_id": "B", "paid_amount": 45.0},
            {"order_id": "C", "paid_amount": 20.0},
        ]
        plan = plan_reimbursement(candidates, 100)
        self.assertTrue(plan["reachable"])
        self.assertEqual(sorted(plan["selected"]), ["A", "B"])
        self.assertAlmostEqual(plan["selected_total"], 105.0)
        self.assertAlmostEqual(plan["overshoot"], 5.0)
        self.assertIn("超出", plan["text"])

    def test_exact_hit(self):
        plan = plan_reimbursement([{"order_id": "A", "paid_amount": 50.0}], 50)
        self.assertAlmostEqual(plan["overshoot"], 0.0)
        self.assertIn("刚好达标", plan["text"])

    def test_reports_gap_when_short(self):
        plan = plan_reimbursement(
            [{"order_id": "A", "paid_amount": 30.0}, {"order_id": "B", "paid_amount": 20.0}], 100
        )
        self.assertFalse(plan["reachable"])
        self.assertAlmostEqual(plan["gap"], 50.0)
        self.assertIn("还差", plan["text"])

    def test_empty_candidates(self):
        plan = plan_reimbursement([], 50)
        self.assertFalse(plan["reachable"])
        self.assertIn("没有可开票订单", plan["text"])

    def test_card_includes_target_section(self):
        orders = load_json("orders.json")
        profile = load_json("invoice_profile.json")
        card = build_invoice_card(orders, profile, city="上海", target=100)
        self.assertIn("报销门槛 ¥100.00", card["text"])
        self.assertTrue(card["reimbursement"]["reachable"])
        self.assertGreaterEqual(card["reimbursement"]["selected_total"], 100)

    def test_selected_orders_must_be_real_candidates(self):
        card = build_invoice_card(load_json("orders.json"), city="上海", target=100)
        candidate_ids = {o["order_id"] for o in card["candidates"]}
        self.assertTrue(set(card["reimbursement"]["selected"]).issubset(candidate_ids))


if __name__ == "__main__":
    unittest.main()

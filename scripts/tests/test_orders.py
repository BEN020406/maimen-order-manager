"""订单状态映射与待评价统计测试（对应交付稿 P0 前三条）。"""

import json
import pathlib
import sys
import unittest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from common.contracts import classify_review, normalize_order  # noqa: E402
from operations.orders import (  # noqa: E402
    build_review_center,
    parse_tiers,
    reward_progress,
)

FIXTURES = SCRIPTS_DIR / "fixtures"


def load_orders():
    with open(FIXTURES / "orders.json", encoding="utf-8") as handle:
        return json.load(handle)


class TestReviewStatusMapping(unittest.TestCase):
    def test_code_8_int_means_reviewed(self):
        order = normalize_order(
            {"orderId": "1", "orderStatus": "订单已完成", "orderStatusCode": 8}
        )
        self.assertEqual(order.review_state, "reviewed")
        self.assertEqual(order.review_label, "已评价")

    def test_code_8_string_means_reviewed(self):
        order = normalize_order(
            {"orderId": "1", "orderStatus": "订单已完成", "orderStatusCode": "8"}
        )
        self.assertEqual(order.review_state, "reviewed")

    def test_completed_without_review_field_is_unknown(self):
        """字段不存在时必须「无法确认」，绝不能默认算未评价。"""
        order = normalize_order({"orderId": "1", "orderStatus": "订单已完成"})
        self.assertEqual(order.review_state, "unknown")
        self.assertEqual(order.review_label, "待确认")

    def test_completed_with_non_8_code_is_likely_pending(self):
        order = normalize_order(
            {"orderId": "1", "orderStatus": "订单已完成", "orderStatusCode": 0}
        )
        self.assertEqual(order.review_state, "likely_pending")
        self.assertEqual(order.review_label, "可能待评价")

    def test_status_text_reviewed_wins_without_code(self):
        order = normalize_order({"orderId": "1", "orderStatus": "订单已完成已评价"})
        self.assertEqual(order.review_state, "reviewed")

    def test_cancelled_is_not_eligible(self):
        order = normalize_order({"orderId": "1", "orderStatus": "订单已取消"})
        self.assertEqual(order.review_state, "not_eligible")

    def test_pending_payment_is_not_eligible(self):
        order = normalize_order({"orderId": "1", "orderStatus": "待支付"})
        self.assertEqual(order.review_state, "not_eligible")

    def test_in_progress_is_not_eligible(self):
        order = normalize_order({"orderId": "1", "orderStatus": "配送中"})
        self.assertEqual(order.review_state, "not_eligible")

    def test_missing_status_is_unknown_not_pending(self):
        order = normalize_order({"orderId": "1"})
        self.assertEqual(order.review_state, "unknown")

    def test_classify_is_pure_function(self):
        order = normalize_order({"orderId": "1", "orderStatus": "订单已完成", "orderStatusCode": 0})
        self.assertEqual(classify_review(order), ("likely_pending", "可能待评价", "订单已完成，评价状态码为 0"))


class TestFieldTolerance(unittest.TestCase):
    def test_missing_amount_stays_none(self):
        order = normalize_order({"orderId": "1", "orderStatus": "订单已完成"})
        self.assertIsNone(order.paid_amount)
        self.assertIsNone(order.to_dict()["paid_amount"])

    def test_amount_string_parsed(self):
        order = normalize_order({"orderId": "1", "realTotalAmount": "42"})
        self.assertEqual(float(order.paid_amount), 42.0)

    def test_amount_with_currency_symbol(self):
        order = normalize_order({"orderId": "1", "realTotalAmount": "¥31.50"})
        self.assertEqual(float(order.paid_amount), 31.5)

    def test_city_from_field(self):
        order = normalize_order({"orderId": "1", "storeName": "麦当劳·深圳华强北店", "cityName": "深圳"})
        self.assertEqual(order.store_city, "深圳")
        self.assertEqual(order.city_source, "field")

    def test_city_inferred_from_store_name_is_marked(self):
        order = normalize_order({"orderId": "1", "storeName": "麦当劳·上海南京东路店"})
        self.assertEqual(order.store_city, "上海")
        self.assertEqual(order.city_source, "store_name")

    def test_city_unknown_when_no_hint(self):
        order = normalize_order({"orderId": "1", "storeName": "某某店"})
        self.assertIsNone(order.store_city)
        self.assertEqual(order.city_source, "unknown")

    def test_order_type_digit_not_guessed(self):
        order = normalize_order({"orderId": "1", "orderType": "1"})
        self.assertIn("接口未定义", order.order_type_label)

    def test_items_normalized(self):
        order = normalize_order(
            {
                "orderId": "1",
                "orderProductList": [{"productCode": "B1", "productName": "巨无霸", "quantity": 2}],
            }
        )
        self.assertEqual(order.items[0]["name"], "巨无霸")
        self.assertEqual(order.items[0]["quantity"], 2)


class TestReviewCenter(unittest.TestCase):
    def setUp(self):
        self.center = build_review_center(load_orders())

    def test_scope_uses_actual_returned_count(self):
        self.assertEqual(self.center["counts"]["total"], 10)
        self.assertEqual(self.center["scope"]["scope_note"], "最近 10 笔订单")

    def test_pending_count_excludes_cancelled_and_pending(self):
        pending_ids = {o["order_id"] for o in self.center["pending"]}
        self.assertIn("DD20261020002", pending_ids)
        self.assertIn("DD20261018003", pending_ids)
        self.assertIn("DD20261012009", pending_ids)
        self.assertNotIn("DD20261015006", pending_ids)  # 已取消
        self.assertNotIn("DD20261014007", pending_ids)  # 待支付
        self.assertEqual(self.center["counts"]["likely_pending"], 3)
        self.assertEqual(self.center["counts"]["candidates"], 4)

    def test_reviewed_recognized(self):
        reviewed_ids = {o["order_id"] for o in self.center["reviewed"]}
        self.assertIn("DD20261020001", reviewed_ids)
        self.assertIn("DD20261011010", reviewed_ids)

    def test_unknown_not_counted_as_pending(self):
        unknown_ids = {o["order_id"] for o in self.center["unknown"]}
        self.assertIn("DD20261017004", unknown_ids)
        self.assertNotIn("DD20261017004", {o["order_id"] for o in self.center["pending"]})

    def test_text_mentions_scope_and_candidates(self):
        text = self.center["text"]
        self.assertIn("待评价候选：4 笔", text)
        self.assertIn("统计范围：最近 10 笔订单", text)
        self.assertIn("待确认", text)
        self.assertIn("官方 App", text)

    def test_empty_orders_does_not_invent(self):
        center = build_review_center([])
        self.assertEqual(center["counts"]["total"], 0)
        self.assertIn("当前返回范围内没有可处理订单", center["text"])
        self.assertEqual(center["pending"], [])

    def test_all_unknown_still_shows_review_path(self):
        """全是「待确认」时也要给出评价入口，不能掉到「查看全部订单」。"""
        center = build_review_center([{"orderId": "1", "orderStatus": "订单已完成"}])
        self.assertEqual(center["counts"]["candidates"], 1)
        self.assertIn("去官方 App 查看评价入口", center["text"])

    def test_all_reviewed_message(self):
        center = build_review_center(
            [{"orderId": "1", "orderStatus": "订单已完成", "orderStatusCode": 8}]
        )
        self.assertIn("都显示为已评价", center["text"])


class TestRewardProgress(unittest.TestCase):
    """评价兑礼档位：1 小可乐 / 2 中可乐 / 3 小薯条（默认示例，可覆盖）。"""

    def test_three_pending_hits_top_tier(self):
        result = reward_progress(3)
        self.assertIsNone(result["next"])
        self.assertEqual([x["gift"] for x in result["reached"]], ["小可乐", "中可乐", "小薯条"])
        self.assertIn("最高档", result["text"])

    def test_two_pending_next_is_fries(self):
        result = reward_progress(2)
        self.assertEqual(result["next"]["gift"], "小薯条")
        self.assertEqual(result["next"]["remaining"], 1)
        self.assertIn("再评 1 单", result["text"])

    def test_zero_pending_reports_none_reached(self):
        result = reward_progress(0)
        self.assertEqual(result["reached"], [])
        self.assertEqual(result["next"]["count"], 1)
        self.assertIn("暂时无法累计", result["text"])

    def test_custom_tiers(self):
        tiers = parse_tiers("1:小可乐,5:巨无霸")
        result = reward_progress(2, tiers)
        self.assertEqual(result["next"]["gift"], "巨无霸")
        self.assertEqual(result["next"]["remaining"], 3)

    def test_bad_tier_spec_is_ignored_not_crashing(self):
        self.assertEqual(parse_tiers("bad,0:x,2:可乐"), ((2, "可乐"),))

    def test_reward_section_appears_in_center(self):
        center = build_review_center(load_orders())
        self.assertIn("评价兑礼", center["text"])
        self.assertEqual(center["reward"]["pending"], 4)


if __name__ == "__main__":
    unittest.main()
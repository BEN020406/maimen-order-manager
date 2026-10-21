"""抽奖测试：确认门、单次闸门、超时核验、资源核验。"""

import json
import pathlib
import sys
import unittest
from datetime import datetime, timedelta

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

from common.contracts import summarize_lottery  # noqa: E402
from operations import lottery  # noqa: E402

FIXTURES = SCRIPTS_DIR / "fixtures"


def load_json(name):
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)


def stamp(delta_seconds=0):
    return (datetime.now() + timedelta(seconds=delta_seconds)).strftime("%Y-%m-%d %H:%M:%S")


class TestLotteryPreview(unittest.TestCase):
    def setUp(self):
        self.info = load_json("lottery_info.json")

    def test_preview_requires_confirmation(self):
        preview = lottery.build_draw_preview(self.info, retrieved_at=stamp())
        self.assertEqual(preview["state"], "AWAIT_CONFIRM")
        self.assertTrue(preview["allowed"])
        self.assertTrue(preview["envelope"]["requires_confirmation"])
        self.assertEqual(preview["envelope"]["module"], "lottery")

    def test_preview_states_cost_and_activity(self):
        text = lottery.build_draw_preview(self.info, retrieved_at=stamp())["text"]
        self.assertIn("本次操作：抽奖 1 次", text)
        self.assertIn("消耗：100 积分", text)
        self.assertIn("麦麦幸运抽", text)
        self.assertIn("[确认抽 1 次] [取消]", text)

    def test_preview_has_stable_idempotency_key(self):
        first = lottery.build_draw_preview(self.info, retrieved_at=stamp())
        second = lottery.build_draw_preview(self.info, retrieved_at=stamp())
        self.assertEqual(
            first["envelope"]["idempotency_key"], second["envelope"]["idempotency_key"]
        )

    def test_stale_resources_block_preview(self):
        preview = lottery.build_draw_preview(self.info, retrieved_at=stamp(-120))
        self.assertEqual(preview["state"], "STALE")
        self.assertFalse(preview["allowed"])
        self.assertIn("重新查询", preview["text"])

    def test_ineligible_blocks_preview(self):
        info = json.loads(json.dumps(self.info))
        info["data"]["drawDecision"]["resourceEligible"] = False
        preview = lottery.build_draw_preview(info, retrieved_at=stamp())
        self.assertFalse(preview["allowed"])
        self.assertIn("资源不足", preview["text"])

    def test_closed_activity_blocks_preview(self):
        info = json.loads(json.dumps(self.info))
        info["data"]["activityStatusText"] = "已结束"
        preview = lottery.build_draw_preview(info, retrieved_at=stamp())
        self.assertFalse(preview["allowed"])
        self.assertIn("没有进行中的抽奖活动", preview["text"])

    def test_overview_lists_prizes(self):
        overview = lottery.build_overview(self.info, retrieved_at=stamp())
        self.assertIn("单次消耗：100 积分", overview["text"])
        self.assertIn("免费中薯条", overview["text"])
        self.assertEqual(overview["summary"]["activity_id"], "2m2t")


class TestSingleDrawGuard(unittest.TestCase):
    def setUp(self):
        self.info = load_json("lottery_info.json")
        self.result = load_json("draw_result.json")
        self.summary = summarize_lottery(self.info)

    def test_guard_allows_only_once(self):
        guard = lottery.DrawGuard(ttl_seconds=300)
        key = lottery.idempotency_key(self.summary)
        self.assertTrue(guard.reserve(key))
        self.assertFalse(guard.reserve(key))

    def test_guard_expires_after_ttl(self):
        guard = lottery.DrawGuard(ttl_seconds=1)
        key = lottery.idempotency_key(self.summary)
        past = datetime.now() - timedelta(seconds=10)
        self.assertTrue(guard.reserve(key, now=past))
        self.assertTrue(guard.reserve(key))

    def test_second_draw_raises(self):
        guard = lottery.DrawGuard()
        key = lottery.idempotency_key(self.summary)
        lottery.interpret_draw_result(self.result, guard=guard, key=key)
        with self.assertRaises(lottery.AlreadyDrawnError):
            lottery.interpret_draw_result(self.result, guard=guard, key=key)

    def test_guard_release_allows_retry_after_no_side_effect(self):
        guard = lottery.DrawGuard()
        key = lottery.idempotency_key(self.summary)
        guard.reserve(key)
        guard.release(key)
        self.assertTrue(guard.reserve(key))


class TestDrawResult(unittest.TestCase):
    def test_win_result(self):
        result = lottery.interpret_draw_result(load_json("draw_result.json"))
        self.assertEqual(result["state"], "DONE")
        self.assertTrue(result["win"])
        self.assertIn("中奖", result["text"])
        self.assertIn("剩余积分 220", result["text"])

    def test_lose_result(self):
        payload = {"data": {"status": {"code": "SUCCESS"}, "win": False, "consumePoint": 100}}
        result = lottery.interpret_draw_result(payload)
        self.assertIn("未中奖", result["text"])

    def test_draw_failed(self):
        payload = {"data": {"status": {"code": "DRAW_FAILED", "message": "很抱歉，活动已结束!"}}}
        result = lottery.interpret_draw_result(payload)
        self.assertEqual(result["state"], "FAILED")
        self.assertFalse(result["success"])
        self.assertIn("活动已结束", result["text"])

    def test_timeout_goes_to_verify_without_retry(self):
        result = lottery.handle_timeout("ReadTimeout")
        self.assertEqual(result["state"], "VERIFY")
        self.assertFalse(result["retry_allowed"])
        self.assertIn("避免重复操作", result["text"])
        self.assertEqual(result["next_action"], "查询状态")

    def test_no_execute_after_timeout(self):
        """状态机层面禁止从 VERIFY 直接回到 EXECUTE。"""
        from common import state_machine as sm

        self.assertFalse(sm.can_transition(sm.VERIFY, sm.EXECUTE))
        self.assertFalse(sm.can_transition(sm.FAILED, sm.EXECUTE))

    def test_verify_consumption_consistent(self):
        before = summarize_lottery(load_json("lottery_info.json"))
        after = {"data": {"availablePoint": 220, "availableTimes": 1}}
        check = lottery.verify_consumption(before, after)
        self.assertTrue(check["consistent"])
        self.assertEqual(check["deltas"]["point_delta"], 100)

    def test_history_renders(self):
        history = lottery.build_history(load_json("my_prizes.json"))
        self.assertEqual(history["count"], 2)
        self.assertIn("免费中薯条", history["text"])


if __name__ == "__main__":
    unittest.main()

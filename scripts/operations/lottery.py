"""抽奖管家：查询 → 预览 → 单次确认 → 单次执行 → 结果核验。

不可妥协的三条：
1. 只允许用户确认后的**单次** draw-lottery。代码里没有「批量」「循环」「抽到完」任何入口。
2. 调用超时/结果未知 → 进入 VERIFY，只允许再查 query-lottery-info 确认结果，
   绝不重新 draw-lottery（重试会二次扣资源）。
3. 执行前必须刷新活动信息（TTL 30 秒）；资源不足直接拦下。

DrawGuard 说明：闸门是**进程内存**实现，不落盘（符合「不持久化会话数据」）。
跨进程的防重复由 SKILL.md 的硬性纪律承担：一轮对话最多一次 draw-lottery。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from common import state_machine as sm
from common.contracts import (
    LotterySummary,
    build_envelope,
    pick,
    pick_bool,
    summarize_lottery,
    to_text,
)
from common.redact import redact_text

CANCELLED_ACTIVITY_WORDS = ("已结束", "未开始", "暂停", "关闭", "已下线")
DRAW_FAILED_CODES = ("DRAW_FAILED",)


class AlreadyDrawnError(RuntimeError):
    """同一幂等键在闸门有效期内重复执行。"""


@dataclass
class DrawGuard:
    """单次执行闸门：同一 idempotency_key 在 ttl 内只放行一次。"""

    ttl_seconds: int = 300
    _seen: Dict[str, datetime] = field(default_factory=dict)

    def _purge(self, now: datetime) -> None:
        expired = [
            key
            for key, stamp in self._seen.items()
            if (now - stamp).total_seconds() > self.ttl_seconds
        ]
        for key in expired:
            self._seen.pop(key, None)

    def reserve(self, key: str, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now()
        self._purge(now)
        if key in self._seen:
            return False
        self._seen[key] = now
        return True

    def require(self, key: str, now: Optional[datetime] = None) -> None:
        if not self.reserve(key, now):
            raise AlreadyDrawnError("该次抽奖已经执行过，拒绝重复扣资源")

    def release(self, key: str) -> None:
        """仅在确认「调用未发出、资源未消耗」时释放。"""
        self._seen.pop(key, None)


def idempotency_key(summary: LotterySummary) -> str:
    """由活动 + 成本派生，同一确认动作得到稳定键。"""
    seed = f"{summary.activity_id or 'unknown'}|{summary.draw_cost}|{summary.cost_unit}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def _activity_closed(status: str) -> bool:
    return any(word in status for word in CANCELLED_ACTIVITY_WORDS)


def _resource_text(summary: LotterySummary) -> str:
    parts = []
    if summary.available_point is not None:
        parts.append(f"积分 {summary.available_point}")
    if summary.available_count is not None:
        parts.append(f"次数 {summary.available_count}")
    return " / ".join(parts) if parts else "未知"


def _prize_lines(summary: LotterySummary, limit: int = 6) -> list:
    lines = []
    for prize in summary.prizes[:limit]:
        suffix = f"（{prize['type_text']}）" if prize.get("type_text") else ""
        lines.append(f"- {prize['name']}{suffix}")
    if len(summary.prizes) > limit:
        lines.append(f"- 等共 {len(summary.prizes)} 种奖品")
    return lines


def build_overview(
    raw: Any, retrieved_at: Optional[str] = None, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """活动概览（不含任何副作用）。"""
    summary = summarize_lottery(raw, retrieved_at)
    staleness = sm.staleness_report(summary.retrieved_at, sm.TTL_LOTTERY, now)

    closed = _activity_closed(summary.status)
    lines = [
        f"抽奖活动：{summary.activity_name or '未知'}（{summary.status}）",
    ]
    if summary.draw_cost is not None:
        lines.append(f"单次消耗：{summary.draw_cost} {summary.cost_unit}")
    lines.append(f"可用资源：{_resource_text(summary)}")
    if summary.reason:
        lines.append(f"参与条件：{summary.reason}")
    if summary.prizes:
        lines.append("")
        lines.append("奖品：")
        lines.extend(_prize_lines(summary))

    if closed:
        lines.append("")
        lines.append("当前没有进行中的抽奖活动。")
        state = sm.DONE
    elif summary.eligible is False:
        lines.append("")
        lines.append("当前资源不足以抽奖。")
        state = sm.DONE
    else:
        state = sm.STALE if staleness["is_stale"] else sm.PREVIEW

    return {
        "state": state,
        "summary": summary.to_dict(),
        "staleness": staleness,
        "closed": closed,
        "text": "\n".join(lines),
    }


def build_draw_preview(
    raw: Any, retrieved_at: Optional[str] = None, now: Optional[datetime] = None
) -> Dict[str, Any]:
    """生成单次抽奖预览与确认门。不执行任何外部动作。"""
    summary = summarize_lottery(raw, retrieved_at)
    staleness = sm.staleness_report(summary.retrieved_at, sm.TTL_LOTTERY, now)
    key = idempotency_key(summary)

    if _activity_closed(summary.status):
        return {
            "state": sm.DONE,
            "allowed": False,
            "summary": summary.to_dict(),
            "envelope": None,
            "reason": "当前没有进行中的抽奖活动。",
            "text": "当前没有进行中的抽奖活动。\n先查询活动状态，不要发起抽奖。",
        }

    if summary.eligible is False:
        return {
            "state": sm.DONE,
            "allowed": False,
            "summary": summary.to_dict(),
            "envelope": None,
            "reason": "当前资源不足以抽奖。",
            "text": "当前资源不足以抽奖。\n可以先看看历史奖品记录。",
        }

    if staleness["is_stale"]:
        return {
            "state": sm.STALE,
            "allowed": False,
            "summary": summary.to_dict(),
            "envelope": None,
            "reason": "抽奖资源数据超过 30 秒，必须重新查询后再确认。",
            "text": "抽奖资源数据已过期（超过 30 秒）。\n请先重新查询活动信息，再决定是否抽奖。",
            "staleness": staleness,
        }

    prize_names = [p["name"] for p in summary.prizes]
    prize_hint = "、".join(prize_names[:6]) if prize_names else "未知"
    lines = [
        "本次操作：抽奖 1 次",
    ]
    if summary.draw_cost is not None:
        lines.append(f"消耗：{summary.draw_cost} {summary.cost_unit}")
    else:
        lines.append("消耗：消耗规则未知（接口未返回）")
    lines.append(f"抽奖活动：{summary.activity_name or '未知'}")
    lines.append(f"可用资源：{_resource_text(summary)}")
    lines.append(f"可能奖品：{prize_hint}")
    lines.append("")
    lines.append("[确认抽 1 次] [取消]")

    envelope = build_envelope(
        module="lottery",
        action="draw-lottery 1 次",
        preview="\n".join(lines),
        state=sm.AWAIT_CONFIRM,
        requires_confirmation=True,
        idempotency_key=key,
    )
    return {
        "state": sm.AWAIT_CONFIRM,
        "allowed": True,
        "summary": summary.to_dict(),
        "envelope": envelope,
        "reason": None,
        "text": "\n".join(lines),
        "staleness": staleness,
    }


def interpret_draw_result(
    raw: Any,
    guard: Optional[DrawGuard] = None,
    key: Optional[str] = None,
    reserve: bool = True,
) -> Dict[str, Any]:
    """解析 draw-lottery 返回；同时充当单次执行闸门的落点。

    reserve=True 时，同一 key 第二次调用会抛 AlreadyDrawnError。
    """
    if guard is not None and key:
        if reserve:
            guard.require(key)

    body = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else raw
    body = body if isinstance(body, dict) else {}

    status_node = body.get("status") if isinstance(body.get("status"), dict) else {}
    code = to_text(pick(status_node, ("code", "statusCode"))) or ""
    message = to_text(pick(status_node, ("message", "msg"))) or ""

    win = pick_bool(body, ("win", "isWin", "won"))
    prizes = []
    for entry in body.get("prizes") or []:
        if isinstance(entry, dict):
            prizes.append(
                {
                    "name": to_text(entry.get("name")) or "未知",
                    "type_text": to_text(pick(entry, ("typeText", "type"))),
                    "valid_date": to_text(pick(entry, ("validDateInfo", "validDate"))),
                }
            )
    consumed = body.get("consumePoint")
    remain_point = body.get("remainPoint")
    remain_chance = body.get("remainChance")

    failed = code in DRAW_FAILED_CODES

    if failed:
        text = f"抽奖未成功：{message or '接口返回失败'}"
        if message and "已结束" in message:
            text += "\n活动可能已结束，请重新查询活动状态。"
        return {
            "state": sm.FAILED,
            "success": False,
            "win": None,
            "prizes": [],
            "consumed": consumed,
            "remain_point": remain_point,
            "remain_chance": remain_chance,
            "text": text,
            "next_action": "重新查询活动状态",
        }

    lines = []
    if win is True:
        names = "、".join(p["name"] for p in prizes) or "奖品信息未返回"
        lines.append(f"抽奖结果：中奖 —— {names}")
    elif win is False:
        lines.append("抽奖结果：未中奖")
    else:
        lines.append("抽奖结果：接口未返回是否中奖")

    if consumed is not None:
        lines.append(f"本次消耗：{consumed} 积分")
    remain = []
    if remain_point is not None:
        remain.append(f"剩余积分 {remain_point}")
    if remain_chance is not None:
        remain.append(f"剩余次数 {remain_chance}")
    if remain:
        lines.append("当前资源：" + " / ".join(remain))
    if prizes:
        for prize in prizes:
            if prize.get("valid_date"):
                lines.append(f"有效期：{prize['valid_date']}")
                break

    return {
        "state": sm.DONE if win is not None else sm.VERIFY,
        "success": True,
        "win": win,
        "prizes": prizes,
        "consumed": consumed,
        "remain_point": remain_point,
        "remain_chance": remain_chance,
        "text": "\n".join(lines),
        "next_action": None if win is not None else "查询状态",
    }


def handle_timeout(error: Any = None) -> Dict[str, Any]:
    """调用超时/网络异常：只允许转入状态核验。"""
    detail = redact_text(error) if error else ""
    lines = [
        "暂时无法确认结果，正在避免重复操作。",
        "请先查询抽奖/奖品记录确认本次是否已扣资源，不要再次发起抽奖。",
    ]
    if detail:
        lines.append(f"错误摘要：{detail}")
    return {
        "state": sm.VERIFY,
        "retry_allowed": False,
        "text": "\n".join(lines),
        "next_action": "查询状态",
        "verify_tool": "query-lottery-info / query-my-prizes",
    }


def verify_consumption(
    before: Optional[LotterySummary],
    after_raw: Any,
) -> Dict[str, Any]:
    """执行后核验：资源变化是否与本次消耗一致。"""
    after = summarize_lottery(after_raw)
    deltas: Dict[str, Any] = {}
    consistent = True

    if before is not None:
        if before.available_point is not None and after.available_point is not None:
            delta = before.available_point - after.available_point
            deltas["point_delta"] = delta
            if delta < 0:
                consistent = False
        if before.available_count is not None and after.available_count is not None:
            deltas["count_delta"] = before.available_count - after.available_count

    return {
        "state": sm.DONE if consistent else sm.STALE,
        "consistent": consistent,
        "deltas": deltas,
        "after": after.to_dict(),
        "note": "资源变化与预期一致" if consistent else "资源出现异常增加，请以官方 App 记录为准",
    }


def build_history(raw: Any, limit: int = 5) -> Dict[str, Any]:
    """query-my-prizes 的展示（只读）。"""
    body = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else raw
    body = body if isinstance(body, dict) else {}
    entries = body.get("prizes") or []
    records = []
    for entry in entries[:limit]:
        if not isinstance(entry, dict):
            continue
        records.append(
            {
                "name": to_text(entry.get("name")) or "未知",
                "record_time": to_text(pick(entry, ("recordTime", "createTime"))),
                "status_text": to_text(pick(entry, ("statusText", "status"))),
                "valid_hint": to_text(pick(entry, ("timeRemindText", "validDateInfo"))),
            }
        )
    if not records:
        text = "暂无奖品记录。"
    else:
        lines = [f"最近的奖品（{len(records)} 条）："]
        for item in records:
            when = (item["record_time"] or "")[:10]
            status = f" {item['status_text']}" if item["status_text"] else ""
            lines.append(f"- {when}  {item['name']}{status}")
        text = "\n".join(lines)
    return {"count": len(records), "records": records, "text": text}

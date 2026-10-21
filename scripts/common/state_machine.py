"""统一状态机与数据新鲜度（TTL）判定。

流程：DISCOVER → NORMALIZE → PREVIEW → AWAIT_CONFIRM → EXECUTE | HANDOFF
      → VERIFY → DONE
异常：UNSUPPORTED / STALE / FAILED / CANCELLED

纪律：副作用动作（draw-lottery）在 UNKNOWN 结果下只能回到 VERIFY，
不得从 FAILED / VERIFY 直接重新 EXECUTE —— 这是「超时不重复扣资源」的机器保障。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional, Set

# 状态常量
DISCOVER = "DISCOVER"
NORMALIZE = "NORMALIZE"
PREVIEW = "PREVIEW"
AWAIT_CONFIRM = "AWAIT_CONFIRM"
EXECUTE = "EXECUTE"
HANDOFF = "HANDOFF"
VERIFY = "VERIFY"
DONE = "DONE"
UNSUPPORTED = "UNSUPPORTED"
STALE = "STALE"
FAILED = "FAILED"
CANCELLED = "CANCELLED"

ALL_STATES = (
    DISCOVER,
    NORMALIZE,
    PREVIEW,
    AWAIT_CONFIRM,
    EXECUTE,
    HANDOFF,
    VERIFY,
    DONE,
    UNSUPPORTED,
    STALE,
    FAILED,
    CANCELLED,
)

# 允许的迁移
TRANSITIONS: Dict[str, Set[str]] = {
    DISCOVER: {NORMALIZE, UNSUPPORTED, FAILED, CANCELLED},
    NORMALIZE: {PREVIEW, STALE, FAILED, UNSUPPORTED, DISCOVER},
    PREVIEW: {AWAIT_CONFIRM, HANDOFF, CANCELLED, STALE, FAILED},
    AWAIT_CONFIRM: {EXECUTE, HANDOFF, CANCELLED, STALE},
    EXECUTE: {VERIFY, DONE, FAILED},
    HANDOFF: {DONE, CANCELLED},
    VERIFY: {DONE, FAILED, STALE},
    DONE: set(),
    UNSUPPORTED: {DISCOVER, DONE, CANCELLED},
    STALE: {DISCOVER, CANCELLED},
    # 失败后只允许重新查询（DISCOVER）或状态核验（VERIFY），不允许直接再执行副作用
    FAILED: {DISCOVER, VERIFY, CANCELLED},
    CANCELLED: set(),
}

TERMINAL_STATES = {DONE, CANCELLED, UNSUPPORTED}

# 建议 TTL（秒）
TTL_ORDER = 300
TTL_LOTTERY = 30
TTL_LOTTERY_RESULT = 0  # 执行后立即核验

STATE_LABELS = {
    DISCOVER: "查询中",
    NORMALIZE: "整理中",
    PREVIEW: "待确认",
    AWAIT_CONFIRM: "等待确认",
    EXECUTE: "执行中",
    HANDOFF: "需在官方 App 完成",
    VERIFY: "核验中",
    DONE: "已完成",
    UNSUPPORTED: "能力不可用",
    STALE: "数据已过期",
    FAILED: "执行失败",
    CANCELLED: "已取消",
}


class InvalidTransition(Exception):
    """非法的状态迁移。"""


def can_transition(current: str, target: str) -> bool:
    if current not in TRANSITIONS or target not in ALL_STATES:
        return False
    return target in TRANSITIONS[current]


def transition(current: str, target: str) -> str:
    if not can_transition(current, target):
        raise InvalidTransition(f"不允许的状态迁移：{current} → {target}")
    return target


def next_state_for_result(result: str) -> str:
    """按执行结果决定下一态：ok / unknown / failed / cancelled。"""
    return {
        "ok": DONE,
        "unknown": VERIFY,
        "failed": FAILED,
        "cancelled": CANCELLED,
    }.get(result, VERIFY)


def parse_stamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def age_seconds(retrieved_at: Optional[str], now: Optional[datetime] = None) -> Optional[float]:
    stamp = parse_stamp(retrieved_at)
    if stamp is None:
        return None
    current = now or datetime.now()
    return max(0.0, (current - stamp).total_seconds())


def is_stale(
    retrieved_at: Optional[str], ttl: int, now: Optional[datetime] = None
) -> bool:
    """拿不到时间戳时按「过期」处理，宁可重新查询。"""
    age = age_seconds(retrieved_at, now)
    if age is None:
        return True
    return age > ttl


def staleness_report(
    retrieved_at: Optional[str], ttl: int, now: Optional[datetime] = None
) -> Dict[str, object]:
    age = age_seconds(retrieved_at, now)
    stale = is_stale(retrieved_at, ttl, now)
    return {
        "retrieved_at": retrieved_at,
        "ttl_seconds": ttl,
        "age_seconds": None if age is None else int(age),
        "is_stale": stale,
        "state": STALE if stale else PREVIEW,
        "label": "数据已过期，需要重新查询" if stale else "数据有效",
    }


def all_states() -> Iterable[str]:
    return ALL_STATES

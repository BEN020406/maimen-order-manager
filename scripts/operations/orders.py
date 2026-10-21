"""待评价订单中心。

规则（严格对齐交付稿 8.1）：
1. 调用 order-list 取最近订单；
2. 保留已完成订单；
3. orderStatusCode=8 → 已评价；
4. 已完成且状态不是 8 → 可能待评价；
5. 取消 / 待支付 / 进行中 → 不计入待评价数量；
6. 缺少评价状态字段 → 显示「无法确认评价状态」，绝不自动归为未评价。

统计范围只承诺接口实际返回的订单数（官方 order-list 最多返回最近 10 笔）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from common.contracts import (
    OrderSummary,
    classify_review,
    format_amount,
    format_date,
    normalize_orders,
    parse_time,
)

APP_REVIEW_HINT = "麦当劳官方 App → 我的 → 订单 → 选择该订单 → 评价"
SCOPE_NOTE_TEMPLATE = "最近 {n} 笔订单"

# 评价兑礼档位：各门店规则不同，这里只是默认示例，可用 --tiers 覆盖
DEFAULT_REWARD_TIERS = ((1, "小可乐"), (2, "中可乐"), (3, "小薯条"))
REWARD_NOTE = "档位规则因门店而异，以门店为准；评价请基于真实用餐体验。"


def parse_tiers(spec: str) -> tuple:
    """把 "1:小可乐,2:中可乐,3:小薯条" 解析成 ((1,'小可乐'), ...)。"""
    tiers = []
    for chunk in (spec or "").split(","):
        if ":" not in chunk:
            continue
        count_text, _, gift = chunk.partition(":")
        try:
            count = int(count_text.strip())
        except ValueError:
            continue
        if count <= 0 or not gift.strip():
            continue
        tiers.append((count, gift.strip()))
    return tuple(sorted(tiers))


def reward_progress(pending_count: int, tiers: Optional[tuple] = None) -> Dict[str, Any]:
    """根据待评价单数，算出已达成的档位与距离下一档还差几单。"""
    tiers = tuple(sorted(tiers or DEFAULT_REWARD_TIERS))
    reached = [(count, gift) for count, gift in tiers if pending_count >= count]
    upcoming = [(count, gift) for count, gift in tiers if pending_count < count]
    next_tier = None
    if upcoming:
        count, gift = upcoming[0]
        next_tier = {"count": count, "gift": gift, "remaining": count - pending_count}

    if not pending_count:
        text = "当前没有待评价订单，暂时无法累计评价档位。"
    elif next_tier:
        best = f"已达成 {reached[-1][0]} 好评（{reached[-1][1]}）" if reached else "尚未达成任何档位"
        text = f"{best}；再评 {next_tier['remaining']} 单可达 {next_tier['count']} 好评（{next_tier['gift']}）。"
    else:
        top = tiers[-1] if tiers else (0, "")
        text = f"已达成最高档 {top[0]} 好评（{top[1]}）。"

    return {
        "pending": pending_count,
        "tiers": [{"count": c, "gift": g} for c, g in tiers],
        "reached": [{"count": c, "gift": g} for c, g in reached],
        "next": next_tier,
        "text": text,
        "note": REWARD_NOTE,
    }


def _sort_key(order: OrderSummary):
    parsed = parse_time(order.created_at)
    return parsed or datetime.min


def _order_line(order: OrderSummary) -> str:
    store = order.store_name or "门店未知"
    date = format_date(order.created_at)
    amount = format_amount(order.paid_amount)
    return f"{date}  {store}  {amount}  {order.review_label}"


def build_review_center(
    raw_orders: Any,
    retrieved_at: Optional[str] = None,
    limit: Optional[int] = None,
    tiers: Optional[tuple] = None,
) -> Dict[str, Any]:
    """生成待评价中心的数据与文本卡片。"""
    orders = normalize_orders(raw_orders, source="order-list", retrieved_at=retrieved_at)
    if limit is not None:
        orders = orders[:limit]
    for order in orders:
        order.review_state, order.review_label, order.review_reason = classify_review(order)

    orders.sort(key=_sort_key, reverse=True)

    pending = [o for o in orders if o.review_state == "likely_pending"]
    reviewed = [o for o in orders if o.review_state == "reviewed"]
    unknown = [o for o in orders if o.review_state == "unknown"]
    excluded = [o for o in orders if o.review_state == "not_eligible"]

    # 真实接口不返回评价状态，因此「待确认」的订单也是候选：
    # 是否评过由用户在工具里本地标记（只存订单号哈希），不由接口猜测。
    candidates = sorted(pending + unknown, key=_sort_key, reverse=True)

    total = len(orders)
    scope_note = SCOPE_NOTE_TEMPLATE.format(n=total) if total else "本次未返回订单"

    lines: List[str] = []
    if total == 0:
        lines.append("当前返回范围内没有可处理订单。")
    elif candidates:
        lines.append(f"待评价候选：{len(candidates)} 笔")
        lines.append(f"统计范围：{scope_note}")
        lines.append("")
        lines.extend(_order_line(order) for order in candidates)
    elif reviewed:
        lines.append("当前查询到的订单都显示为已评价。")
        lines.append(f"统计范围：{scope_note}")
    else:
        lines.append("当前返回范围内没有可处理订单。")
        lines.append(f"统计范围：{scope_note}")

    if unknown:
        lines.append("")
        lines.append(
            f"其中 {len(unknown)} 笔接口未返回评价状态，标为「待确认」；评过后请在清点里点「已评过」。"
        )
    if excluded:
        lines.append(f"另有 {len(excluded)} 笔未完成或已取消订单未纳入统计。")

    reward = reward_progress(len(candidates), tiers)
    if candidates:
        lines.append("")
        lines.append(f"评价兑礼：{reward['text']}")
        lines.append(f"（按 {len(candidates)} 笔待确认估算，标记「已评过」后会重算）")

    lines.append("")
    if candidates:
        lines.append("去官方 App 查看评价入口 →")
        lines.append(f"路径：{APP_REVIEW_HINT}")
    else:
        lines.append("查看全部订单 →")

    result = {
        "state": "PREVIEW",
        "scope": {
            "total_orders": total,
            "scope_note": scope_note,
            "retrieved_at": retrieved_at or (orders[0].retrieved_at if orders else None),
            "source": "order-list",
        },
        "counts": {
            "total": total,
            "candidates": len(candidates),
            "likely_pending": len(pending),
            "reviewed": len(reviewed),
            "unknown": len(unknown),
            "excluded": len(excluded),
        },
        "candidates": [o.to_dict() for o in candidates],
        "pending": [o.to_dict() for o in pending],
        "reviewed": [o.to_dict() for o in reviewed],
        "unknown": [o.to_dict() for o in unknown],
        "excluded": [o.to_dict() for o in excluded],
        "next_action": {
            "label": "去官方 App 查看评价入口" if candidates else "查看全部订单",
            "path": APP_REVIEW_HINT,
        },
        "reward": reward,
        "empty_reason": None if total else "当前返回范围内没有可处理订单。",
        "text": "\n".join(lines),
    }
    return result


def review_summary_line(center: Dict[str, Any]) -> str:
    """首页卡片用的一句话摘要。"""
    counts = center["counts"]
    if counts["total"] == 0:
        return "暂无可处理订单"
    if counts.get("candidates"):
        return f"{counts['candidates']} 笔"
    return "0 笔"

"""发票助手：真实订单筛选 + 开票资料校验 + 官方 App 交接。

边界：
- 只筛选真实存在的订单，金额/城市/门店全部来自订单返回值；
- 不修改金额、不伪造城市、不生成订单；
- 当前 MCP 未公开 issue-invoice，因此**不提交发票**，只产出清单并交接官方 App；
- 税号/邮箱只在当前会话内存中使用，输出一律脱敏。
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from itertools import combinations
from typing import Any, Dict, List, Optional, Sequence

from common.contracts import (
    CANCELLED_WORDS,
    COMPLETED_WORDS,
    OrderSummary,
    format_amount,
    format_date,
    normalize_orders,
    parse_time,
    to_amount,
)
from common.redact import mask_email, mask_tax_id

PAID_WORDS = ("已支付", "支付成功", "已付款", "付款成功", "支付完成")
APP_INVOICE_HINT = "麦当劳官方 App / 小程序 → 我的 → 订单 → 选择订单 → 申请开票"
USCC_CHARSET = "0123456789ABCDEFGHJKLMNPQRTUWXY"
USCC_WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")

# 报销凑单：订单数超过该值时改用贪心，避免组合爆炸
MAX_EXACT_SUBSET = 16
COMMON_TARGETS = (50, 100)


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def plan_reimbursement(
    candidates: Sequence[Dict[str, Any]], target: float
) -> Dict[str, Any]:
    """从真实候选订单中挑一组凑到 target 元，优先超出最少，其次单数最少。

    只做「已有订单如何组合」，不新增、不修改任何订单金额。
    """
    goal = _money(target)
    rows = []
    for order in candidates:
        amount = order.get("paid_amount")
        if amount is None:
            continue
        rows.append((order.get("order_id"), _money(amount)))

    total = sum((amount for _, amount in rows), Decimal("0.00"))

    if not rows:
        return {
            "target": float(goal),
            "reachable": False,
            "available_total": 0.0,
            "selected": [],
            "selected_total": 0.0,
            "overshoot": 0.0,
            "gap": float(goal),
            "text": f"报销门槛 ¥{goal:.2f}：当前没有可开票订单。",
        }

    if total < goal:
        gap = goal - total
        return {
            "target": float(goal),
            "reachable": False,
            "available_total": float(total),
            "selected": [],
            "selected_total": float(total),
            "overshoot": 0.0,
            "gap": float(gap),
            "text": (
                f"报销门槛 ¥{goal:.2f}：当前候选合计 ¥{total:.2f}，还差 ¥{gap:.2f}。"
            ),
        }

    best: Optional[tuple] = None  # (overshoot, size, ids, amount)
    count = len(rows)
    if count <= MAX_EXACT_SUBSET:
        for size in range(1, count + 1):
            for combo in combinations(rows, size):
                amount = sum((item[1] for item in combo), Decimal("0.00"))
                if amount < goal:
                    continue
                overshoot = amount - goal
                if best is None or (overshoot, size) < (best[0], best[1]):
                    best = (overshoot, size, [item[0] for item in combo], amount)
    else:
        # 订单过多时按金额降序贪心，先满足门槛，再尝试回退
        picked: List[tuple] = []
        running = Decimal("0.00")
        for row in sorted(rows, key=lambda item: item[1], reverse=True):
            if running >= goal:
                break
            picked.append(row)
            running += row[1]
        best = (running - goal, len(picked), [item[0] for item in picked], running)

    overshoot, size, ids, amount = best
    return {
        "target": float(goal),
        "reachable": True,
        "available_total": float(total),
        "selected": ids,
        "selected_total": float(amount),
        "overshoot": float(overshoot),
        "gap": 0.0,
        "text": (
            f"报销门槛 ¥{goal:.2f}：选 {size} 笔，合计 ¥{amount:.2f}"
            + (f"，超出 ¥{overshoot:.2f}。" if overshoot > 0 else "，刚好达标。")
        ),
    }


def is_invoiceable(order: OrderSummary) -> bool:
    """订单状态必须为已支付或已完成，且未取消。"""
    text = order.status_label or ""
    if any(word in text for word in CANCELLED_WORDS):
        return False
    if any(word in text for word in PAID_WORDS):
        return True
    return any(word in text for word in COMPLETED_WORDS)


def _city_matches(order: OrderSummary, city: str) -> bool:
    if not order.store_city:
        return False
    return city.strip() in order.store_city or order.store_city in city.strip()


def _sort_key(order: OrderSummary):
    return parse_time(order.created_at) or datetime.min


def _in_range(order: OrderSummary, date_from: Optional[str], date_to: Optional[str]) -> bool:
    stamp = parse_time(order.created_at)
    if stamp is None:
        return date_from is None and date_to is None
    if date_from:
        start = parse_time(date_from)
        if start and stamp < start.replace(hour=0, minute=0, second=0):
            return False
    if date_to:
        end = parse_time(date_to)
        if end and stamp > end.replace(hour=23, minute=59, second=59):
            return False
    return True


def filter_candidates(
    raw_orders: Any,
    city: Optional[str] = None,
    store: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    retrieved_at: Optional[str] = None,
) -> Dict[str, Any]:
    """按城市/门店/日期/金额/状态筛选可开票候选订单。"""
    orders = normalize_orders(raw_orders, source="order-list", retrieved_at=retrieved_at)
    candidates: List[OrderSummary] = []
    excluded: List[Dict[str, Any]] = []
    city_unknown = 0

    for order in orders:
        if not is_invoiceable(order):
            excluded.append(
                {
                    "order_id": order.order_id,
                    "reason": f"订单状态为「{order.status_label or '未知'}」，非已支付或已完成",
                }
            )
            continue
        if store and store not in (order.store_name or ""):
            excluded.append({"order_id": order.order_id, "reason": "门店不匹配"})
            continue
        if city:
            if not order.store_city:
                city_unknown += 1
                excluded.append(
                    {
                        "order_id": order.order_id,
                        "reason": "订单无城市字段，无法按城市筛选（不做猜测归类）",
                    }
                )
                continue
            if not _city_matches(order, city):
                excluded.append({"order_id": order.order_id, "reason": "城市不匹配"})
                continue
        if not _in_range(order, date_from, date_to):
            excluded.append({"order_id": order.order_id, "reason": "不在指定日期范围"})
            continue
        limit_min = to_amount(min_amount) if min_amount is not None else None
        limit_max = to_amount(max_amount) if max_amount is not None else None
        if limit_min is not None and (
            order.paid_amount is None or order.paid_amount < limit_min
        ):
            excluded.append({"order_id": order.order_id, "reason": "低于金额下限或金额未知"})
            continue
        if limit_max is not None and (
            order.paid_amount is None or order.paid_amount > limit_max
        ):
            excluded.append({"order_id": order.order_id, "reason": "高于金额上限或金额未知"})
            continue
        candidates.append(order)

    candidates.sort(key=_sort_key, reverse=True)

    total = sum(
        (order.paid_amount for order in candidates if order.paid_amount is not None),
        Decimal("0.00"),
    )
    amount_missing = [o.order_id for o in candidates if o.paid_amount is None]
    inferred_city = [o.order_id for o in candidates if o.city_source == "store_name"]

    return {
        "filters": {
            "city": city,
            "store": store,
            "date_from": date_from,
            "date_to": date_to,
            "min_amount": min_amount,
            "max_amount": max_amount,
        },
        "candidates": [o.to_dict() for o in candidates],
        "excluded": excluded,
        "count": len(candidates),
        "total_amount": float(total),
        "amount_missing": amount_missing,
        "city_inferred": inferred_city,
        "city_unknown_excluded": city_unknown,
        "source_scope": f"最近 {len(orders)} 笔订单",
    }


def validate_uscc(tax_id: str) -> Dict[str, Any]:
    """统一社会信用代码校验（GB 32100-2015）。返回问题清单，不阻断流程。"""
    text = re.sub(r"\s+", "", tax_id or "").upper()
    issues: List[str] = []
    if len(text) != 18:
        issues.append(f"统一社会信用代码应为 18 位，当前 {len(text)} 位，请人工检查")
        return {"valid": False, "issues": issues, "normalized": text}
    bad = [ch for ch in text if ch not in USCC_CHARSET]
    if bad:
        issues.append(f"包含非法字符：{''.join(sorted(set(bad)))}（不含 I/O/S/V/Z）")
        return {"valid": False, "issues": issues, "normalized": text}
    total = sum(USCC_CHARSET.index(ch) * weight for ch, weight in zip(text[:17], USCC_WEIGHTS))
    check = 31 - (total % 31)
    if check == 31:
        check = 0
    expected = USCC_CHARSET[check]
    if expected != text[17]:
        issues.append(f"校验位不匹配（期望 {expected}），请人工核对")
        return {"valid": False, "issues": issues, "normalized": text}
    return {"valid": True, "issues": issues, "normalized": text}


def validate_profile(
    company_name: Optional[str],
    tax_id: Optional[str],
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """校验开票资料。errors 会导致无法出清单，warnings 仅提示。"""
    errors: List[str] = []
    warnings: List[str] = []

    name = (company_name or "").strip()
    if not name:
        errors.append("公司抬头不能为空")

    tax = (tax_id or "").strip()
    if not tax:
        errors.append("统一社会信用代码不能为空")
        uscc = {"valid": False, "issues": [], "normalized": ""}
    else:
        uscc = validate_uscc(tax)
        warnings.extend(uscc["issues"])

    mail = (email or "").strip()
    if mail and not EMAIL_PATTERN.match(mail):
        warnings.append("接收邮箱格式可能不正确，请人工检查")

    return {
        "company_name": name,
        "tax_id_masked": mask_tax_id(tax),
        "email_masked": mask_email(mail) if mail else None,
        "errors": errors,
        "warnings": warnings,
        "ok": not errors,
        "uscc_valid": uscc["valid"],
        "email_present": bool(mail),
    }


def build_invoice_card(
    raw_orders: Any,
    profile: Optional[Dict[str, Any]] = None,
    city: Optional[str] = None,
    store: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    retrieved_at: Optional[str] = None,
    target: Optional[float] = None,
) -> Dict[str, Any]:
    """生成候选清单 + 资料校验 + 官方 App 交接卡片。"""
    result = filter_candidates(
        raw_orders,
        city=city,
        store=store,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        retrieved_at=retrieved_at,
    )

    profile = profile or {}
    check = validate_profile(
        profile.get("company_name"), profile.get("tax_id"), profile.get("email")
    )
    reimbursement = plan_reimbursement(result["candidates"], target) if target else None

    lines: List[str] = []
    scope_word = f"{city}" if city else ""
    if result["count"]:
        lines.append(
            f"找到 {result['count']} 笔{scope_word}订单，实付合计 {format_amount(Decimal(str(result['total_amount'])))}"
        )
        lines.append("")
        for order in result["candidates"]:
            mark = "☑"
            amount = (
                format_amount(Decimal(str(order["paid_amount"])))
                if order["paid_amount"] is not None
                else "金额未知"
            )
            lines.append(
                f"{mark} {format_date(order['created_at'])}  {order['store_name']}  {amount}"
            )
    else:
        lines.append("当前筛选范围内没有可开票订单。")
        lines.append(f"统计范围：{result['source_scope']}")

    if result["amount_missing"]:
        lines.append("")
        lines.append(f"注意：{len(result['amount_missing'])} 笔订单接口未返回金额，合计不含这些订单。")
    if result["city_inferred"]:
        lines.append(
            f"注意：{len(result['city_inferred'])} 笔订单的城市按门店名推断，非接口字段，请以官方 App 为准。"
        )
    if result["city_unknown_excluded"]:
        lines.append(
            f"注意：{result['city_unknown_excluded']} 笔订单无城市字段，未纳入本次城市筛选。"
        )

    if reimbursement:
        lines.append("")
        lines.append(reimbursement["text"])

    lines.append("")
    lines.append(f"抬头：{check['company_name'] or '未填写'}")
    lines.append(f"税号：{check['tax_id_masked']}")
    if check["email_present"]:
        lines.append(f"邮箱：{check['email_masked']}")
    for warning in check["warnings"]:
        lines.append(f"提示：{warning}")
    for error in check["errors"]:
        lines.append(f"待补：{error}")

    lines.append("")
    lines.append("下一步：打开麦当劳官方 App，在对应订单中提交开票。")
    lines.append(f"路径：{APP_INVOICE_HINT}")
    lines.append("说明：本工具不代替你提交发票，也不会修改任何订单信息。")

    ok = bool(result["count"]) and check["ok"]
    return {
        "state": "HANDOFF" if result["count"] else "DONE",
        "filters": result["filters"],
        "candidates": result["candidates"],
        "excluded": result["excluded"][:20],
        "count": result["count"],
        "total_amount": result["total_amount"],
        "reimbursement": reimbursement,
        "profile": check,
        "ready": ok,
        "handoff": {
            "label": "打开官方 App",
            "path": APP_INVOICE_HINT,
            "auto_submit": False,
            "reason": "issue-invoice 未在公开工具列表，且发票须由用户本人提交",
        },
        "warnings": check["warnings"],
        "text": "\n".join(lines),
    }

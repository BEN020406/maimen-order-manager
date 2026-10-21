#!/usr/bin/env python3
"""麦门订单管家 · 统一命令行入口。

Agent 用这个 CLI 把 MCP 返回的原始 JSON 变成可展示的卡片与结构化结果。
CLI 本身**不调用 MCP、不持有 Token、不写任何会话数据到磁盘**（除非显式指定 --out）。

用法示例：
  python cli.py capabilities --tools fixtures/tools_public.json
  python cli.py orders --input fixtures/orders.json
  python cli.py invoice --input fixtures/orders.json --profile fixtures/invoice_profile.json --city 上海
  python cli.py lottery-info --input fixtures/lottery_info.json
  python cli.py lottery-preview --input fixtures/lottery_info.json
  python cli.py lottery-result --input fixtures/draw_result.json
  python cli.py home --orders fixtures/orders.json --lottery fixtures/lottery_info.json \
      --tools fixtures/tools_public.json --city 上海 --format json
  python cli.py demo
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import mcp_client  # noqa: E402
from common.contracts import format_amount, summarize_lottery  # noqa: E402
from operations import invoice as invoice_ops  # noqa: E402
from operations import lottery as lottery_ops  # noqa: E402
from operations import orders as orders_ops  # noqa: E402

FIXTURES = SCRIPTS_DIR / "fixtures"


# --------------------------------------------------------------------------- #
# 输入输出
# --------------------------------------------------------------------------- #
def read_json(path: Optional[str]) -> Any:
    if path in (None, "", "-"):
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_fixture(name: str) -> Any:
    return read_json(str(FIXTURES / name))


def parse_targets(spec: Optional[str]) -> Sequence[float]:
    """把 "50,100" 解析成 (50.0, 100.0)；为空用默认档位。"""
    if not spec:
        return invoice_ops.COMMON_TARGETS
    values = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            value = float(chunk)
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return tuple(values) or invoice_ops.COMMON_TARGETS


def emit(payload: Dict[str, Any], fmt: str, text_key: str = "text") -> None:
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        print(payload.get(text_key, json.dumps(payload, ensure_ascii=False, default=str)))


def maybe_write(payload: Dict[str, Any], out: Optional[str], as_js: bool = False) -> None:
    if not out:
        return
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if as_js:
        body = "window.MCD_SNAPSHOT = " + body + ";\n"
    Path(out).write_text(body, encoding="utf-8")
    print(f"已写入 {out}", file=sys.stderr)


# --------------------------------------------------------------------------- #
# 子命令实现
# --------------------------------------------------------------------------- #
def cmd_capabilities(args) -> int:
    report = mcp_client.discover(read_json(args.tools))
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(mcp_client.render_matrix(report))
    return 0


def cmd_orders(args) -> int:
    tiers = orders_ops.parse_tiers(args.tiers) if args.tiers else None
    center = orders_ops.build_review_center(
        read_json(args.input), limit=args.limit, tiers=tiers
    )
    if args.format == "json":
        maybe_write(center, args.out)
        print(json.dumps(center, ensure_ascii=False, indent=2, default=str))
    else:
        print(center["text"])
    return 0


def cmd_invoice(args) -> int:
    profile = read_json(args.profile) if args.profile else None
    card = invoice_ops.build_invoice_card(
        read_json(args.input),
        profile=profile,
        city=args.city,
        store=args.store,
        date_from=args.date_from,
        date_to=args.date_to,
        min_amount=args.min_amount,
        max_amount=args.max_amount,
        target=args.target,
    )
    if args.format == "json":
        maybe_write(card, args.out)
        print(json.dumps(card, ensure_ascii=False, indent=2, default=str))
    else:
        print(card["text"])
    return 0


def cmd_lottery_info(args) -> int:
    overview = lottery_ops.build_overview(read_json(args.input), retrieved_at=args.retrieved_at)
    if args.history:
        history = lottery_ops.build_history(read_json(args.history))
        overview["history"] = history
        overview["text"] = overview["text"] + "\n\n" + history["text"]
    if args.format == "json":
        print(json.dumps(overview, ensure_ascii=False, indent=2, default=str))
    else:
        print(overview["text"])
    return 0


def cmd_lottery_preview(args) -> int:
    preview = lottery_ops.build_draw_preview(
        read_json(args.input), retrieved_at=args.retrieved_at
    )
    if args.format == "json":
        print(json.dumps(preview, ensure_ascii=False, indent=2, default=str))
    else:
        print(preview["text"])
    return 0


def cmd_lottery_result(args) -> int:
    result = lottery_ops.interpret_draw_result(read_json(args.input))
    if args.verify_with:
        before = summarize_lottery(read_json(args.verify_with))
        result["verification"] = lottery_ops.verify_consumption(before, read_json(args.input))
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(result["text"])
    return 0


def cmd_lottery_timeout(args) -> int:
    result = lottery_ops.handle_timeout(args.error)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(result["text"])
    return 0


def build_snapshot(
    orders_raw: Any,
    lottery_raw: Optional[Any] = None,
    profile: Optional[Dict[str, Any]] = None,
    tools_raw: Optional[Any] = None,
    city: Optional[str] = None,
    targets: Sequence[float] = invoice_ops.COMMON_TARGETS,
) -> Dict[str, Any]:
    """首页快照：三卡片 + 待处理总数 + 最近动态。"""
    review = orders_ops.build_review_center(orders_raw)
    invoice_card = invoice_ops.build_invoice_card(orders_raw, profile=profile, city=city)
    reimbursements = {
        str(int(target)): invoice_ops.plan_reimbursement(invoice_card["candidates"], target)
        for target in targets
    }
    invoice_card["reimbursements"] = reimbursements
    invoice_card["reimbursement"] = reimbursements.get(str(int(targets[0]))) if targets else None
    lottery_overview = (
        lottery_ops.build_overview(lottery_raw) if lottery_raw else None
    )
    capabilities = mcp_client.discover(tools_raw) if tools_raw is not None else None

    pending_ids = {order["order_id"] for order in review["candidates"] if order.get("order_id")}
    invoice_ids = {order["order_id"] for order in invoice_card["candidates"] if order.get("order_id")}
    total = len(pending_ids | invoice_ids)

    summary = (lottery_overview or {}).get("summary") or {}
    if summary.get("available_point") is not None:
        lottery_value = f"{summary['available_point']} 积分"
    elif summary.get("available_count") is not None:
        lottery_value = f"{summary['available_count']} 次"
    else:
        lottery_value = "未知"

    cards = [
        {
            "module": "orders",
            "title": "待评价",
            "value": f"{review['counts']['candidates']} 笔",
            "caption": (
                f"含 {review['counts']['unknown']} 笔待确认"
                if review["counts"]["unknown"]
                else review["scope"]["scope_note"]
            ),
            "action": "查看待评价订单",
            "state": "pending" if review["counts"]["candidates"] else "done",
        },
        {
            "module": "invoice",
            "title": "开发票",
            "value": f"{invoice_card['count']} 笔",
            "caption": f"实付合计 {format_amount(Decimal(str(invoice_card['total_amount'])))}",
            "action": "整理开票资料",
            "state": "pending" if invoice_card["count"] else "done",
        },
        {
            "module": "lottery",
            "title": "抽奖",
            "value": lottery_value,
            "caption": (summary.get("activity_name") or "未查询活动") if summary else "未查询活动",
            "action": "查询抽奖活动",
            "state": (
                "confirm"
                if summary.get("eligible") is True
                else ("unavailable" if lottery_overview is None else "done")
            ),
        },
    ]

    timeline = []
    for order in review["pending"][:6]:
        timeline.append(
            {
                "date": (order.get("created_at") or "")[:10],
                "text": f"{order.get('store_name')} 可能待评价",
                "module": "orders",
            }
        )
    if lottery_overview:
        timeline.append(
            {
                "date": (summary.get("retrieved_at") or "")[:10],
                "text": f"抽奖活动{summary.get('status') or '状态未知'}",
                "module": "lottery",
            }
        )
    timeline.sort(key=lambda item: item["date"], reverse=True)

    return {
        "generated_at": review["scope"]["retrieved_at"],
        "capabilities": capabilities,
        "home": {
            "pending_total": total,
            "synced_label": "刚刚",
            "cards": cards,
            "timeline": timeline[:6],
        },
        "review": review,
        "invoice": invoice_card,
        "lottery": lottery_overview,
    }


def cmd_home(args) -> int:
    snapshot = build_snapshot(
        read_json(args.orders),
        lottery_raw=read_json(args.lottery) if args.lottery else None,
        profile=read_json(args.profile) if args.profile else None,
        tools_raw=read_json(args.tools) if args.tools else None,
        city=args.city,
        targets=parse_targets(args.targets),
    )
    if args.out:
        maybe_write(snapshot, args.out, as_js=args.out.endswith(".js"))
    if args.format == "json":
        print(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str))
    else:
        home = snapshot["home"]
        print(f"现在有 {home['pending_total']} 件权益待处理")
        print(f"最近同步：{home['synced_label']}")
        print("")
        for card in home["cards"]:
            print(f"[{card['title']}] {card['value']}  ·  {card['caption']}  → {card['action']}")
        print("")
        print("最近动态")
        for item in home["timeline"]:
            print(f"{item['date']}  {item['text']}")
    return 0


def cmd_demo(args) -> int:
    """离线自演：一次跑完四个模块，验证链路。"""
    orders = load_fixture("orders.json")
    info = load_fixture("lottery_info.json")
    profile = load_fixture("invoice_profile.json")
    tools = load_fixture("tools_public.json")

    print("=" * 62)
    print("① 能力发现")
    print("=" * 62)
    print(mcp_client.render_matrix(mcp_client.discover(tools)))

    print("\n" + "=" * 62)
    print("② 待评价订单")
    print("=" * 62)
    print(orders_ops.build_review_center(orders)["text"])

    print("\n" + "=" * 62)
    print("③ 发票助手（含 ¥100 报销门槛凑单）")
    print("=" * 62)
    print(invoice_ops.build_invoice_card(orders, profile, city="上海", target=100)["text"])

    print("\n" + "=" * 62)
    print("④ 抽奖管家")
    print("=" * 62)
    overview = lottery_ops.build_overview(info)
    print(overview["text"])
    print("")
    preview = lottery_ops.build_draw_preview(info)
    print(preview["text"])
    print("")
    print(lottery_ops.interpret_draw_result(load_fixture("draw_result.json"))["text"])

    print("\n" + "=" * 62)
    print("⑤ 首页卡片")
    print("=" * 62)
    snapshot = build_snapshot(orders, info, profile, tools, city="上海")
    home = snapshot["home"]
    print(f"现在有 {home['pending_total']} 件权益待处理")
    for card in home["cards"]:
        print(f"[{card['title']}] {card['value']}  ·  {card['caption']}  → {card['action']}")

    if args.out:
        maybe_write(snapshot, args.out, as_js=args.out.endswith(".js"))
    return 0


# --------------------------------------------------------------------------- #
# 参数解析
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maimen",
        description="麦门订单管家：待评价订单 / 发票整理 / 单次抽奖（个人效率工具，非官方产品）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(node, text=True):
        node.add_argument("--format", choices=("text", "json"), default="text")
        if text:
            node.add_argument("--out", help="额外写出一份 JSON/JS 快照（默认不落盘）")

    cap = sub.add_parser("capabilities", help="解析 tools/list 并给出能力矩阵")
    cap.add_argument("--tools", required=True, help="tools/list 的 JSON 返回，- 表示 stdin")
    cap.add_argument("--format", choices=("text", "json"), default="text")
    cap.set_defaults(func=cmd_capabilities)

    orders = sub.add_parser("orders", help="待评价订单统计")
    orders.add_argument("--input", required=True, help="order-list 返回")
    orders.add_argument("--limit", type=int)
    orders.add_argument(
        "--tiers",
        help="评价兑礼档位，默认 1:小可乐,2:中可乐,3:小薯条；按门店规则填写",
    )
    add_common(orders)
    orders.set_defaults(func=cmd_orders)

    inv = sub.add_parser("invoice", help="发票候选筛选与资料整理")
    inv.add_argument("--input", required=True, help="order-list / query-order 返回")
    inv.add_argument("--profile", help="开票资料 JSON（抬头/税号/邮箱）")
    inv.add_argument("--city")
    inv.add_argument("--store")
    inv.add_argument("--from", dest="date_from")
    inv.add_argument("--to", dest="date_to")
    inv.add_argument("--min", dest="min_amount", type=float)
    inv.add_argument("--max", dest="max_amount", type=float)
    inv.add_argument(
        "--target",
        type=float,
        help="报销门槛金额（如 50 / 100），会给出凑单组合与差额",
    )
    add_common(inv)
    inv.set_defaults(func=cmd_invoice)

    info = sub.add_parser("lottery-info", help="抽奖活动概览")
    info.add_argument("--input", required=True, help="query-lottery-info 返回")
    info.add_argument("--history", help="query-my-prizes 返回（可选）")
    info.add_argument("--retrieved-at", help="数据抓取时间，用于 TTL 判断")
    add_common(info)
    info.set_defaults(func=cmd_lottery_info)

    preview = sub.add_parser("lottery-preview", help="生成单次抽奖确认卡（不执行）")
    preview.add_argument("--input", required=True)
    preview.add_argument("--retrieved-at")
    add_common(preview, text=False)
    preview.set_defaults(func=cmd_lottery_preview)

    result = sub.add_parser("lottery-result", help="解析单次抽奖结果")
    result.add_argument("--input", required=True, help="draw-lottery 返回")
    result.add_argument("--verify-with", help="可选的 query-lottery-info 返回，用于核验资源变化")
    add_common(result, text=False)
    result.set_defaults(func=cmd_lottery_result)

    timeout = sub.add_parser("lottery-timeout", help="超时/异常时的标准响应（只核验不重试）")
    timeout.add_argument("--error", help="错误摘要，会被脱敏")
    add_common(timeout, text=False)
    timeout.set_defaults(func=cmd_lottery_timeout)

    home = sub.add_parser("home", help="生成首页快照（三卡片 + 最近动态）")
    home.add_argument("--orders", required=True)
    home.add_argument("--lottery")
    home.add_argument("--profile")
    home.add_argument("--tools")
    home.add_argument("--city")
    home.add_argument("--targets", help="报销门槛档位，默认 50,100")
    home.add_argument("--out", help="写出快照；.js 后缀会包成 window.MCD_SNAPSHOT")
    home.add_argument("--format", choices=("text", "json"), default="text")
    home.set_defaults(func=cmd_home)

    demo = sub.add_parser("demo", help="离线自演四个模块")
    demo.add_argument("--out", help="写出首页快照（可给 .js）")
    demo.set_defaults(func=cmd_demo)

    return parser


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        print(f"读取失败：{exc}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"JSON 解析失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

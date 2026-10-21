"""MCP 能力发现。

运行时必须先做 tools/list，再决定走完整流程还是降级交接。
**不假设任何工具存在**，也**不凭空编造工具名**。

关于 Token：本模块完全不接触凭证。Token 由 WorkBuddy 的连接器配置注入，
技能内部不读取、不缓存、不落盘。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

# 各模块必需工具
MODULE_REQUIRED = {
    "orders": ("order-list",),
    "invoice": ("order-list",),
    "lottery": ("query-lottery-info", "draw-lottery", "query-my-prizes"),
}

# 可选增强工具（缺失不影响主流程）
MODULE_OPTIONAL = {
    "orders": ("query-order",),
    "invoice": ("query-order",),
    "lottery": (),
}

# 策略性禁用的工具：即使接口存在，也不代替用户提交
POLICY_DISABLED = {
    "issue-invoice": "发票提交必须由用户在官方 App/小程序完成，技能只整理清单",
    "submit-review": "评价必须由用户本人提交，技能只展示状态或生成草稿",
    "mall-create-order": "本技能不提供下单主线",
    "create-order": "本技能不提供点餐下单主线",
    "auto-bind-coupons": "本技能不做优惠券领取",
}


def _extract_names(payload: Any) -> List[str]:
    """兼容 tools/list 的多种返回形态。"""
    names: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            names.append(node)
            return
        if isinstance(node, dict):
            if isinstance(node.get("name"), str):
                names.append(node["name"])
                return
            for key in ("tools", "data", "result", "items", "list"):
                if key in node:
                    walk(node[key])
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    walk(payload)
    # 去重保序
    seen: set = set()
    unique: List[str] = []
    for name in names:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    return unique


def discover(payload: Any) -> Dict[str, Any]:
    """返回能力矩阵。payload 为 tools/list 的原始返回（list 或对象均可）。"""
    names = _extract_names(payload)
    available = set(names)
    modules: Dict[str, Dict[str, Any]] = {}

    for module, required in MODULE_REQUIRED.items():
        found = [tool for tool in required if tool in available]
        missing = [tool for tool in required if tool not in available]
        optional_found = [t for t in MODULE_OPTIONAL[module] if t in available]
        optional_missing = [t for t in MODULE_OPTIONAL[module] if t not in available]

        if not missing:
            mode = "full"
            note = "所需工具均已就绪"
        elif found:
            mode = "degraded"
            note = "部分工具缺失，仅能展示已有信息"
        else:
            mode = "unsupported"
            note = "缺少必需工具，无法执行该模块"

        modules[module] = {
            "module": module,
            "mode": mode,
            "state": "DISCOVER" if mode != "unsupported" else "UNSUPPORTED",
            "required": list(required),
            "found": found,
            "missing": missing,
            "optional_found": optional_found,
            "optional_missing": optional_missing,
            "note": note,
        }

    policy_blocked = [
        {"tool": tool, "reason": reason}
        for tool, reason in POLICY_DISABLED.items()
        if tool in available
    ]

    return {
        "tool_count": len(names),
        "tools": sorted(available),
        "modules": modules,
        "policy_blocked": policy_blocked,
        "handoff": {
            "invoice": "issue-invoice" not in available,
            "review": "submit-review" not in available,
            "note": "发票与评价的最终提交始终由用户在官方 App/小程序完成",
        },
    }


def module_mode(report: Dict[str, Any], module: str) -> str:
    return report.get("modules", {}).get(module, {}).get("mode", "unsupported")


def require(report: Dict[str, Any], tools: Sequence[str]) -> List[str]:
    """返回缺失的工具名列表，供调用前校验。"""
    available = set(report.get("tools") or [])
    return [tool for tool in tools if tool not in available]


def missing_tools_summary(report: Dict[str, Any]) -> List[str]:
    missing: List[str] = []
    for module in MODULE_REQUIRED:
        for tool in report.get("modules", {}).get(module, {}).get("missing", []):
            if tool not in missing:
                missing.append(tool)
    return missing


def render_matrix(report: Dict[str, Any]) -> str:
    """能力矩阵的纯文本版，方便直接贴进对话。"""
    lines = [
        f"已发现 {report.get('tool_count', 0)} 个 MCP 工具",
        "",
        "模块能力：",
    ]
    labels = {"orders": "待评价订单", "invoice": "发票助手", "lottery": "抽奖管家"}
    mode_text = {"full": "完整", "degraded": "部分可用", "unsupported": "不可用"}
    for module, info in report.get("modules", {}).items():
        lines.append(
            f"- {labels.get(module, module)}：{mode_text.get(info['mode'], info['mode'])}"
            f"（{info['note']}）"
        )
        if info["missing"]:
            lines.append(f"  缺失：{', '.join(info['missing'])}")

    lines.append("")
    lines.append("交接模式：")
    lines.append(
        "- 发票提交："
        + ("未公开接口，整理清单后交官方 App" if report["handoff"]["invoice"] else "接口存在，但按策略仍由用户提交")
    )
    lines.append(
        "- 评价提交："
        + ("未公开接口，仅展示状态" if report["handoff"]["review"] else "接口存在，但按策略仍由用户提交")
    )
    if report.get("policy_blocked"):
        lines.append("")
        lines.append("策略禁用：")
        for item in report["policy_blocked"]:
            lines.append(f"- {item['tool']}：{item['reason']}")
    return "\n".join(lines)

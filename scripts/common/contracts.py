"""统一数据契约：订单 / 抽奖 / 发票资料 / 动作信封。

设计原则（不可妥协）：
1. 字段名以 McDonald's MCP 实际返回为准。官方文档中 `order-list` 返回
   orderId / createTime / orderStatus / realTotalAmount / storeCode / storeName /
   orderProductList / orderType，最多最近 10 笔；`query-order` 另含 totalAmount 等明细。
2. 交付稿约定的 `orderStatusCode=8` 表示「已评价」。若接口未返回任何评价状态字段，
   一律归类为 `unknown`（无法确认），**绝不**默认算成未评价。
3. 缺失字段统一填 `未知`，不使用猜测值。金额只取自订单实付金额。
4. 本模块不做任何 IO，不接触 Token。

金额单位说明：订单类字段（realTotalAmount / totalAmount）按元处理；
`calculate-price` 返回的是「分」，与本模块无关，严禁混用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

UNKNOWN = "未知"
DEFAULT_CURRENCY = "CNY"

# 交付稿约定：orderStatusCode=8 → 已评价
REVIEWED_STATUS_CODES = {"8"}

ORDER_ID_KEYS = ("orderId", "order_id", "orderNo", "orderCode", "id")
CREATE_TIME_KEYS = ("createTime", "createdAt", "created_at", "orderTime", "submitTime")
STATUS_CODE_KEYS = ("orderStatusCode", "order_status_code", "statusCode", "status_code")
STATUS_TEXT_KEYS = (
    "orderStatus",
    "orderStatusText",
    "statusText",
    "statusDesc",
    "orderStatusName",
)
PAID_AMOUNT_KEYS = (
    "realTotalAmount",
    "realPayAmount",
    "payAmount",
    "paidAmount",
    "actualAmount",
    "totalAmount",
)
CURRENCY_KEYS = ("currency", "currencyCode")
STORE_NAME_KEYS = ("storeName", "store_name", "storeTitle")
STORE_CITY_KEYS = ("storeCity", "storeCityName", "cityName", "city", "store_city")
ORDER_TYPE_KEYS = ("orderType", "orderTypeName", "takeWay", "channel")
ITEMS_KEYS = ("orderProductList", "productList", "items", "products")

# 订单状态文案关键词（中文接口以文案为主，数字码仅在交付稿约定范围内使用）
CANCELLED_WORDS = ("取消", "关闭", "已退款", "退款", "失败")
PENDING_WORDS = ("待支付", "未支付", "待付款", "支付中", "待确认")
IN_PROGRESS_WORDS = (
    "进行中",
    "制作中",
    "待取餐",
    "待取货",
    "配送中",
    "待接单",
    "备餐",
    "已下单",
    "待发货",
)
COMPLETED_WORDS = ("已完成", "完成", "已送达", "已取餐", "已收货", "已消费")
REVIEWED_WORDS = ("已评价", "已评论", "已点评")

# 取餐方式文案（仅用于展示，不推断业务含义）
TAKE_WAY_LABELS = {
    "locker-in": "取餐柜取餐",
    "locker": "取餐柜取餐",
    "counter": "柜台取餐",
    "table": "送餐到桌",
    "drive": "得来速",
    "delivery": "外送",
}

# 城市推断用的常见城市名（仅当订单无城市字段时，作为「门店名后缀」匹配提示）
CITY_HINTS = (
    "北京", "上海", "广州", "深圳", "天津", "重庆", "成都", "杭州", "南京", "武汉",
    "西安", "苏州", "无锡", "宁波", "厦门", "福州", "长沙", "郑州", "济南", "青岛",
    "合肥", "南昌", "昆明", "贵阳", "南宁", "海口", "三亚", "沈阳", "大连", "长春",
    "哈尔滨", "石家庄", "太原", "呼和浩特", "兰州", "西宁", "银川", "乌鲁木齐",
    "拉萨", "东莞", "佛山", "珠海", "中山", "惠州", "汕头", "温州", "嘉兴", "绍兴",
    "金华", "台州", "泉州", "常州", "南通", "徐州", "扬州", "烟台", "潍坊", "洛阳",
)


# --------------------------------------------------------------------------- #
# 基础取值工具
# --------------------------------------------------------------------------- #
def pick(raw: Dict[str, Any], keys: Iterable[str]) -> Any:
    """按候选键顺序取第一个有效标量值；dict/list/空串视为缺失。"""
    if not isinstance(raw, dict):
        return None
    for key in keys:
        if key not in raw:
            continue
        value = raw[key]
        if value is None:
            continue
        if isinstance(value, (dict, list, tuple)):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def pick_bool(raw: Dict[str, Any], keys: Iterable[str]) -> Optional[bool]:
    if not isinstance(raw, dict):
        return None
    for key in keys:
        if key not in raw:
            continue
        value = raw[key]
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            low = value.strip().lower()
            if low in ("true", "1", "yes", "y"):
                return True
            if low in ("false", "0", "no", "n"):
                return False
    return None


def pick_list(raw: Dict[str, Any], keys: Iterable[str]) -> List[Any]:
    if not isinstance(raw, dict):
        return []
    for key in keys:
        value = raw.get(key)
        if isinstance(value, list):
            return value
    return []


def to_amount(value: Any) -> Optional[Decimal]:
    """把金额解析为元（Decimal，两位小数）。无法解析返回 None，绝不填 0。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, (int, float)):
        candidate = Decimal(str(value))
    elif isinstance(value, str):
        cleaned = re.sub(r"[¥￥,，\s元]", "", value)
        if cleaned in ("", "-", "--", "null", "None"):
            return None
        try:
            candidate = Decimal(cleaned)
        except InvalidOperation:
            return None
    else:
        return None
    try:
        return candidate.quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def to_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (dict, list, tuple)):
        return None
    text = str(value).strip()
    return text or None


def normalize_status_code(value: Any) -> Optional[str]:
    """状态码统一成字符串：8 / "8" / 8.0 → "8"。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def parse_time(value: Any) -> Optional[datetime]:
    """解析常见时间格式：yyyy-MM-dd HH:mm:ss / ISO8601 / 秒级或毫秒级时间戳。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        stamp = float(value)
        if stamp > 1e12:  # 毫秒
            stamp /= 1000.0
        try:
            return datetime.fromtimestamp(stamp)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d{10,13}", text):
        return parse_time(int(text))
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def format_amount(amount: Optional[Decimal]) -> str:
    if amount is None:
        return "金额未知"
    return f"¥{amount:.2f}"


def format_date(value: Optional[str]) -> str:
    parsed = parse_time(value)
    return parsed.strftime("%Y-%m-%d") if parsed else "时间未知"


# --------------------------------------------------------------------------- #
# 订单模型
# --------------------------------------------------------------------------- #
@dataclass
class OrderSummary:
    order_id: Optional[str] = None
    created_at: Optional[str] = None
    status_code: Optional[str] = None
    status_label: Optional[str] = None
    paid_amount: Optional[Decimal] = None
    currency: str = DEFAULT_CURRENCY
    store_name: Optional[str] = None
    store_city: Optional[str] = None
    city_source: str = "unknown"  # field | store_name | unknown
    order_type: Optional[str] = None
    order_type_label: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "order-list"
    retrieved_at: str = field(default_factory=now_iso)

    # 派生字段（不来自接口）
    review_state: str = "unknown"  # reviewed | likely_pending | unknown | not_eligible
    review_label: str = "无法确认评价状态"
    review_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """按交付稿第 7 节的数据契约输出，附加字段均为派生值。"""
        return {
            "order_id": self.order_id,
            "created_at": self.created_at,
            "status_code": self.status_code,
            "status_label": self.status_label or UNKNOWN,
            "paid_amount": None if self.paid_amount is None else float(self.paid_amount),
            "currency": self.currency,
            "store_name": self.store_name or UNKNOWN,
            "store_city": self.store_city or UNKNOWN,
            "city_source": self.city_source,
            "order_type": self.order_type,
            "order_type_label": self.order_type_label or UNKNOWN,
            "items": self.items,
            "source": self.source,
            "retrieved_at": self.retrieved_at,
            "review_state": self.review_state,
            "review_label": self.review_label,
            "review_reason": self.review_reason,
        }


def _infer_city(store_name: Optional[str]) -> Tuple[Optional[str], str]:
    if not store_name:
        return None, "unknown"
    for city in CITY_HINTS:
        if city in store_name:
            return city, "store_name"
    return None, "unknown"


def _order_type_label(raw_type: Any) -> Optional[str]:
    text = to_text(raw_type)
    if text is None:
        return None
    if text in TAKE_WAY_LABELS:
        return TAKE_WAY_LABELS[text]
    if text.isdigit():
        # 接口未公开数字码含义，如实展示，不猜测
        return f"类型码 {text}（接口未定义）"
    return text


def _normalize_items(raw: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return items
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        items.append(
            {
                "product_code": to_text(
                    pick(entry, ("productCode", "code", "skuId", "productId"))
                ),
                "name": to_text(pick(entry, ("productName", "name", "title"))) or UNKNOWN,
                "quantity": pick(entry, ("quantity", "qty", "count")) or 1,
            }
        )
    return items


def classify_review(order: OrderSummary) -> Tuple[str, str, str]:
    """判定评价状态，返回 (state, label, reason)。

    规则（严格按交付稿）：
    - status_code == 8 或状态文案含「已评价」 → reviewed
    - 取消 / 待支付 / 进行中 → not_eligible（不计入待评价）
    - 已完成且 status_code 存在且不是 8 → likely_pending（可能待评价）
    - 已完成但没有评价状态字段 → unknown（无法确认）
    - 其余 → unknown
    """
    code = order.status_code
    text = order.status_label or ""

    if code is not None and code in REVIEWED_STATUS_CODES:
        return "reviewed", "已评价", "orderStatusCode=8"
    if any(word in text for word in REVIEWED_WORDS):
        return "reviewed", "已评价", "状态文案含评价标记"

    if any(word in text for word in CANCELLED_WORDS):
        return "not_eligible", "不适用", "订单已取消或已关闭"
    if any(word in text for word in PENDING_WORDS):
        return "not_eligible", "不适用", "订单未完成支付"
    if any(word in text for word in IN_PROGRESS_WORDS):
        return "not_eligible", "不适用", "订单仍在进行中"

    is_completed = any(word in text for word in COMPLETED_WORDS)
    if is_completed:
        if code is not None:
            return "likely_pending", "可能待评价", f"订单已完成，评价状态码为 {code}"
        return "unknown", "待确认", "接口未返回评价状态字段，需用户自行确认"

    if not text:
        return "unknown", "待确认", "接口未返回订单状态"
    return "unknown", "待确认", f"状态「{text}」无法判断是否可评价"


def normalize_order(
    raw: Dict[str, Any],
    source: str = "order-list",
    retrieved_at: Optional[str] = None,
) -> OrderSummary:
    """把 MCP 原始订单转成统一模型。缺失字段留空，由展示层写「未知」。"""
    store_name = to_text(pick(raw, STORE_NAME_KEYS))
    city_field = to_text(pick(raw, STORE_CITY_KEYS))
    if city_field:
        store_city, city_source = city_field, "field"
    else:
        store_city, city_source = _infer_city(store_name)

    raw_type = pick(raw, ORDER_TYPE_KEYS)
    order = OrderSummary(
        order_id=to_text(pick(raw, ORDER_ID_KEYS)),
        created_at=to_text(pick(raw, CREATE_TIME_KEYS)),
        status_code=normalize_status_code(pick(raw, STATUS_CODE_KEYS)),
        status_label=to_text(pick(raw, STATUS_TEXT_KEYS)),
        paid_amount=to_amount(pick(raw, PAID_AMOUNT_KEYS)),
        currency=to_text(pick(raw, CURRENCY_KEYS)) or DEFAULT_CURRENCY,
        store_name=store_name,
        store_city=store_city,
        city_source=city_source,
        order_type=to_text(raw_type),
        order_type_label=_order_type_label(raw_type),
        items=_normalize_items(pick_list(raw, ITEMS_KEYS)),
        source=source,
        retrieved_at=retrieved_at or now_iso(),
    )
    order.review_state, order.review_label, order.review_reason = classify_review(order)
    return order


def normalize_orders(
    raw_orders: Any, source: str = "order-list", retrieved_at: Optional[str] = None
) -> List[OrderSummary]:
    """接受 list 或 {data:{list:[...]}} / {list:[...]} 形态的返回。"""
    entries: List[Any] = []
    if isinstance(raw_orders, list):
        entries = raw_orders
    elif isinstance(raw_orders, dict):
        for key in ("list", "orders", "orderList", "records"):
            value = raw_orders.get(key)
            if isinstance(value, list):
                entries = value
                break
        if not entries:
            data = raw_orders.get("data")
            if isinstance(data, dict):
                for key in ("list", "orders", "orderList", "records"):
                    value = data.get(key)
                    if isinstance(value, list):
                        entries = value
                        break
            elif isinstance(data, list):
                entries = data
    stamp = retrieved_at or now_iso()
    return [normalize_order(item, source, stamp) for item in entries if isinstance(item, dict)]


# --------------------------------------------------------------------------- #
# 抽奖模型
# --------------------------------------------------------------------------- #
@dataclass
class LotterySummary:
    activity_id: Optional[str] = None
    activity_name: Optional[str] = None
    status: str = UNKNOWN
    resource_type: str = "unknown"  # points | count | unknown
    available_count: Optional[int] = None
    available_point: Optional[int] = None
    draw_cost: Optional[int] = None
    cost_unit: str = ""
    prizes: List[Dict[str, Any]] = field(default_factory=list)
    eligible: Optional[bool] = None
    reason: Optional[str] = None
    retrieved_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "activity_name": self.activity_name or UNKNOWN,
            "status": self.status,
            "resource_type": self.resource_type,
            "available_count": self.available_count,
            "available_point": self.available_point,
            "draw_cost": self.draw_cost,
            "cost_unit": self.cost_unit,
            "prizes": self.prizes,
            "eligible": self.eligible,
            "reason": self.reason,
            "retrieved_at": self.retrieved_at,
        }


def _to_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(Decimal(str(value).strip()))
    except (InvalidOperation, ValueError):
        return None


def summarize_lottery(raw: Any, retrieved_at: Optional[str] = None) -> LotterySummary:
    """归一化 query-lottery-info 的返回。"""
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        body = raw["data"]
    elif isinstance(raw, dict):
        body = raw
    else:
        body = {}

    draw_decision = body.get("drawDecision") if isinstance(body.get("drawDecision"), dict) else {}
    next_cost = draw_decision.get("nextConsumption")
    next_cost = next_cost if isinstance(next_cost, dict) else {}

    draw_cost = _to_int(body.get("drawPoint"))
    cost_unit = "积分"
    if draw_cost is None:
        draw_cost = _to_int(next_cost.get("points"))
    if draw_cost is None and next_cost.get("type"):
        draw_cost = 1
        cost_unit = "次数"

    available_point = _to_int(body.get("availablePoint"))
    available_count = _to_int(body.get("availableTimes"))

    if draw_cost is not None and cost_unit == "积分":
        resource_type = "points"
    elif available_count is not None:
        resource_type = "count"
    else:
        resource_type = "unknown"

    prizes: List[Dict[str, Any]] = []
    for entry in body.get("prizes") or []:
        if not isinstance(entry, dict):
            continue
        prizes.append(
            {
                "name": to_text(entry.get("name")) or UNKNOWN,
                "type_text": to_text(pick(entry, ("typeText", "type", "prizeTypeText"))),
                "valid_date": to_text(
                    pick(entry, ("validDateInfo", "validDate", "validDateText"))
                ),
            }
        )

    return LotterySummary(
        activity_id=to_text(pick(body, ("activityCode", "activityId", "id"))),
        activity_name=to_text(pick(body, ("activityName", "name"))),
        status=to_text(
            pick(body, ("activityStatusText", "statusText", "activityStatus"))
        )
        or UNKNOWN,
        resource_type=resource_type,
        available_count=available_count,
        available_point=available_point,
        draw_cost=draw_cost,
        cost_unit=cost_unit,
        prizes=prizes,
        eligible=pick_bool(draw_decision, ("resourceEligible", "eligible")),
        reason=to_text(draw_decision.get("reason")),
        retrieved_at=retrieved_at or now_iso(),
    )


# --------------------------------------------------------------------------- #
# 动作信封
# --------------------------------------------------------------------------- #
def build_envelope(
    module: str,
    action: str,
    preview: str,
    state: str,
    requires_confirmation: bool = True,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "module": module,
        "action": action,
        "preview": preview,
        "requires_confirmation": requires_confirmation,
        "state": state,
        "idempotency_key": idempotency_key or "",
    }

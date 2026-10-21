"""脱敏工具：税号、邮箱、Token、订单号、日志回传。

硬性要求（交付稿第 11 节）：
- MCP Token 只能来自 WorkBuddy 的连接配置，本模块**不读取任何环境变量**，
  也不从文件读取 Token；仅提供展示/日志层面的掩码函数。
- 税号、邮箱、订单 ID 做最小化展示；日志与错误回传必须脱敏。
- 本模块不写磁盘、不落缓存。
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

MASK_CHAR = "*"
AUTH_PATTERN = re.compile(r"(Bearer\s+)([A-Za-z0-9\-\._~\+/=]{4,})", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"\b([A-Za-z0-9]{8}[-_][A-Za-z0-9]{4}[-_][A-Za-z0-9]{4}[-_][A-Za-z0-9]{4}[-_][A-Za-z0-9]{12})\b")
LONG_SECRET_PATTERN = re.compile(r"\b([A-Za-z0-9]{32,})\b")


def mask_tax_id(value: Optional[str]) -> str:
    """91310000MA1FL0XXXX → 9131**********1234（前 4 + 中间打码 + 后 4）。"""
    if not value:
        return "未知"
    text = re.sub(r"\s+", "", str(value)).upper()
    if len(text) <= 8:
        return MASK_CHAR * len(text)
    return f"{text[:4]}{MASK_CHAR * (len(text) - 8)}{text[-4:]}"


def mask_email(value: Optional[str]) -> str:
    """zhangsan@example.com → z***@example.com。"""
    if not value:
        return "未知"
    text = str(value).strip()
    if "@" not in text:
        return MASK_CHAR * min(len(text), 6)
    local, _, domain = text.partition("@")
    head = local[:1] if local else ""
    return f"{head}{MASK_CHAR * 3}@{domain}"


def mask_order_id(value: Optional[str]) -> str:
    """保留首尾各 3 位，中间打码；过短则整体打码。"""
    if not value:
        return "未知"
    text = str(value).strip()
    if len(text) <= 6:
        return MASK_CHAR * len(text)
    return f"{text[:3]}{MASK_CHAR * (len(text) - 6)}{text[-3:]}"


def mask_token(value: Optional[str]) -> str:
    if not value:
        return MASK_CHAR * 8
    text = str(value)
    if len(text) <= 8:
        return MASK_CHAR * len(text)
    return f"{text[:4]}{MASK_CHAR * 8}"


def redact_text(text: Any) -> str:
    """对任意日志文本做兜底脱敏：Authorization、疑似 Token、长串密钥。"""
    if text is None:
        return ""
    output = str(text)
    output = AUTH_PATTERN.sub(lambda m: m.group(1) + mask_token(m.group(2)), output)
    output = TOKEN_PATTERN.sub(lambda m: mask_token(m.group(1)), output)
    output = LONG_SECRET_PATTERN.sub(lambda m: mask_token(m.group(1)), output)
    return output


SECRET_KEYS = {
    "token",
    "access_token",
    "authorization",
    "mcp_token",
    "tax_id",
    "taxid",
    "tax_no",
    "taxno",
    "税号",
    "email",
    "mail",
    "mobile",
    "phone",
    "tel",
}


def redact_payload(payload: Any) -> Any:
    """递归脱敏结构化数据，用于日志/错误回传，可直接 JSON 序列化。"""
    if isinstance(payload, dict):
        result: Dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if lowered in SECRET_KEYS or "token" in lowered:
                result[key] = mask_token(value) if "token" in lowered else "***"
            elif "tax" in lowered:
                result[key] = mask_tax_id(value)
            elif lowered in ("email", "mail"):
                result[key] = mask_email(value)
            else:
                result[key] = redact_payload(value)
        return result
    if isinstance(payload, (list, tuple)):
        return [redact_payload(item) for item in payload]
    if isinstance(payload, str):
        return redact_text(payload)
    return payload


def assert_no_secret_leak(text: str, secrets: Optional[list] = None) -> bool:
    """供测试与自检使用：返回 True 表示未发现明文敏感值。"""
    if secrets:
        for secret in secrets:
            if secret and str(secret) in text:
                return False
    if AUTH_PATTERN.search(text) and not re.search(r"Bearer\s+\*{8}", text):
        return False
    return True

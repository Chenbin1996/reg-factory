"""Protocol payment-link catalog and optional local-engine discovery.

The WebUI keeps its own small contract instead of importing an external tool at
startup.  A locally installed protocol engine is only loaded by the dedicated
batch worker, so normal authorization/import runs remain self-contained.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PAYMENT_METHODS: tuple[dict[str, Any], ...] = (
    {"id": "paypal", "label": "PayPal", "country": "US", "currency": "USD", "batch_enabled": True, "payment_execution": "paypal_auto"},
    {"id": "gopay", "label": "GoPay", "country": "ID", "currency": "IDR", "batch_enabled": True},
    {"id": "gcash", "label": "GCash", "country": "PH", "currency": "PHP", "batch_enabled": True},
    {"id": "grabpay", "label": "GrabPay", "country": "PH", "currency": "PHP", "batch_enabled": True},
    {"id": "upi", "label": "UPI", "country": "IN", "currency": "INR", "batch_enabled": True},
    {"id": "ideal", "label": "iDEAL", "country": "NL", "currency": "EUR", "batch_enabled": True},
    {"id": "pix", "label": "PIX", "country": "BR", "currency": "BRL", "batch_enabled": True},
    {"id": "kakao", "label": "Kakao Pay", "country": "KR", "currency": "KRW", "batch_enabled": True},
    {"id": "blik", "label": "BLIK", "country": "PL", "currency": "PLN", "batch_enabled": False, "payment_execution": "single_code"},
    {"id": "twint", "label": "TWINT", "country": "CH", "currency": "CHF", "batch_enabled": True},
    {"id": "direct_card", "label": "Direct Card Checkout", "country": "PH", "currency": "PHP", "batch_enabled": True},
    {"id": "momo", "label": "MoMo", "country": "VN", "currency": "VND", "batch_enabled": True},
)

_METHODS_BY_ID = {item["id"]: item for item in PAYMENT_METHODS}


def payment_method(method: object) -> dict[str, Any] | None:
    """Return a copy of one known method without accepting aliases implicitly."""
    item = _METHODS_BY_ID.get(str(method or "").strip().lower())
    return dict(item) if item else None


def resolve_protocol_engine_root(value: object = "") -> Path | None:
    """Locate a compatible local GPT-Register-Tool checkout, if installed."""
    project_root = Path(__file__).resolve().parents[1]
    candidates = (
        str(value or "").strip(),
        os.environ.get("REG_FACTORY_PROTOCOL_PAYMENT_ROOT", "").strip(),
        str(project_root.parent / "GPT-Register-Tool"),
    )
    seen: set[Path] = set()
    for raw in candidates:
        if not raw:
            continue
        try:
            root = Path(raw).expanduser().resolve()
        except OSError:
            continue
        if root in seen:
            continue
        seen.add(root)
        if (root / "sms_tool" / "payment_link_manager.py").is_file() and (root / "payment_methods.json").is_file():
            return root
    return None


def protocol_catalog(engine_root: object = "") -> list[dict[str, Any]]:
    """Return UI-safe channel metadata and whether the local bridge can run it."""
    root = resolve_protocol_engine_root(engine_root)
    paypal_ready = paypal_payment_ready(root)
    return [
        {
            **item,
            "available": bool(root),
            "batch_payment_enabled": item.get("payment_execution") == "paypal_auto",
            "payment_available": bool(root and item.get("payment_execution") == "paypal_auto"),
            "payment_configured": bool(
                item.get("payment_execution") == "paypal_auto" and paypal_ready
            ),
            "payment_reason": (
                "可使用引擎默认资料，也可在本次任务中临时录入"
                if item.get("payment_execution") == "paypal_auto" and paypal_ready
                else "需要在本次任务中录入卡片、地址和手机号接码资料"
                if item.get("payment_execution") == "paypal_auto"
                else "BLIK 仅支持单账号六位码支付，不支持批量"
                if item.get("payment_execution") == "single_code"
                else "该渠道需在提取的链接或二维码中完成渠道确认"
            ),
            "reason": (
                "该渠道的上游协议不支持批量"
                if not item["batch_enabled"]
                else "本机未找到协议引擎"
                if not root
                else ""
            ),
        }
        for item in PAYMENT_METHODS
    ]


def paypal_payment_ready(engine_root: object = "") -> bool:
    """Check PayPal auto-pay prerequisites without returning payment details."""
    root = resolve_protocol_engine_root(engine_root)
    if not root:
        return False
    try:
        data = json.loads((root / "config.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, TypeError):
        return False
    config = data.get("paypal_auto") if isinstance(data, dict) else None
    return paypal_payment_config_ready(config)


def paypal_payment_config_ready(config: object) -> bool:
    """Validate the non-secret shape required by the PayPal execution adapter."""
    if not isinstance(config, dict):
        return False
    has_phone = bool(config.get("phone_numbers") or config.get("phone_number"))
    return bool(config.get("cards") and config.get("addresses") and has_phone)

window.MCD_SNAPSHOT = {
  "generated_at": "2026-10-21 22:55:36",
  "capabilities": {
    "tool_count": 11,
    "tools": [
      "calculate-price",
      "create-order",
      "draw-lottery",
      "now-time-info",
      "order-list",
      "query-lottery-info",
      "query-meals",
      "query-my-account",
      "query-my-coupons",
      "query-my-prizes",
      "query-order"
    ],
    "modules": {
      "orders": {
        "module": "orders",
        "mode": "full",
        "state": "DISCOVER",
        "required": [
          "order-list"
        ],
        "found": [
          "order-list"
        ],
        "missing": [],
        "optional_found": [
          "query-order"
        ],
        "optional_missing": [],
        "note": "所需工具均已就绪"
      },
      "invoice": {
        "module": "invoice",
        "mode": "full",
        "state": "DISCOVER",
        "required": [
          "order-list"
        ],
        "found": [
          "order-list"
        ],
        "missing": [],
        "optional_found": [
          "query-order"
        ],
        "optional_missing": [],
        "note": "所需工具均已就绪"
      },
      "lottery": {
        "module": "lottery",
        "mode": "full",
        "state": "DISCOVER",
        "required": [
          "query-lottery-info",
          "draw-lottery",
          "query-my-prizes"
        ],
        "found": [
          "query-lottery-info",
          "draw-lottery",
          "query-my-prizes"
        ],
        "missing": [],
        "optional_found": [],
        "optional_missing": [],
        "note": "所需工具均已就绪"
      }
    },
    "policy_blocked": [
      {
        "tool": "create-order",
        "reason": "本技能不提供点餐下单主线"
      }
    ],
    "handoff": {
      "invoice": true,
      "review": true,
      "note": "发票与评价的最终提交始终由用户在官方 App/小程序完成"
    }
  },
  "home": {
    "pending_total": 6,
    "synced_label": "刚刚",
    "cards": [
      {
        "module": "orders",
        "title": "待评价",
        "value": "4 笔",
        "caption": "含 1 笔待确认",
        "action": "查看待评价订单",
        "state": "pending"
      },
      {
        "module": "invoice",
        "title": "开发票",
        "value": "5 笔",
        "caption": "实付合计 ¥196.50",
        "action": "整理开票资料",
        "state": "pending"
      },
      {
        "module": "lottery",
        "title": "抽奖",
        "value": "320 积分",
        "caption": "麦麦幸运抽",
        "action": "查询抽奖活动",
        "state": "confirm"
      }
    ],
    "timeline": [
      {
        "date": "2026-10-21",
        "text": "抽奖活动进行中",
        "module": "lottery"
      },
      {
        "date": "2026-10-20",
        "text": "麦当劳·上海徐家汇店 可能待评价",
        "module": "orders"
      },
      {
        "date": "2026-10-18",
        "text": "麦当劳·上海陆家嘴店 可能待评价",
        "module": "orders"
      },
      {
        "date": "2026-10-12",
        "text": "麦当劳·上海陆家嘴店 可能待评价",
        "module": "orders"
      }
    ]
  },
  "review": {
    "state": "PREVIEW",
    "scope": {
      "total_orders": 10,
      "scope_note": "最近 10 笔订单",
      "retrieved_at": "2026-10-21 22:55:36",
      "source": "order-list"
    },
    "counts": {
      "total": 10,
      "candidates": 4,
      "likely_pending": 3,
      "reviewed": 3,
      "unknown": 1,
      "excluded": 3
    },
    "candidates": [
      {
        "order_id": "DD20261020002",
        "created_at": "2026-10-20 08:12:40",
        "status_code": "0",
        "status_label": "订单已完成",
        "paid_amount": 42.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海徐家汇店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [
          {
            "product_code": "CBO001",
            "name": "麦辣鸡腿堡套餐",
            "quantity": 1
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "likely_pending",
        "review_label": "可能待评价",
        "review_reason": "订单已完成，评价状态码为 0"
      },
      {
        "order_id": "DD20261018003",
        "created_at": "2026-10-18 19:02:11",
        "status_code": "0",
        "status_label": "订单已完成",
        "paid_amount": 31.5,
        "currency": "CNY",
        "store_name": "麦当劳·上海陆家嘴店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [
          {
            "product_code": "DES001",
            "name": "麦旋风",
            "quantity": 2
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "likely_pending",
        "review_label": "可能待评价",
        "review_reason": "订单已完成，评价状态码为 0"
      },
      {
        "order_id": "DD20261017004",
        "created_at": "2026-10-17 18:45:00",
        "status_code": null,
        "status_label": "订单已完成",
        "paid_amount": 12.0,
        "currency": "CNY",
        "store_name": "麦当劳·北京国贸店",
        "store_city": "北京",
        "city_source": "store_name",
        "order_type": "2",
        "order_type_label": "类型码 2（接口未定义）",
        "items": [
          {
            "product_code": "SID001",
            "name": "中薯条",
            "quantity": 1
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "unknown",
        "review_label": "待确认",
        "review_reason": "接口未返回评价状态字段，需用户自行确认"
      },
      {
        "order_id": "DD20261012009",
        "created_at": "2026-10-12 13:10:00",
        "status_code": "0",
        "status_label": "订单已完成",
        "paid_amount": 42.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海陆家嘴店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "likely_pending",
        "review_label": "可能待评价",
        "review_reason": "订单已完成，评价状态码为 0"
      }
    ],
    "pending": [
      {
        "order_id": "DD20261020002",
        "created_at": "2026-10-20 08:12:40",
        "status_code": "0",
        "status_label": "订单已完成",
        "paid_amount": 42.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海徐家汇店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [
          {
            "product_code": "CBO001",
            "name": "麦辣鸡腿堡套餐",
            "quantity": 1
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "likely_pending",
        "review_label": "可能待评价",
        "review_reason": "订单已完成，评价状态码为 0"
      },
      {
        "order_id": "DD20261018003",
        "created_at": "2026-10-18 19:02:11",
        "status_code": "0",
        "status_label": "订单已完成",
        "paid_amount": 31.5,
        "currency": "CNY",
        "store_name": "麦当劳·上海陆家嘴店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [
          {
            "product_code": "DES001",
            "name": "麦旋风",
            "quantity": 2
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "likely_pending",
        "review_label": "可能待评价",
        "review_reason": "订单已完成，评价状态码为 0"
      },
      {
        "order_id": "DD20261012009",
        "created_at": "2026-10-12 13:10:00",
        "status_code": "0",
        "status_label": "订单已完成",
        "paid_amount": 42.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海陆家嘴店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "likely_pending",
        "review_label": "可能待评价",
        "review_reason": "订单已完成，评价状态码为 0"
      }
    ],
    "reviewed": [
      {
        "order_id": "DD20261020001",
        "created_at": "2026-10-20 12:31:05",
        "status_code": "8",
        "status_label": "订单已完成",
        "paid_amount": 55.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海南京东路店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [
          {
            "product_code": "BUR001",
            "name": "巨无霸",
            "quantity": 1
          },
          {
            "product_code": "DRK001",
            "name": "可口可乐(中)",
            "quantity": 1
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "reviewed",
        "review_label": "已评价",
        "review_reason": "orderStatusCode=8"
      },
      {
        "order_id": "DD20261016005",
        "created_at": "2026-10-16 11:20:30",
        "status_code": "8",
        "status_label": "订单已完成",
        "paid_amount": 38.5,
        "currency": "CNY",
        "store_name": "麦当劳·深圳华强北店",
        "store_city": "深圳",
        "city_source": "field",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "reviewed",
        "review_label": "已评价",
        "review_reason": "orderStatusCode=8"
      },
      {
        "order_id": "DD20261011010",
        "created_at": "2026-10-11 19:40:00",
        "status_code": "8",
        "status_label": "订单已完成",
        "paid_amount": 26.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海南京东路店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "reviewed",
        "review_label": "已评价",
        "review_reason": "orderStatusCode=8"
      }
    ],
    "unknown": [
      {
        "order_id": "DD20261017004",
        "created_at": "2026-10-17 18:45:00",
        "status_code": null,
        "status_label": "订单已完成",
        "paid_amount": 12.0,
        "currency": "CNY",
        "store_name": "麦当劳·北京国贸店",
        "store_city": "北京",
        "city_source": "store_name",
        "order_type": "2",
        "order_type_label": "类型码 2（接口未定义）",
        "items": [
          {
            "product_code": "SID001",
            "name": "中薯条",
            "quantity": 1
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "unknown",
        "review_label": "待确认",
        "review_reason": "接口未返回评价状态字段，需用户自行确认"
      }
    ],
    "excluded": [
      {
        "order_id": "DD20261015006",
        "created_at": "2026-10-15 09:05:00",
        "status_code": null,
        "status_label": "订单已取消",
        "paid_amount": 28.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海徐家汇店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "not_eligible",
        "review_label": "不适用",
        "review_reason": "订单已取消或已关闭"
      },
      {
        "order_id": "DD20261014007",
        "created_at": "2026-10-14 12:00:00",
        "status_code": null,
        "status_label": "待支付",
        "paid_amount": 15.5,
        "currency": "CNY",
        "store_name": "麦当劳·上海徐家汇店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "not_eligible",
        "review_label": "不适用",
        "review_reason": "订单未完成支付"
      },
      {
        "order_id": "DD20261013008",
        "created_at": "2026-10-13 12:30:00",
        "status_code": null,
        "status_label": "配送中",
        "paid_amount": 20.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海人民广场店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "3",
        "order_type_label": "类型码 3（接口未定义）",
        "items": [],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "not_eligible",
        "review_label": "不适用",
        "review_reason": "订单仍在进行中"
      }
    ],
    "next_action": {
      "label": "去官方 App 查看评价入口",
      "path": "麦当劳官方 App → 我的 → 订单 → 选择该订单 → 评价"
    },
    "reward": {
      "pending": 4,
      "tiers": [
        {
          "count": 1,
          "gift": "小可乐"
        },
        {
          "count": 2,
          "gift": "中可乐"
        },
        {
          "count": 3,
          "gift": "小薯条"
        }
      ],
      "reached": [
        {
          "count": 1,
          "gift": "小可乐"
        },
        {
          "count": 2,
          "gift": "中可乐"
        },
        {
          "count": 3,
          "gift": "小薯条"
        }
      ],
      "next": null,
      "text": "已达成最高档 3 好评（小薯条）。",
      "note": "档位规则因门店而异，以门店为准；评价请基于真实用餐体验。"
    },
    "empty_reason": null,
    "text": "待评价候选：4 笔\n统计范围：最近 10 笔订单\n\n2026-10-20  麦当劳·上海徐家汇店  ¥42.00  可能待评价\n2026-10-18  麦当劳·上海陆家嘴店  ¥31.50  可能待评价\n2026-10-17  麦当劳·北京国贸店  ¥12.00  待确认\n2026-10-12  麦当劳·上海陆家嘴店  ¥42.00  可能待评价\n\n其中 1 笔接口未返回评价状态，标为「待确认」；评过后请在清点里点「已评过」。\n另有 3 笔未完成或已取消订单未纳入统计。\n\n评价兑礼：已达成最高档 3 好评（小薯条）。\n（按 4 笔待确认估算，标记「已评过」后会重算）\n\n去官方 App 查看评价入口 →\n路径：麦当劳官方 App → 我的 → 订单 → 选择该订单 → 评价"
  },
  "invoice": {
    "state": "HANDOFF",
    "filters": {
      "city": "上海",
      "store": null,
      "date_from": null,
      "date_to": null,
      "min_amount": null,
      "max_amount": null
    },
    "candidates": [
      {
        "order_id": "DD20261020001",
        "created_at": "2026-10-20 12:31:05",
        "status_code": "8",
        "status_label": "订单已完成",
        "paid_amount": 55.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海南京东路店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [
          {
            "product_code": "BUR001",
            "name": "巨无霸",
            "quantity": 1
          },
          {
            "product_code": "DRK001",
            "name": "可口可乐(中)",
            "quantity": 1
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "reviewed",
        "review_label": "已评价",
        "review_reason": "orderStatusCode=8"
      },
      {
        "order_id": "DD20261020002",
        "created_at": "2026-10-20 08:12:40",
        "status_code": "0",
        "status_label": "订单已完成",
        "paid_amount": 42.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海徐家汇店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [
          {
            "product_code": "CBO001",
            "name": "麦辣鸡腿堡套餐",
            "quantity": 1
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "likely_pending",
        "review_label": "可能待评价",
        "review_reason": "订单已完成，评价状态码为 0"
      },
      {
        "order_id": "DD20261018003",
        "created_at": "2026-10-18 19:02:11",
        "status_code": "0",
        "status_label": "订单已完成",
        "paid_amount": 31.5,
        "currency": "CNY",
        "store_name": "麦当劳·上海陆家嘴店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [
          {
            "product_code": "DES001",
            "name": "麦旋风",
            "quantity": 2
          }
        ],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "likely_pending",
        "review_label": "可能待评价",
        "review_reason": "订单已完成，评价状态码为 0"
      },
      {
        "order_id": "DD20261012009",
        "created_at": "2026-10-12 13:10:00",
        "status_code": "0",
        "status_label": "订单已完成",
        "paid_amount": 42.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海陆家嘴店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "likely_pending",
        "review_label": "可能待评价",
        "review_reason": "订单已完成，评价状态码为 0"
      },
      {
        "order_id": "DD20261011010",
        "created_at": "2026-10-11 19:40:00",
        "status_code": "8",
        "status_label": "订单已完成",
        "paid_amount": 26.0,
        "currency": "CNY",
        "store_name": "麦当劳·上海南京东路店",
        "store_city": "上海",
        "city_source": "store_name",
        "order_type": "1",
        "order_type_label": "类型码 1（接口未定义）",
        "items": [],
        "source": "order-list",
        "retrieved_at": "2026-10-21 22:55:36",
        "review_state": "reviewed",
        "review_label": "已评价",
        "review_reason": "orderStatusCode=8"
      }
    ],
    "excluded": [
      {
        "order_id": "DD20261017004",
        "reason": "城市不匹配"
      },
      {
        "order_id": "DD20261016005",
        "reason": "城市不匹配"
      },
      {
        "order_id": "DD20261015006",
        "reason": "订单状态为「订单已取消」，非已支付或已完成"
      },
      {
        "order_id": "DD20261014007",
        "reason": "订单状态为「待支付」，非已支付或已完成"
      },
      {
        "order_id": "DD20261013008",
        "reason": "订单状态为「配送中」，非已支付或已完成"
      }
    ],
    "count": 5,
    "total_amount": 196.5,
    "reimbursement": {
      "target": 50.0,
      "reachable": true,
      "available_total": 196.5,
      "selected": [
        "DD20261020001"
      ],
      "selected_total": 55.0,
      "overshoot": 5.0,
      "gap": 0.0,
      "text": "报销门槛 ¥50.00：选 1 笔，合计 ¥55.00，超出 ¥5.00。"
    },
    "profile": {
      "company_name": "上海示例科技有限公司",
      "tax_id_masked": "9135**********0Y43",
      "email_masked": "f***@example.com",
      "errors": [],
      "warnings": [],
      "ok": true,
      "uscc_valid": true,
      "email_present": true
    },
    "ready": true,
    "handoff": {
      "label": "打开官方 App",
      "path": "麦当劳官方 App / 小程序 → 我的 → 订单 → 选择订单 → 申请开票",
      "auto_submit": false,
      "reason": "issue-invoice 未在公开工具列表，且发票须由用户本人提交"
    },
    "warnings": [],
    "text": "找到 5 笔上海订单，实付合计 ¥196.50\n\n☑ 2026-10-20  麦当劳·上海南京东路店  ¥55.00\n☑ 2026-10-20  麦当劳·上海徐家汇店  ¥42.00\n☑ 2026-10-18  麦当劳·上海陆家嘴店  ¥31.50\n☑ 2026-10-12  麦当劳·上海陆家嘴店  ¥42.00\n☑ 2026-10-11  麦当劳·上海南京东路店  ¥26.00\n注意：5 笔订单的城市按门店名推断，非接口字段，请以官方 App 为准。\n\n抬头：上海示例科技有限公司\n税号：9135**********0Y43\n邮箱：f***@example.com\n\n下一步：打开麦当劳官方 App，在对应订单中提交开票。\n路径：麦当劳官方 App / 小程序 → 我的 → 订单 → 选择订单 → 申请开票\n说明：本工具不代替你提交发票，也不会修改任何订单信息。",
    "reimbursements": {
      "50": {
        "target": 50.0,
        "reachable": true,
        "available_total": 196.5,
        "selected": [
          "DD20261020001"
        ],
        "selected_total": 55.0,
        "overshoot": 5.0,
        "gap": 0.0,
        "text": "报销门槛 ¥50.00：选 1 笔，合计 ¥55.00，超出 ¥5.00。"
      },
      "100": {
        "target": 100.0,
        "reachable": true,
        "available_total": 196.5,
        "selected": [
          "DD20261020002",
          "DD20261012009",
          "DD20261011010"
        ],
        "selected_total": 110.0,
        "overshoot": 10.0,
        "gap": 0.0,
        "text": "报销门槛 ¥100.00：选 3 笔，合计 ¥110.00，超出 ¥10.00。"
      }
    }
  },
  "lottery": {
    "state": "PREVIEW",
    "summary": {
      "activity_id": "2m2t",
      "activity_name": "麦麦幸运抽",
      "status": "进行中",
      "resource_type": "points",
      "available_count": 2,
      "available_point": 320,
      "draw_cost": 100,
      "cost_unit": "积分",
      "prizes": [
        {
          "name": "免费中薯条",
          "type_text": "优惠券",
          "valid_date": null
        },
        {
          "name": "麦金卡 7 天体验",
          "type_text": "权益卡",
          "valid_date": null
        },
        {
          "name": "满 30 减 5 券",
          "type_text": "优惠券",
          "valid_date": null
        }
      ],
      "eligible": true,
      "reason": "积分充足，可参与抽奖",
      "retrieved_at": "2026-10-21 22:55:36"
    },
    "staleness": {
      "retrieved_at": "2026-10-21 22:55:36",
      "ttl_seconds": 30,
      "age_seconds": 0,
      "is_stale": false,
      "state": "PREVIEW",
      "label": "数据有效"
    },
    "closed": false,
    "text": "抽奖活动：麦麦幸运抽（进行中）\n单次消耗：100 积分\n可用资源：积分 320 / 次数 2\n参与条件：积分充足，可参与抽奖\n\n奖品：\n- 免费中薯条（优惠券）\n- 麦金卡 7 天体验（权益卡）\n- 满 30 减 5 券（优惠券）"
  }
};

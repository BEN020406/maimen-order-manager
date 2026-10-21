# 麦当劳 MCP 能力与字段对照

接入地址 `https://mcp.mcd.cn`，Streamable HTTP，`Authorization: Bearer <MCP_TOKEN>`。
**Token 由 WorkBuddy 连接器注入，本技能不读取、不缓存、不落盘。**

> 字段名以运行时 `tools/list` 与实际返回为准。下表是按 2026-10 官方文档核对的结果，
> 与本技能容错解析所覆盖的候选键。

## 一、用到的工具（均为公开工具）

| 工具 | 中文名 | 入参 | 本技能用途 |
|---|---|---|---|
| `order-list` | 查询历史订单 | 无 | **待评价与开票的主数据源**，最多最近 10 笔 |
| `query-order` | 查询订单详情 | `orderId` | 明细/金额补全（可选） |
| `query-lottery-info` | 查看积分抽奖活动信息 | 无 | 活动状态、奖品、消耗、可用资源 |
| `draw-lottery` | 积分抽奖 | 无 | **单次**执行，1 秒内不可重复调用 |
| `query-my-prizes` | 查看我的奖品 | `pageNum`、`pageSize`(≤20) | 历史奖品 |
| `now-time-info` | 当前时间 | 无 | 判断日期范围（可选） |

**不存在于公开列表、不得调用**：`issue-invoice`（发票提交）、`submit-review`（评价提交）。
`create-order`、`auto-bind-coupons` 等点餐/领券工具属于策略禁用，不进入本技能流程。

## 二、字段对照与容错键

### order-list / query-order

| 契约字段 | 官方字段 | 容错候选键 | 说明 |
|---|---|---|---|
| `order_id` | `orderId` | `orderId, order_id, orderNo, orderCode, id` | 展示时最小化 |
| `created_at` | `createTime` | `createTime, createdAt, orderTime` | `yyyy-MM-dd HH:mm:ss` |
| `status_code` | **接口不返回** | `orderStatusCode, statusCode` | 交付稿约定的 8=已评价在真实接口中不存在；有则兼容，无则标「待确认」 |
| `status_label` | `orderStatus` | `orderStatus, orderStatusText, statusText` | **字符串**，如「订单已完成」 |
| `paid_amount` | `realTotalAmount` | `realTotalAmount, realPayAmount, payAmount, paidAmount, totalAmount` | 单位：元 |
| `store_name` | `storeName` | `storeName, store_name, storeTitle` | — |
| `store_city` | **无此字段** | `storeCity, cityName, city` | 缺失时从门店名推断并标注 |
| `order_type` | `orderType` | `orderType, takeWay, channel` | 数字码含义未公开 |
| `items[]` | `orderProductList` | `orderProductList, productList, items` | `productCode/productName/quantity` |

### query-lottery-info

`activityCode`、`activityName`、`activityStatusText`、`beginTime`、`endTime`、
`drawPoint`（单次消耗积分）、`availableTimes`、`availablePoint`、
`drawDecision.resourceEligible`、`drawDecision.reason`、`prizes[].name/typeText`。

### draw-lottery

`status.code`（失败如 `DRAW_FAILED`）、`status.message`、`win`、`prizes[]`、
`consumePoint`、`remainPoint`、`remainChance`。

### query-my-prizes

`prizes[].name`、`recordTime`、`prizeTypeText`、`statusText`、`timeRemindText`。

## 三、真实联调结论（2026-10-21，直连 mcp.mcd.cn）

用真实 Token 完成 `initialize` → `tools/list` → 三次 `tools/call`，结论如下：

| 项 | 交付稿假设 | 实测结果 |
|---|---|---|
| 工具总数 | 35~40 | **35 个** |
| `orderStatusCode` | 8 = 已评价 | **不存在**；`order-list` 与 `query-order` 均无任何评价字段 |
| 订单城市 | 有字段 | **无**（只有 `storeName` / `storeAddress`） |
| `order-list` 条数 | 最近 10 笔 | **确认 10 笔**，全部「订单已完成」 |
| `issue-invoice` | 未公开 | **确认不存在** |
| `submit-review` | 未公开 | **确认不存在** |
| 抽奖字段 | drawPoint / availablePoint / drawDecision | **完全符合**；但**无** `availableTimes` |
| 积分精度 | 整数 | `availablePoint=4782.6`，**是浮点** |

由此带来的两个设计变更：

1. **待评价改为「接口列表 + 本地记忆」**：接口给不出评价状态，就无法自动判定。
   工具列出所有已完成订单并标「待确认」，用户评过后点「已评过」，
   标记只以**订单号哈希**存在本机 `localStorage`（`mm.reviewed.v1`），不存订单原文、不上传。
2. **不再声称「已评价/未评价」**：文案统一为「待确认」，避免把平台的未知说成已知。

其余偏差（历史记录）：

| 偏差 | 影响 | 处理 |
|---|---|---|
| 订单状态是字符串 `orderStatus` | 只按数字 8 判定会全部落空 | 有码看码，无码看文案，再降级为「待确认」 |
| 订单无城市字段 | 无法严格按城市筛选 | 从门店名匹配城市并标注「推断」 |
| `order-list` 只返回最近 10 笔 | 不能承诺全量历史 | 输出固定写「统计范围：最近 N 笔订单」 |
| 金额单位：订单侧为元，`calculate-price` 为分 | 混用会差 100 倍 | 只读订单侧金额 |

## 四、能力矩阵输出示例

```text
已发现 35 个 MCP 工具

模块能力：
- 待评价订单：完整（所需工具均已就绪）
- 发票助手：完整（所需工具均已就绪）
- 抽奖管家：完整（所需工具均已就绪）

交接模式：
- 发票提交：未公开接口，整理清单后交官方 App
- 评价提交：未公开接口，仅展示状态
```

`mode` 取值：`full` / `degraded`（部分工具缺失）/ `unsupported`（缺必需工具）。

## 五、TTL 与刷新

| 数据 | TTL | 过期行为 |
|---|---|---|
| 订单 | 300 秒 | 提示重新查询，不展示执行按钮 |
| 抽奖资源 | 30 秒 | **执行前必须刷新**，否则拒绝进入确认 |
| 抽奖结果 | 立即核验 | 超时只查状态，不重试 |
| 发票资料 | 仅当前会话 | 不写磁盘 |

## 六、错误码

| code | 原因 | 处理 |
|---|---|---|
| 401 | Token 无效/过期/未提供 | 让用户在连接器里重新配置，**不要索取 Token 原文** |
| 429 | 超过 600 次/分钟 | 降低频率、合并请求；抽奖同样不得重试 |
| `DRAW_FAILED` | 活动结束/无资格等 | 展示 `status.message`，引导重新查询，不重试 |

---
name: maimen-order-manager
description: 麦门订单管家。当用户想查「有没有没评价的订单」「哪些订单能开发票」「积分抽奖活动/我的奖品」时使用；也适用于「我还有多少单没评价」「找出上海最近能开发票的麦当劳订单」「查一下现在有没有抽奖」「抽一次」。它通过麦当劳中国 MCP 读取近期订单与抽奖信息，自动统计待评价候选、整理开票清单、单次执行抽奖，并在每个外部动作前给出预览和单独确认。本技能不提供省钱点餐、优惠组合优化、在线试算或自动下单。
agent_created: true
---

# 麦门订单管家

个人效率工具 · **非麦当劳官方产品**。本技能只做三件事：把「还没评价的订单」「能开票的订单」「抽奖活动」整理清楚，最后一步交给用户自己在官方 App 完成。

> 一句话分工：**MCP 取数 → `scripts/` 做确定性计算 → 你负责讲清楚 + 拿到确认 → 官方 App 收尾。**

## 何时使用

- "我还有多少单没评价？""帮我看看哪些订单没评价"
- "我要开发票""找出上海最近能开发票的订单""这笔能开票吗"
- "查一下现在有没有抽奖""我的奖品还有哪些""抽一次"
- 用户提到「权益」「待办」「积压的订单」「发票抬头」

**不适用**：点餐、凑满减、算最省钱的组合、代下单一律不做。用户提出这类需求时，直接说明本技能不覆盖，不要拐回旧主线。

## 铁律（违反即返工）

1. **先发现能力，再动手**。每次会话先跑 `capabilities` 解析 `tools/list`；不假设 `issue-invoice`、`submit-review` 存在，也不虚构工具名。
2. **接口不返回评价状态（已实测）**。`order-list` / `query-order` 都没有任何评价字段，
   `orderStatusCode` 不存在。因此只把「已完成」订单列为候选并标「待确认」，
   由用户点「已评过」在**本机浏览器**记住；绝不声称平台确认「未评价」，也不代写评价。
   若未来接口返回 `orderStatusCode=8`，按已评价处理（代码已兼容）。
3. **统计口径只承诺接口实际返回**。`order-list` 最多返回最近 10 笔，输出必须写「统计范围：最近 N 笔订单」，不说「全部历史」。
4. **绝不猜测字段值**。金额只取订单实付金额；缺失就写「未知」，不补 0、不估算；城市优先取接口字段，只有门店名可依据时标注「推断」。
5. **抽奖只允许单次**。用户明确确认后调用一次 `draw-lottery`；没有「再抽一次」的循环、没有批量、没有无人值守。
6. **超时不重试**。抽奖超时或结果未知 → 只查 `query-lottery-info` / `query-my-prizes` 确认，禁止再次 `draw-lottery`。
7. **不代替用户提交**。不自动提交发票、不自动提交五星评价、不编造消费体验、不修改订单金额/城市/门店。
   兑礼进度只做提醒：告诉用户「还差几单」，不代写评价内容，也不以保证礼品为承诺。
8. **不落敏感数据**。Token 只来自 WorkBuddy 连接配置；税号、邮箱、完整订单原文不写日志、不写文件、不进示例。
9. **凑单只用已有订单**。报销门槛凑单只做组合，不新增/修改订单；凑不够就报差额，
   不要建议用户「再点一单凑数」——那是诱导超支。

## 工作流

### 第 0 步：能力发现

拿到 `tools/list` 的原始返回（存成临时 JSON），执行：

```bash
python scripts/cli.py capabilities --tools /tmp/tools.json
```

- 三个模块都 `完整` → 正常走。
- `发票助手` 显示交接模式 → 正常，最后交给官方 App（这是设计预期，不是故障）。
- 任一模块 `不可用` → 按第 5 节降级，不要硬跑。

### 第 1 步：取数

按用户诉求只取需要的：

| 诉求 | 调用 | 说明 |
|---|---|---|
| 待评价 | `order-list` | 无需入参，取最近订单 |
| 开票 | `order-list` →（必要时）`query-order` | 明细不全时按 `orderId` 补详情 |
| 抽奖 | `query-lottery-info`；历史用 `query-my-prizes`（`pageNum`/`pageSize`≤20） | 记录 `retrieved_at` |

把返回原样写到临时文件（`/tmp/orders.json` 之类），**不要手工改写字段、不要编造订单**。

### 第 2 步：算（用脚本，不要口算）

```bash
# 待评价（默认按 1 小可乐 / 2 中可乐 / 3 小薯条 计算兑礼进度）
python scripts/cli.py orders --input /tmp/orders.json
python scripts/cli.py orders --input /tmp/orders.json --tiers "1:小可乐,2:中可乐,3:小薯条"

# 发票（--target 给报销门槛，会算最少凑单组合；可加 --city 上海 --store 陆家嘴 --from 2026-10-01 --to 2026-10-31）
python scripts/cli.py invoice --input /tmp/orders.json --profile /tmp/profile.json --city 上海 --target 100

# 抽奖活动
python scripts/cli.py lottery-info --input /tmp/lottery.json --history /tmp/prizes.json

# 单次抽奖确认卡（不执行）
python scripts/cli.py lottery-preview --input /tmp/lottery.json
```

加 `--format json` 拿结构化结果做二次加工。**金额、数量、合计一律以脚本输出为准**，不要自己加总。

### 第 3 步：讲清楚 + 拿确认

- 待评价：先说「待评价候选 N 笔」，再说「统计范围」，最后列订单（时间 / 门店 / 金额 / 状态）；有兑礼进度时补一句「还差几单到下一档」。
- 发票：先说候选数与实付合计；用户有报销要求时问一句门槛（50 / 100 或其它），用 `--target` 给出**最少凑单组合与超出额**，凑不够就报差额；展示**脱敏后**的抬头与税号，明确说「本工具不提交发票」。
- 抽奖：必须先出预览——本次操作、消耗、活动、可能奖品、可用资源，然后**等用户确认**。

预览模板（不要省略消耗）：

```text
本次操作：抽奖 1 次
消耗：100 积分
抽奖活动：麦麦幸运抽
可能奖品：免费中薯条、麦金卡 7 天体验
可用资源：积分 320 / 次数 2

[确认抽 1 次] [取消]
```

### 第 4 步：执行或交接

- **抽奖**：仅在用户明确回复确认后，调用**一次** `draw-lottery`（接口限频：1 秒内不可重复调用）。结果用 `python scripts/cli.py lottery-result --input /tmp/draw.json` 解读，再用 `query-lottery-info` 核验资源变化。
- **超时/网络异常**：`python scripts/cli.py lottery-timeout --error "ReadTimeout"` → 只允许查询状态，不重试。
- **发票**：走 `invoice` 命令的交接卡片，给路径 `官方 App / 小程序 → 我的 → 订单 → 选择订单 → 申请开票`。
- **评价**：接口不返回是否已评，所以只列已完成订单 + 引导用户在界面点「已评过」（本机 localStorage 存订单号哈希）。
  绝不代写评价内容、不代提交；用户想写评价时，可把他自己的真实感受整理成草稿。

### 第 5 步：首页快照（可选）

用户想「一眼看还有几件事没处理」时：

```bash
python scripts/cli.py home --orders /tmp/orders.json --lottery /tmp/lottery.json \
  --profile /tmp/profile.json --tools /tmp/tools.json --city 上海
```

待处理总数 = 待评价候选订单与可开票订单的**去重并集**。要让用户看界面，把快照写成 `ui/data.js` 后打开 `ui/index.html`：

```bash
python scripts/cli.py home ... --out ui/data.js --format json
```

## 数据事实与降级

> 下表状态已于 2026-10-21 用真实 Token 直连 `mcp.mcd.cn` 核实：`tools/list` 返回 **35 个工具**。

| 模块 | 依赖工具 | 实测 | 缺失/差异时怎么做 |
|---|---|---|---|
| 待评价 | `order-list`（可选 `query-order`） | 存在；**无任何评价字段** | 只列已完成订单并标「待确认」，用户本地标记「已评过」 |
| 发票 | `order-list` | 存在；无城市字段 | 城市由门店名推断并标注 |
| 抽奖查询 | `query-lottery-info`、`query-my-prizes` | 存在；无 `availableTimes` | 用 `availablePoint` 判断资源，不显示次数 |
| 单次抽奖 | `draw-lottery` | 存在（1 秒限频） | 缺则告知无法抽奖，不给替代方案 |
| 发票提交 | `issue-invoice` | **确认不存在** | 只整理清单 + 官方 App 交接 |
| 评价提交 | `submit-review` | **确认不存在** | 只展示状态 + 官方 App 交接 |

真实返回的关键字段：

```text
order-list:        orderId, orderType, createTime, beType, beCode, storeCode,
                   storeName, orderStatus(字符串), orderProductList, realTotalAmount
                   → 10 笔；无 orderStatusCode、无城市、无评价标记
query-order:       orderStatus, status(内部码，如 40), storeAddress, totalAmount,
                   realTotalAmount, totalDiscountAmount, couponList, takeWay, payId …
                   → 同样无 review/comment/score 字段
query-lottery-info: activityCode(dtx2), activityStatusText, drawPoint(24),
                   availablePoint(4782.6 浮点), drawDecision.resourceEligible, prizes[]
```

字段细节、容错规则与错误码见 [`references/mcp-capabilities.md`](references/mcp-capabilities.md)。

## 空状态与错误文案

| 场景 | 这样说 | 动作 |
|---|---|---|
| 未连接 MCP | 「还没有连接麦当劳 MCP。」 | 指路连接器，不要让用户把 Token 贴进对话 |
| 没有订单 | 「当前返回范围内没有可处理订单。」 | 重新查询 |
| 都评价过了 | 「这些订单都已标记为已评价。」 | 查看全部订单 |
| 有缺字段 | 「N 笔接口未返回评价状态，标为待确认。」 | 引导用户点「已评过」 |
| 无发票接口 | 「暂不支持自动开票，请在官方 App 对应订单中操作。」 | 查看开票清单 |
| 抽奖关闭 | 「当前没有进行中的抽奖活动。」 | 稍后再查 |
| 资源不足 | 「当前资源不足以抽奖。」 | 查看奖品记录 |
| 工具超时 | 「暂时无法确认结果，正在避免重复操作。」 | 查询状态 |

## 资源索引

- [`scripts/cli.py`](scripts/cli.py) —— 统一入口：`capabilities` / `orders` / `invoice` / `lottery-info` / `lottery-preview` / `lottery-result` / `lottery-timeout` / `home` / `demo`（纯标准库）。
- [`scripts/common/contracts.py`](scripts/common/contracts.py) —— 统一数据契约与容错字段解析。
- [`scripts/common/state_machine.py`](scripts/common/state_machine.py) —— 状态机与 TTL（订单 5 分钟、抽奖资源 30 秒），禁止 `VERIFY → EXECUTE`。
- [`scripts/common/redact.py`](scripts/common/redact.py) —— 税号/邮箱/Token/订单号脱敏。
- [`scripts/common/mcp_client.py`](scripts/common/mcp_client.py) —— `tools/list` 能力发现与降级判定。
- [`scripts/operations/orders.py`](scripts/operations/orders.py) —— 待评价统计。
- [`scripts/operations/invoice.py`](scripts/operations/invoice.py) —— 开票候选筛选、USCC 校验、交接卡片。
- [`scripts/operations/lottery.py`](scripts/operations/lottery.py) —— 活动概览、单次确认门、超时核验。
- [`scripts/tests/`](scripts/tests/) —— 99 项测试，改逻辑后必跑：
  `python -m unittest discover -s scripts/tests`（在技能根目录执行）
- [`references/order-status.md`](references/order-status.md) —— 订单状态映射与「可能待评价」判定。
- [`references/invoice-handoff.md`](references/invoice-handoff.md) —— 开票筛选规则与交接话术。
- [`references/ui-spec.md`](references/ui-spec.md) —— 「权益收纳夹」视觉与交互规范。
- [`ui/index.html`](ui/index.html) —— 三卡片界面（配合 `ui/data.js`）。
- [`ui/assets/`](ui/assets/) —— 票券 logo（512/192/64 + favicon）与一次性构建脚本 `build_logo.py`（需 Pillow，运行时不依赖）。

## 改完代码的自检

```bash
python -m unittest discover -s scripts/tests -v   # 99 项必须全绿
python scripts/cli.py demo                        # 四个模块的文本卡片应完整输出
```

测试不通过就不算改完。

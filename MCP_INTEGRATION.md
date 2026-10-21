# 麦当劳 MCP 集成说明

本文说明「麦门订单管家」实际调用了哪些麦当劳 MCP Server 与 Tool、按什么流程调用、
以及这些调用带来了什么业务价值。

> 文中金额与订单均为 `scripts/fixtures/` 下的**示例数据**，不含任何真实账号信息。

---

## 一、接入的 MCP Server

| 项 | 内容 |
|---|---|
| 名称 | 麦当劳中国 MCP（`mcd-mcp`） |
| 地址 | `https://mcp.mcd.cn` |
| 传输 | Streamable HTTP（`type: "streamableHttp"`） |
| 鉴权 | 请求头 `Authorization: Bearer <MCP_TOKEN>` |
| Token 获取 | [open.mcd.cn/mcp](https://open.mcd.cn/mcp) → 登录 → 控制台 → 申请 |
| 工具规模 | `tools/list` 实测返回 **35 个工具** |

客户端配置（Token 使用占位符，不提交真实凭证）：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamableHttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_MCP_TOKEN" }
    }
  }
}
```

## 二、实际调用的 Tool

只用了 5 个，其余 30 个（点餐、领券、团餐、商城等）**一律不调用**。

| # | Tool | 入参 | 本项目的用法 | 为什么需要它 |
|---|---|---|---|---|
| 1 | `order-list` | 无 | 待评价清单 + 开票候选的**唯一数据源** | 提供订单时间、门店、状态、实付金额 |
| 2 | `query-order` | `orderId` | 明细不全时补金额与门店地址 | 列表字段不够时补详情 |
| 3 | `query-lottery-info` | 无 | 活动、奖品、单次消耗、可用积分 | 抽奖前必须知道成本 |
| 4 | `query-my-prizes` | `pageNum`、`pageSize` | 历史奖品 | 抽奖结果核验 |
| 5 | `draw-lottery` | 无 | **用户确认后执行一次** | 唯一有副作用的调用 |

### 刻意不用的 Tool

| Tool | 结论 |
|---|---|
| `issue-invoice` | **不存在**于工具列表（已实测），发票只能交接官方 App |
| `submit-review` | **不存在**，评价只能引导用户自己去写 |
| `create-order` / `mall-create-order` / `auto-bind-coupons` | 属于点餐主线，本技能明确定位为「不代下单、不领券」 |

## 三、调用流程

```text
[1] tools/list              能力发现，判断模块完整/降级/不可用
        ↓
[2] order-list              取最近订单（实测上限 10 笔）
        ↓
[3] 本地确定性计算            状态映射 / 筛选 / 合计 / 凑单组合（不经过模型）
        ↓
[4] query-lottery-info      取活动与资源（仅在涉及抽奖时）
        ↓
[5] 预览 + 确认门             展示本次消耗，等待用户明确确认
        ↓
[6] draw-lottery            仅一次；超时/失败 → 只查状态，绝不重试
        ↓
[7] 本地渲染                 文本卡片 / 三卡片界面
        ↓
[8] 交接官方 App             发票提交、评价撰写
```

### 状态机约束

```text
PREVIEW → AWAIT_CONFIRM → EXECUTE → DONE
                ↓            ↓
             CANCELLED     FAILED ──┐
                ↓                    │
             VERIFY ←── 超时/未知 ────┘
              （VERIFY 不可回到 EXECUTE）
```

`VERIFY → EXECUTE` 与 `FAILED → EXECUTE` 在代码里是非法迁移，用测试锁死——
抽奖最怕重复扣积分，这条不能靠自觉。

### TTL 策略

| 数据 | 有效期 | 过期行为 |
|---|---|---|
| 订单 | 300 秒 | 提示重新查询，不展示执行按钮 |
| 抽奖资源 | 30 秒 | **执行前必须刷新**，否则拒绝进入确认 |

## 四、业务价值

### 4.1 从「逐单翻」到「一句话结论」

示例数据（5 笔上海订单，实付合计 ¥196.50）：

| 用户问题 | 之前 | 现在 |
|---|---|---|
| 还有几单没评价？ | 逐个点开 10 次，靠记忆判断 | 一次调用 → `待评价候选 5 笔`，并标注哪些是「待确认」 |
| 再评几单能换薯条？ | 拿计算器数 | `已达成 2 好评（中可乐）；再评 1 单可达 3 好评（小薯条）` |
| 哪几张能凑够 100？ | 手动加总试错 | `选 3 笔，合计 ¥110.00，超出 ¥10.00` |
| 现在能抽吗？ | 翻 App 找入口 | `24 积分/次，可用 4782 积分，确认后抽 1 次` |

### 4.2 减少「白跑一趟」

好评兑礼是**按单累计**的：1 单换小可乐、2 单换中可乐、3 单换小薯条。
用户到店才发现「还差一单」是常见损失。技能把差额提前算出来。

### 4.3 让发票凑单可执行

公司报销通常要求单次满 50 或 100 元，而单笔订单多为二三十元。
技能在真实订单上做组合求解（≤16 单精确穷举，超出用贪心），
优先「超出最少」、其次「单数最少」，凑不够就如实报差额。

### 4.4 把副作用关进笼子

抽奖是本项目唯一会改变账号资源的操作。设计上有四重约束：

1. 执行前必须展示 `drawDecision.nextConsumption`（本次实际消耗）并获明确确认；
2. 单次闸门（`DrawGuard`）保证同一幂等键只放行一次；
3. 超时统一转入 `VERIFY`，只允许查状态；
4. 状态机层面禁止 `VERIFY/FAILED → EXECUTE`。

## 五、实测结论（2026-10-21）

用真实 Token 完成 `initialize` → `tools/list` → 多次 `tools/call`，验证结果：

| 项 | 交付前假设 | 实测 |
|---|---|---|
| 工具总数 | 35~40 | **35 个** |
| `orderStatusCode = 8` | 有（用来判断是否已评价） | **不存在**；`order-list` 与 `query-order` 均无评价字段 |
| 订单城市字段 | 有 | **没有**，只有 `storeName` / `storeAddress` |
| `order-list` 条数 | 最近 10 笔 | **确认 10 笔** |
| `issue-invoice` / `submit-review` | 未公开 | **确认不存在** |
| 抽奖字段 | `drawPoint` / `availablePoint` / `drawDecision` | **完全符合**；无 `availableTimes` |
| 积分精度 | 整数 | `availablePoint` 为**浮点**（如 4782.6） |

由此产生一个重要的产品决策：

> 接口既然不返回「是否已评价」，工具就不替平台下结论。
> 一律标「待确认」，由用户点「已评过」在本机记住（只存订单号哈希）。
> 这是**能力的边界**，不是降级的妥协。

## 六、字段容错

接口字段在文档、不同工具之间并不完全一致，解析层做了候选键兜底：

| 契约字段 | 主字段 | 容错候选 |
|---|---|---|
| 订单号 | `orderId` | `orderId, order_id, orderNo, orderCode, id` |
| 下单时间 | `createTime` | `createTime, createdAt, orderTime` |
| 状态文案 | `orderStatus` | `orderStatus, orderStatusText, statusText` |
| 实付金额 | `realTotalAmount` | `realTotalAmount, realPayAmount, payAmount, totalAmount` |
| 门店 | `storeName` | `storeName, store_name, storeTitle` |
| 城市 | （接口无） | `storeCity, cityName, city` → 缺失则从门店名推断并标注 |

金额缺失时写「未知」，**不补 0、不估算**；城市为推断时在输出中明确标注。

## 七、错误与限频

| 情况 | 处理 |
|---|---|
| 401 Token 无效 | 提示在连接器里重新配置，不索取 Token 原文 |
| 429 超过 600 次/分钟 | 降低频率、合并请求 |
| `draw-lottery` 频繁调用 | 展示接口原话「操作太频繁，请稍后再试」，**不重试** |
| `DRAW_FAILED` | 展示 `status.message`，引导重新查询活动状态 |
| 网络超时 | 转入 `VERIFY`，只查状态不重试 |

## 八、安全设计

1. **Token 不进入代码**：只存在于 WorkBuddy 连接器配置；本仓库所有示例均为 `YOUR_MCP_TOKEN` 占位符。
2. **不改写数据**：不修改订单金额、门店、城市；不新增订单。
3. **不代提交**：发票与评价的最终提交永远由用户在官方 App 完成。
4. **脱敏**：税号、邮箱、订单号在输出与日志中一律掩码；不落盘、不上传。
5. **最少调用**：只调用完成当前任务所需的工具，不做遍历式抓取。

## 九、代码位置

| 能力 | 文件 |
|---|---|
| 能力发现 / 降级判定 | `scripts/common/mcp_client.py` |
| 统一数据契约与容错解析 | `scripts/common/contracts.py` |
| 状态机与 TTL | `scripts/common/state_machine.py` |
| 订单统计 | `scripts/operations/orders.py` |
| 发票筛选与凑单 | `scripts/operations/invoice.py` |
| 抽奖确认门与核验 | `scripts/operations/lottery.py` |
| 统一入口（9 个子命令） | `scripts/cli.py` |

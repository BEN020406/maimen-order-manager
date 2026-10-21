# 麦门订单管家

> 把麦当劳订单里那些「还没评价、还能开票、还有积分抽奖」的权益尾巴，一次性理清楚。
> 只整理，不代办。

个人效率工具 · **非麦当劳官方产品**，与麦当劳无隶属或授权关系。

---

## 一、它解决什么问题

多数人一个月点十几次麦当劳，却从没算清三笔账：

| 场景 | 规则 | 真实困难 |
|---|---|---|
| 好评兑小食 | 1 个好评换小可乐，2 个换中可乐，3 个换小薯条（各门店略有差异） | 不知道还差几单，常常白跑一趟 |
| 发票报销 | 公司要求单次发票满 50 或 100 元 | 一单只有二三十，得几张凑，手动加总易错 |
| 积分抽奖 | 消耗积分抽券 | 不知道剩多少积分、值不值得抽 |

官方 App 擅长处理**单笔**订单，但不负责回答三个聚合问题：我还差几单能换薯条？哪几张发票能凑够 100？我还有多少积分可以抽？

本技能把分散的状态聚合成一句可执行的结论，把执行留给用户自己。

## 二、目标用户

- 每周点 2 次以上麦当劳、会把好评换成小食的人
- 需要按月凑发票报销的上班族
- 不想为了几十块钱逐条翻订单记录的人

## 三、五个核心能力

| 能力 | 输出示例 |
|---|---|
| 待评价清单 | `待评价候选：10 笔` + 逐单列表（时间 / 门店 / 金额 / 状态） |
| 兑礼进度 | `已达成最高档 3 好评（小薯条）`，或「再评 1 单可达」 |
| 本地已评标记 | 点「已评过」隐藏该行，标记只存本机浏览器 |
| 报销门槛凑单 | `报销门槛 ¥100：选 6 笔，合计 ¥102.80，超出 ¥2.80` |
| 单次抽奖 | `本次操作：抽奖 1 次，消耗 24 积分` + 确认后才执行 |

## 四、安装

### 前置条件

1. WorkBuddy 桌面端（技能运行在本地，依赖本机 Python 与连接器配置）
2. 麦当劳 MCP Token：[open.mcd.cn/mcp](https://open.mcd.cn/mcp) 登录 → 控制台 → 申请

### 第一步：安装技能

把本目录放到 WorkBuddy 技能目录：

```text
~/.workbuddy/skills/maimen-order-manager/
```

（Windows 为 `C:\Users\<你>\.workbuddy\skills\maimen-order-manager\`）

### 第二步：配置 MCP 连接器

WorkBuddy → 左侧「专家 · 技能 · 连接器」→「连接器」→ 右上角「自定义连接器」→「配置 MCP」：

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

⚠️ 三个坑：

- `type` **必须驼峰** `streamableHttp`。写成全小写 `streamablehttp` 客户端不识别，会退化成 OAuth 流程，界面一直显示「未认证」。
- `Authorization` 必须带 `Bearer ` 前缀，只填 Token 会返回 403「校验鉴权authToken必填」。
- 保存后回到列表**启用** `mcd-mcp`，再新开一轮对话，工具才会注入。

### 第三步：验证

```bash
cd ~/.workbuddy/skills/maimen-order-manager
python scripts/cli.py demo              # 离线跑一遍四个模块
python -m unittest discover -s scripts/tests   # 99 项测试应全绿
```

## 五、使用示例

在 WorkBuddy 对话里直接说：

| 你说 | 它做 |
|---|---|
| 我还有多少单没评价 | 拉取最近订单 → 标注待确认 → 给出兑礼进度 |
| 再评几单能换薯条 | 按兑礼档位算差额 |
| 哪几张发票能凑够 100 | 从真实订单里挑最少组合，报超出额 |
| 查一下现在有没有抽奖 | 活动、奖品、单次消耗、可用积分 |
| 抽一次 | **先出预览卡**，你确认后才执行一次 |

命令行也能单独跑：

```bash
python scripts/cli.py orders   --input orders.json
python scripts/cli.py invoice  --input orders.json --target 100
python scripts/cli.py lottery-info --input lottery.json
python scripts/cli.py home --orders orders.json --lottery lottery.json --out ui/data.js
```

## 六、目录结构

```text
maimen-order-manager/
├── README.md                  # 本文件
├── CONTEST_DECLARATION.md     # 参赛声明（官方原文，未改动）
├── MCP_INTEGRATION.md         # MCP Server / Tool / 调用流程
├── workbuddy.md               # WorkBuddy 开发对话上下文
├── SKILL.md                   # 技能入口：触发条件、铁律、工作流
├── references/                # 接口对照、状态规则、发票交接、界面规范
├── scripts/                   # 主体代码（纯标准库）
│   ├── cli.py                 # 9 个子命令统一入口
│   ├── common/                # 契约、状态机、脱敏、能力发现
│   ├── operations/            # 订单、发票、抽奖
│   ├── fixtures/              # 样例数据
│   └── tests/                 # 99 项自动化测试
└── ui/                        # 三卡片界面（index.html + data.js + assets）
```

## 七、设计边界

| 做 | 不做 |
|---|---|
| 列出订单、算差额、给组合 | 代下单、代评价、代提交发票 |
| 抽奖前展示消耗、等确认 | 批量抽、循环抽、无人值守抽 |
| 缺失字段标「未知」 | 猜测金额、城市、评价状态 |
| 税号邮箱脱敏 | 落盘、上传、写日志 |

## 八、已知限制

1. **接口不返回评价状态**：实测 `order-list` 与 `query-order` 都没有评价字段，所以只能标「待确认」，由你点「已评过」。
2. **只覆盖最近 10 笔**：`order-list` 返回上限，不能当全量账单。
3. **发票只能整理不能提交**：公开工具列表没有开票接口。
4. **兑礼档位因门店而异**：默认 1/2/3 档，可配置。
5. **标记只存本机**：换设备或清缓存后需重新标记。

## 九、测试

```bash
python -m unittest discover -s scripts/tests
# Ran 99 tests — OK
```

覆盖：状态映射、兑礼档位、筛选合计、凑单组合、USCC 校验、脱敏、抽奖确认门与超时、能力降级、CLI 集成。

---

参赛作品 · 麦当劳程序员节创意开发大赛。非麦当劳官方产品，输出仅供参考，
餐品与订单信息以麦当劳官方渠道为准。

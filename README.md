<div align="center">
  <img src="assets/banner.svg" alt="麦门助手 MCD Buddy" width="860">
</div>

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="mcp" src="https://img.shields.io/badge/MCP-Streamable%20HTTP-green">
  <img alt="mcd" src="https://img.shields.io/badge/McDonald's%20China-MCP-DA291C">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-lightgrey">
  <img alt="CI" src="https://github.com/janetom645-coder/mcd-buddy/actions/workflows/ci.yml/badge.svg">
</p>

<p align="center">
  <b>一个真正懂麦当劳的 AI 助手</b> —— 基于麦当劳中国官方 MCP，把点餐这件事玩出四种花样。
</p>

---

## 👋 认识一下麦麦

<div align="center">
  <img src="assets/mascot.svg" alt="吉祥物麦麦" width="180">
</div>

**麦麦**是麦门助手的吉祥物——一只圆滚滚的汉堡小人，头顶金拱门小帽，笑眯眯的。
它每天的工作，就是帮你把「吃麦当劳」这件小事，变得更有趣、更明白、更划算。

---

## 🎮 四大玩法

<table>
<tr>
<td align="center" width="25%"><img src="assets/icon-practice.svg" alt="修行录" width="96"><br><b>🧘 修行录</b></td>
<td align="center" width="25%"><img src="assets/icon-group-meal.svg" alt="团餐指挥官" width="96"><br><b>🍱 团餐指挥官</b></td>
<td align="center" width="25%"><img src="assets/icon-hidden-menu.svg" alt="隐藏菜单实验室" width="96"><br><b>🧪 隐藏菜单实验室</b></td>
<td align="center" width="25%"><img src="assets/icon-fortune.svg" alt="每日运势签" width="96"><br><b>🔮 每日运势签</b></td>
</tr>
<tr>
<td valign="top">点餐即打卡，解锁成就徽章与「麦门段位」</td>
<td valign="top">一群人的点单自动合成最优团餐，凑满减、卡预算、避忌口</td>
<td valign="top">用套餐替换选项重组配方，实时对比营养与价格</td>
<td valign="top">今天宜吃啥 + 今日活动 + 抽奖吉时，仪式感拉满</td>
</tr>
<tr>
<td valign="top"><code>order-list</code><br><code>query-my-account</code><br><code>query-my-coupons</code><br><code>query-my-prizes</code><br><code>now-time-info</code></td>
<td valign="top"><code>query-nearby-stores</code><br><code>query-meals</code><br><code>calculate-price</code><br><code>query-my-coupons</code><br><code>query-store-coupons</code></td>
<td valign="top"><code>query-meal-detail</code><br><code>list-nutrition-foods</code><br><code>calculate-price</code></td>
<td valign="top"><code>now-time-info</code><br><code>list-nutrition-foods</code><br><code>campaign-calendar</code><br><code>query-lottery-info</code><br><code>query-my-prizes</code></td>
</tr>
</table>

---

## ✨ 长这样

### 🧘 修行录 —— 把吃麦当劳变成一场修行

```text
  🍟 麦门修行录 🍔
  MCD Buddy · 点餐即修行
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

╭─ 🧘 我的修行进度 ──────────────────────────────────────╮
│ 📅 修行日期：2026-10-10                                │
│ 🎖️ 当前段位：麦门学徒                                  │
│ 🍟 ▰▰▰▰▱▱▱▱▱▱▱▱ 3/10　距「麦门弟子」还差 7 单          │
╰────────────────────────────────────────────────────────╯

▍ 📊 修行数据

| 指标 | 数值 |
| --- | --- |
| 🍔 累计点餐 | 8 单 |
| 💸 累计消费 | ¥138.00 |
| 🌅 早餐修行 | 2 次 |
| ☕ 咖啡因摄入 | 2 杯 |
| 🏅 可用积分 | 2860.5 分 |
| 🎟️ 卡包券数 | 3 张 |

▍ 🏅 成就徽章　5/12

|  | 成就 | 达成条件 | 状态 |
| --- | --- | --- | --- |
| 🌙 | 「深夜食堂」 | 在 21:00 之后点过餐 | ✅ |
| 🏅 | 「单品收集家」 | 点过 8 种以上不同单品 | ✅ |
| 🔒 | 「巨无霸十人斩」 | 累计点过 10 个巨无霸 | — |
```

### 🍱 团餐指挥官 —— 一群人的点单终于不用吵了

```text
╭─ 🍱 本次团餐 ──────────────────────────────────────────╮
│ 👥 团餐人数：4 人                                      │
│ 🏪 取餐门店：麦当劳深圳福华一路(卓悦中心)餐厅          │
│ 🛵 取餐方式：到店自取                                  │
│ 💰 预计应付：¥70.00                                    │
│ 🍔 人均分摊：¥17.50                                    │
╰────────────────────────────────────────────────────────╯

| 伙伴 | 推荐单品 | 单价 | 依据 |
| --- | --- | --- | --- |
| 小王 | 巨无霸 | ¥24.50 | 想吃「牛肉」 · 预算 ¥25 |
| 小李 | 麦香鸡 | ¥15.50 | 想吃「鸡肉」 · 预算 ¥20 · 忌口 辣 |
| 小张 | 麦香鱼 | ¥17.50 | 想吃「鱼」 · 预算 ¥15 |
| 小周 | 大杯鲜萃咖啡 | ¥12.50 | 想吃「咖啡」 · 预算 ¥18 |

⚠️ 匹配说明：
  · **小张**：超预算 ¥2.50
```

### 🧪 隐藏菜单实验室 —— 人人都能发明自己的麦当劳

```text
╭─ 🧪 我的隐藏配方 ──────────────────────────────────────╮
│ 🍔 配方名称：全明星双人分享餐八件套·减脂版             │
│ 🧾 基础套餐：全明星双人分享餐八件套（9900011056）      │
╰────────────────────────────────────────────────────────╯

▍ 🔧 改配说明

- 选择汉堡：麦辣鸡腿汉堡 ➜ 板烧鸡腿堡
- 选择小食：麦乐鸡4块 ➜ 脆薯饼
- 选择小食：麦辣鸡翅2块 ➜ 麦乐鸡4块（+¥1）
- 选择小食：中薯条 ➜ 小杯玉米杯
- 选择套餐内饮料：可乐中杯 ➜ 无糖可口可乐中杯

▍ 📈 营养对比

| 指标 | 原配方 |  | 新配方 | 变化 |
| --- | --- | --- | --- | --- |
| 🔥 能量 | 2150 kcal | ➜ | 1212 kcal | -938 kcal |
| 🧈 脂肪 | 90 g | ➜ | 55 g | -35 g |
| 🍚 碳水 | 245 g | ➜ | 111 g | -134 g |

▍ 💰 价格

| 版本 | 价格 |
| --- | --- |
| 原套餐 | ¥114.50 |
| **减脂版** | **¥115.50** |

定价来源：已通过 calculate-price 实时核算
```

### 🔮 每日运势签 —— 今天宜吃巨无霸

```text
╭─ 🔮 麦门灵签 ──────────────────────────────────────────╮
│ 🎋 签　等：中吉                                        │
│ 📅 日　期：2026-10-10 星期六                           │
│                                                        │
│ 📜 签　文：咖啡入喉，万事不愁。今日宜早起，忌拖延。    │
╰────────────────────────────────────────────────────────╯

▍ 🍟 今日宜吃

| 推荐 | 说明 |
| --- | --- |
| 🥇 高达吉士双牛堡 | 今日头牌，主推　448 kcal · 蛋白 26g |
| 🥈 猪柳蛋麦满分 | 搭配之选，可加购　387 kcal · 蛋白 23g |

▍ 🎰 抽奖吉时

| 项目 | 今日指引 |
| --- | --- |
| ⏰ 吉时 | 09:00 - 10:00 |
| 🎁 抽奖活动 | 周六麦金喜抽奖（进行中） |
| 💳 单次消耗 | 本次将消耗 24 积分 |
```

> 📎 完整输出见 [`examples/sample-outputs.md`](examples/sample-outputs.md)

---

## 🚀 快速开始

### 1️⃣ 申请麦当劳 MCP Token

前往 **[https://open.mcd.cn/mcp](https://open.mcd.cn/mcp)** → 右上角【登录】→ 手机号验证 → 【控制台】→【激活】→ 复制 Token。

### 2️⃣ 安装

```bash
git clone https://github.com/janetom645-coder/mcd-buddy.git
cd mcd-buddy
pip install -r requirements.txt
pip install -e .
```

### 3️⃣ 先玩离线演示（不需要 Token）

```bash
mcd-buddy practice --demo
mcd-buddy group-meal --demo
mcd-buddy hidden-menu --meal 双人分享餐 --preset 减脂 --demo
mcd-buddy fortune --demo
```

### 4️⃣ 接上真实麦当劳 MCP

```bash
export MCD_MCP_TOKEN="你的 Token"   # Windows: set MCD_MCP_TOKEN=...

# 修行录 / 运势签 只用你的账号数据，直接跑
mcd-buddy practice
mcd-buddy fortune

# 团餐 / 隐藏菜单 需要先定位门店
mcd-buddy group-meal --city 深圳市 --keyword 麦当劳
mcd-buddy hidden-menu --city 深圳市 --keyword 麦当劳 --meal 双人分享餐 --preset 增肌
```

---

## 🧭 命令一览

| 命令 | 说明 | 关键参数 |
|---|---|---|
| `mcd-buddy practice` | 🧘 修行录 | — |
| `mcd-buddy group-meal` | 🍱 团餐指挥官 | `--people "名字:预算:忌口;…"`（也支持 JSON / `@file`） |
| `mcd-buddy hidden-menu` | 🧪 隐藏菜单实验室 | `--meal <名称或编码>` `--preset 减脂\|增肌\|解馋\|清醒` `--swap 轮次=商品` `--list` |
| `mcd-buddy fortune` | 🔮 每日运势签 | — |
| `mcd-buddy tools` | 列出 MCP Server 全部工具 | — |

**通用参数**

| 参数 | 说明 |
|---|---|
| `--demo` | 离线演示模式，无需 Token |
| `--token` | 指定 MCP Token（默认读环境变量 `MCD_MCP_TOKEN`） |
| `--json` | 输出 JSON（含**未拆信封**的原始工具返回 + 渲染结果） |
| `--city` | 城市名（默认 `深圳市`，也可用环境变量 `MCD_CITY`） |
| `--keyword` | 门店关键词（默认 `麦当劳`，也可用环境变量 `MCD_KEYWORD`） |
| `--store` | 直接指定门店编码，跳过搜索 |

> 💡 `--city` / `--keyword` 只在团餐指挥官和隐藏菜单实验室生效 —— 其余两个模块只用你的账号数据，不依赖门店。

<details>
<summary>🍱 团餐指挥官：自定义伙伴需求</summary>

**写法一：直接说人话**（推荐，每个人用 `;` 分隔，字段用 `:` 分隔）

```bash
mcd-buddy group-meal --city 深圳市 --keyword 麦当劳 \
  --people "小王:25:要牛肉;小李:20:要鸡肉:不要辣;小张:15:要鱼"
```

字段按内容自动归类：纯数字 = 预算，`不要/忌/免…` 开头 = 忌口，`要/想吃…` 开头 = 口味，
其余第一个字段 = 名字。`--people "小王:预算25:不要辣,不要香菜"` 这种混写也能识别。

**写法二：JSON**（适合脚本调用）

```bash
mcd-buddy group-meal --city 深圳市 --keyword 麦当劳 --people \
  '[{"name":"小王","budget":25,"want":"牛肉"},
    {"name":"小李","budget":20,"want":"鸡肉","avoid":["辣"]}]'
```

**写法三：从文件读取** —— `--people @examples/people.json`

字段说明：`name` 姓名、`budget` 预算（元）、`want` 想吃什么、`avoid` 忌口列表。

匹配优先级：**忌口 > 口味 > 预算**。预算内取**最接近预算**的一份，而不是最便宜的那份；
如果为了满足口味不得不超预算，会在「匹配说明」里写明。
</details>

<details>
<summary>🧪 隐藏菜单实验室：自定义替换</summary>

先看看这个门店有什么、套餐能怎么换：

```bash
mcd-buddy hidden-menu --list --city 深圳市 --keyword 麦当劳
mcd-buddy hidden-menu --city 深圳市 --keyword 麦当劳 --meal 双人分享餐
```

再按「轮次 = 商品」指定替换（轮次可以是编号，也可以是名称）：

```bash
# 按编号
mcd-buddy hidden-menu --city 深圳市 --keyword 麦当劳 --meal 9900011056 \
  --swap "1=巨无霸" --swap "6=纯牛奶"

# 按轮次名称
mcd-buddy hidden-menu --city 深圳市 --keyword 麦当劳 --meal 双人分享餐 \
  --swap "选择套餐内饮料=大杯鲜萃咖啡"
```

> ⚠️ 替换只能选该轮次**真实存在的选项**，否则门店会返回「商品已售罄或不可售」。
> 程序会替你校验，不合法就自动退回默认选项。
</details>

---

## 🏗️ 项目结构

```text
mcd-buddy/
├── assets/                  # 🎨 手绘卡通视觉资产（SVG，可缩放不糊）
│   ├── banner.svg           # README 头图
│   ├── mascot.svg           # 吉祥物「麦麦」
│   ├── icon-*.svg           # 四大模块图标
│   └── IMAGE_BRIEF.md       # 外部插画生成需求书
├── src/mcd_buddy/
│   ├── theme.py             # 🎨 卡通主题：金拱门艺术字 / 卡片 / 薯条进度条
│   ├── mcp_client.py        # 麦当劳 MCP 客户端（Streamable HTTP + 瞬时故障退避重试）
│   ├── mcd_api.py           # 🔌 业务层：信封拆解 / 门店前置 / 分→元 / rounds 解析
│   ├── demo.py              # 离线演示数据（与真实响应同构）
│   ├── utils.py             # 结果解析 / Markdown 表格 / 中英混排宽度
│   ├── cli.py               # 命令行入口
│   └── modules/
│       ├── practice.py      # 🧘 修行录
│       ├── group_meal.py    # 🍱 团餐指挥官
│       ├── hidden_menu.py   # 🧪 隐藏菜单实验室
│       └── fortune.py       # 🔮 每日运势签
├── tests/                   # 🧪 187 个单元 / 集成测试
├── .github/workflows/ci.yml # ⚙️ GitHub Actions（多版本 pytest + ruff）
├── examples/                # 使用示例与样例输出
├── MCP_INTEGRATION.md       # MCP 集成说明（Server / Tool / 调用流程 / 业务价值）
├── CONTEST_DECLARATION.md   # 参赛声明
├── mcp-config.example.json  # 脱敏 MCP 配置示例
├── SKILL.md                 # WorkBuddy Skill 入口
└── workbuddy.md             # WorkBuddy 开发对话上下文
```

> `mcd_api.py` 是项目的「防坑层」：真实 MCP 的响应信封、门店前置参数、
> 金额单位（分）、套餐 `rounds` 结构、紧凑营养表格字符串等差异全部在这里收口，
> 模块层只面对干净的 Python 对象。

---

## 🧪 开发与测试

```bash
pip install -r requirements-dev.txt

pytest               # 187 个测试，无需 Token
ruff check src tests # 代码风格检查
```

测试分层：

| 文件 | 覆盖内容 |
| --- | --- |
| `test_utils.py` | 中文/emoji 显示宽度、卡片边框对齐、长文本折行、金额格式化 |
| `test_mcp_client.py` | 传输层：什么该重试、什么不该重试（401 / 业务错误不重试，网关抖动退避重试） |
| `test_mcd_api.py` | 信封拆解、分→元、`rounds` 解析、营养表解析、门店搜索约束 |
| `test_demo.py` | **演示与线上同构**：字段名、错误码、`roundList` 校验规则、差价算术 |
| `test_modules.py` | 四大模块端到端输出、预设配方语义（减脂真的降卡）、推荐质量约束 |
| `test_cli.py` | 子命令、`--json`、参数解析、`--people` 简写与错误提示 |

> `test_demo.py` 是这套测试里最有意思的一层：它把「演示数据和真实接口的行为必须一致」
> 这件事写成了断言。演示客户端一旦和线上脱节，测试就会红。
>
> `test_modules.py::TestGroupMealRecommender` 则把「推荐得像不像人话」写成了断言 ——
> 25 元预算不能推 2 元饼干，周边和蘸酱不能被当成餐品，忌口必须压过预算。

---

## 🛠️ 技术亮点

**1. 价格不是算出来的，是问出来的**

隐藏菜单实验室的「改配后价格」走的是真实的 `calculate-price`：
把完整的 `roundList`（每轮选中的商品 code + 数量）回传给门店，由麦当劳系统实时核价。
只有在实时核算不可用时，才降级为「套餐价 + Σ差价」的公式估算，并在输出里**明确标注**。

**2. 不确定的地方会说出来，而不是假装满足**

团餐指挥官里，如果有人想吃的东西门店当天没有、忌口标签在菜单里根本不存在、
或者为了满足口味不得不超预算 —— 这些都会写进「⚠️ 匹配说明」。

> 真实菜单的 `tags` 是营销标签（爆款 / 冷饮），并不包含「油炸」「辣」这类烹饪属性。
> 与其静默返回一个看起来没问题、实际没满足需求的方案，不如坦白说明。

**3. 拿不到数据 ≠ 数据是 0**

「减脂」配方依赖官方营养表。新品常常不在表里，如果让查不到数据的选项以 0 分参与比较，
它会伪装成「零热量」被选中，导致越减越离谱。因此：

- 查不到营养数据的选项**不参与**预设打分
- `lookup_nutrition()` 查不到时返回空 dict，让调用方区分「真的是 0 热量」和「没有数据」
- 餐品名归一化后再匹配（菜单「麦辣鸡翅2块」vs 营养表「麦辣鸡翅-2块」）

**4. 离线演示与线上同构**

`--demo` 不是「另一套假数据」，而是对真实响应逐字段复刻：
同样的信封、同样的字段名、同样的错误码、同样的 `roundList` 校验规则、
同样以「分」为单位的金额。`tests/test_demo.py` 把这份保真度写成了断言。

**5. 中文 + emoji 的终端排版**

卡片边框按**显示宽度**对齐：CJK 与 emoji 算 2 格，变体选择符（U+FE0F）算 0 格，
长文本按宽度自动折行。所以「🎖️ 当前段位」和「🍟 ▰▰▰▱▱」不会把边框撑歪。

**6. 只查不改，边界清晰**

不调用 `create-order` / `draw-lottery` / `mall-create-order`。
涉及资金与积分扣减的操作，一律留给用户在官方渠道完成。

**7. 推荐要「像人话」，不是「满足约束」**

真实菜单里混着很多东西：¥2 的饼干、¥14.90 的按摩捶、¥3 的蘸酱。
一个只按「预算内取最便宜」的匹配器，会给预算 ¥25 的人推荐 2 元饼干 ——
约束全满足，但没有人会这么点单。

所以团餐指挥官做了三件事：

- **排除非餐品**：蘸酱和周边（按摩捶 / 玩具 / 礼品卡）不进候选池
- **按餐品等级排序**：主食 > 小食 > 饮品，再按「最接近预算」取最优
- **标签匹配带否定判断**：「牛肉」能命中「100%纯牛肉」，但「咖啡」不会命中「无咖啡因」

这几条都写成了测试（`TestGroupMealRecommender` / `TestKeywordMatching`），
改坏了会立刻变红。线上实测：¥25 预算 → ¥24.50 的双层牛堡，而不是 ¥2 的饼干。

---

## 👥 谁适合用

- **重度麦门信徒** 🍔：想给自己的「麦当劳生涯」留点记录，喜欢成就与仪式感。
- **办公室团餐组织者** 🍱：每周都要帮一群人点单，最头疼凑单和口味协调。
- **想吃得明白的健身党** 💪：既想解馋又不想爆卡，需要可视化营养对比。
- **隐藏菜单爱好者** 🧪：热衷 DIY 配方、乐于分享「我的独门吃法」。

---

## 🔌 麦当劳 MCP 集成

本项目真实调用麦当劳中国官方 MCP 服务（`https://mcp.mcd.cn`，Streamable HTTP，Bearer Token 鉴权），
Server 共暴露 **35 个** Tool，本项目使用其中 **13 个**。完整说明见 **[MCP_INTEGRATION.md](MCP_INTEGRATION.md)**。

集成时踩到并已解决的几个「文档里没写」的坑：

| 坑 | 现象 | 解决 |
| --- | --- | --- |
| SDK API 改名 | `ImportError: streamablehttp_client` | 改用 `streamable_http_client` + `create_mcp_http_client` |
| 门店搜索 | 只传 `city` 或只传 `keyword` 都报 600058 | 两者必须同时非空 |
| 金额单位 | ¥4.50 返回 `450`，被误显示成 ¥450.00 | 统一用 `cents_to_yuan()` 显式换算，不做单位猜测 |
| 菜单没有名称和价格 | `query-meals` 只返回 `code` + `tags` | 用 `calculate-price` 批量补全（分批 + 失败二分重试） |
| 套餐改配定价 | 漏一个轮次就报 60006 | `roundList` 必须完整，`round` 传数字 id 字符串 |
| 营养数据格式 | 不是 JSON，是自定义紧凑表格字符串 | 单独写解析器 |
| 餐品名不一致 | 菜单「麦辣鸡翅2块」vs 营养表「麦辣鸡翅-2块」 | 名称归一化后再匹配 |

> **安全边界**：本项目只做**查询与试算**，不自动下单、不自动抽奖、不自动兑换积分。
> 所有涉及资金或积分扣减的操作，都留给用户自己在麦当劳官方渠道完成。

配置示例见 **[mcp-config.example.json](mcp-config.example.json)**，仅使用环境变量占位符，不含任何真实密钥。

---

## ⚠️ 免责声明

本项目为**麦当劳程序员节创意开发大赛**参赛作品，由参赛者独立开发，**非麦当劳官方产品**。
项目输出仅供参考，不构成医疗、营养或其他专业建议；餐品信息、价格及供应状态以麦当劳官方渠道的实时结果为准。

## 📄 License

[MIT](LICENSE) © 2026 MCD Buddy

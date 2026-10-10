---
name: mcd-buddy
description: 麦门四重奏 —— 基于麦当劳中国 MCP 的多玩法助手。当用户提到"麦当劳"、"麦门"、"MCD"、"点麦当劳"、"巨无霸"、"麦乐送"、"团餐点单"、"隐藏菜单"、"套餐怎么配"、"麦当劳积分/优惠券/活动"、"今天吃什么麦当劳"等需求时使用。提供四大玩法：修行录（点餐成就与段位）、团餐指挥官（多人凑单）、隐藏菜单实验室（重组套餐配方）、每日运势签（宜吃与抽奖吉时）。
agent_created: true
---

# 麦门四重奏 McQuartet

基于**麦当劳中国官方 MCP**（`https://mcp.mcd.cn`）的多玩法助手。先判断用户想要哪种玩法，再按对应流程调用工具。

> ⚠️ 本文档中的所有接口细节均来自**真实调用验证**。麦当劳 MCP 的实际行为与直觉差异很大，
> 请严格按本文档的参数与结构调用，不要凭常识推测。

## 0. 前置条件

需要麦当劳 MCP 已连接（连接器 `mcd-mcp`）。若工具不可用，提示用户：
前往 https://open.mcd.cn/mcp 手机号登录 →【控制台】→【激活】→ 复制 Token，
再在 WorkBuddy 的【连接器 → 自定义连接器 → 配置 MCP】中填入：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": { "Authorization": "Bearer YOUR_MCP_TOKEN" }
    }
  }
}
```

### 0.1 必须知道的四件事

1. **所有工具返回统一信封** `{success, code, message, datetime, traceId, data}`，
   业务数据在 `data` 里；`success=false` 时 `message` 是中文错误原因，`data` 不存在。
2. **金额单位是「分」**：`11450` = ¥114.50。（但 `order-list` 的 `realTotalAmount` 是**元字符串**。）
3. **菜单 / 价格 / 优惠券类工具都必须先有门店**（`storeCode` + `orderType` + `beType`）。
4. **到店自取场景不要传 `beCode`**，传了会报错；外送 / 团餐场景必须传。

## 1. 意图路由

| 用户说 | 走哪个玩法 | 主要工具 |
|---|---|---|
| "我吃了多少麦当劳 / 我的成就 / 段位" | 🧘 修行录 | `order-list` `query-my-account` `query-my-coupons` `query-my-prizes` `now-time-info` |
| "帮我们几个人点单 / 团餐 / 凑单" | 🍱 团餐指挥官 | `query-nearby-stores` `query-meals` `calculate-price` `query-my-coupons` `query-store-coupons` |
| "套餐怎么改 / 低卡版 / 隐藏菜单" | 🧪 隐藏菜单实验室 | `query-meal-detail` `list-nutrition-foods` `calculate-price` |
| "今天吃什么 / 麦当劳运势 / 抽奖" | 🔮 每日运势签 | `now-time-info` `list-nutrition-foods` `campaign-calendar` `query-lottery-info` `query-my-prizes` |

## 2. 🧘 修行录

1. 调 `now-time-info` 拿今天日期（`data.date`）。
2. 调 `order-list` 拿历史订单。**真实结构**：`data.list[].orderProductList[].comboItemList[]`，
   金额在 `realTotalAmount`（元字符串，如 `"13.9"`），时间在 `createTime`。
   > ⚠️ 套餐的子项藏在 `comboItemList` 里，统计「本命单品」时必须拆开，否则套餐名会占满榜单。
3. 调 `query-my-account` 拿积分（`availablePoint` / `accumulativePoint`，**都是字符串**）。
4. 调 `query-my-coupons` 数券、`query-my-prizes` 数奖品。
5. 统计：单数、天数、**连续连击**（从今天或昨天往前数连续有单的天）、累计消费、早餐次数（10:00 前）、咖啡次数。
6. 判定成就徽章（12 个）：初入麦门 / 三连修行 / 七日不辍 / 巨无霸十人斩 / 晨钟暮鼓 / 咖啡因续命 / 深夜食堂 / 麦门金主 / 单品收集家 / 券包大户 / 麦金喜锦鲤 / 麦门信徒。
7. 评级：见习麦徒(0) → 麦门学徒(5) → 麦门弟子(15) → 麦门执事(30) → 麦门长老(60) → 麦门宗主(100)，附薯条进度条与「距下一段位还差 N 单」。

## 3. 🍱 团餐指挥官

1. 收集每个人的 `{name, budget, want, avoid}`，缺的主动问。
2. **先解析门店**：调 `query-nearby-stores`，参数 `{beType: 1, searchType: 2, city, keyword}`。
   > ⚠️ `city` 与 `keyword` **必须同时非空**，只传一个会报 600058「城市名或者关键词不能为空」。
   选**营业中**（`businessStatus=true`）且距离最近的那家。
3. 调 `query-meals`（`{storeCode, orderType: 1, beType: 1}`）拿菜单编码 ——
   它**只返回 `data.categories[].meals[].code` 和 `tags`，没有名称也没有价格**。
4. 调 `calculate-price` 批量补全名称与价格：`items: [{productCode, quantity: 1}, ...]`，
   一次可传多个。名称取 `productList[].productName`，价格取 `subtotal` ÷ 100。
5. **分层匹配**（口味优先级必须高于预算）：
   排除忌口 → **排除非餐品** → 满足「想吃什么」→ 卡预算 → 取最优。
   - 关键词命中：名称包含 / 类目包含 / 标签包含（**否定式标签除外**）。
     标签是长串营销词，「牛肉」必须能命中 `100%纯牛肉`；
     但不能让「咖啡」命中 `无咖啡因`、让「油炸」命中 `非油炸` ——
     所以要先看关键词前面有没有 `无 / 非 / 不含 / 零 / 去`，有就不算命中。
   - **排除非餐品**：真实菜单的「小食甜品 /其他」类目里混着周边（¥14.90 的按摩捶、¥2 的饼干），
     「蘸酱炸鸡」里混着蘸酱（¥3，名称以「酱」结尾）。这些不能进候选池。
   - 预算内取**最接近预算**的一份，而不是最便宜的那份；
     否则 ¥25 预算会被推 ¥2 的饼干。没有预算时按一顿正餐的目标价（¥30）挑。
   - 餐品等级：主食/套餐 > 小食/炸鸡 > 饮品。
     等级要**同时看类目和名称** —— 「巨无霸」名字里没有「堡」字，只看名称会把它误判成小食。
6. 合并同名单品数量，调 `calculate-price` 算整单：金额在 `data.price`（分）。
7. 调 `query-my-coupons` 列卡包、`query-store-coupons` 列本门店可用券。
   > ⚠️ 必须说明区别：卡包的券**不校验门店与渠道**，能否用以下单时系统判定为准。
8. **如实报告没能满足的需求**：真实菜单的 `tags` 是营销标签（爆款/冷饮），
   不含「油炸」「辣」这类烹饪属性，所以忌口未必生效；为满足口味也可能超预算。
   这些都要在「匹配说明」里写出来，不要静默吞掉。
9. 输出：每人推荐 + 匹配说明 + 合并订单 + 价格明细 + **人均分摊** + 凑券建议。
10. 人数 ≥10 时提示可启用企业团餐助餐服务（需 `beType=6` + `beCode`，走 `delivery-query-stores` 流程）。

## 4. 🧪 隐藏菜单实验室

1. 确认基础套餐（传名称关键词或编码，如「双人分享餐」或 `9900011056`）与目标（减脂 / 增肌 / 解馋 / 清醒）。
2. 调 `query-meal-detail`（`{storeCode, orderType: 1, beType: 1, code}`）拿**套餐轮次**。
   真实结构：`data.rounds[].choices[]`，每个 choice 有
   `{code, name, quantity, isDefault, diffPrice, supportModify}`。
   > ⚠️ `diffPrice` 是**字符串**（`"+ ¥2.5"`），要自己解析成数字。
   > ⚠️ 同名轮次会出现多次（「选择小食」可能出现 3 次），**不能按名字定位轮次**。
3. 调 `list-nutrition-foods` 拿营养表 —— **不是 JSON，是一段自定义格式的文本**：
   ```
   [160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
     巨无霸,null,2146,513,27,26,42,961,171
   ```
   用 `energyKcal`（千卡），不是 `energyKj`（千焦，差 4.184 倍）。
4. **按目标给每个轮次的可选项打分**，取最高分：
   - 减脂：最小化 `energyKcal`
   - 增肌：最大化 `protein`
   - 解馋：最大化 `energyKcal`
   - 清醒：优先含咖啡因的（关键词用单字「咖」——菜单里叫「鲜萃冰咖」，不含「咖啡」二字）
5. **两个必须遵守的评分规则**：
   - **查不到营养数据的选项不参与比较**。新品常常不在官方营养表里，
     如果让它们以 0 分参与，会伪装成「零热量」，让减脂配方越减越离谱。
   - **餐品名要归一化后再匹配**。菜单叫「麦辣鸡翅2块」，营养表叫「麦辣鸡翅-2块」，
     不归一化就双双查不到数据。
6. **算真实价格**：调 `calculate-price`，传**完整的 `roundList`**：
   ```json
   {"productCode": "9900011056", "quantity": 1,
    "roundList": [{"round": "1", "comboItemList": [{"code": "1440", "quantity": 1}]}, ...]}
   ```
   三条硬规则（实测得出）：
   - `round` 必须是**轮次数字 id 的字符串**（`"1"`），不是轮次名称（传名称会 500）
   - `roundList` 必须**覆盖全部轮次**，漏一个就报 60006
   - 只能选该轮次 `choices` 里**真实存在**的 code，否则同样 60006

   价格公式：`新价 = 套餐基准价 + Σ(diffPrice × 该轮次数量)`
   （乘的是**轮次数量**，不是 `comboItemList` 里的数量 —— 最容易算错的地方）
7. 输出「改配说明 + 配方组成 + 可替换选项 + 营养对比 + 价格 + 可分享配方卡」。

## 5. 🔮 每日运势签

1. 调 `now-time-info` 拿日期，**以日期为随机种子**做确定性抽签（同一天结果必须一致，跨设备也一致）。
2. 调 `list-nutrition-foods` 拿餐品清单 —— 用营养表而不是 `query-meals`，
   因为后者需要先解析门店还要额外请求补全名称，而运势是全局玩法，不该绑定门店。
3. 调 `campaign-calendar` 拿今日活动：真实结构是 `data.dailyList[].events[].articleDto`，
   有 `title` / `content` / `highlights`。
4. 调 `query-lottery-info` 拿抽奖情报：`activityName`、`activityStatusText`、`drawPoint`、
   `drawDecision.nextConsumption.text`、`prizes[].name`。调 `query-my-prizes` 拿已中奖品。
5. 输出：签等 + 签文 + 宜吃（带 kcal/蛋白）+ 小忌 + 幸运色/数字 + 抽奖吉时 + 今日活动 + 我的奖品。

## 6. 注意事项

- 每个 Token 每分钟最多 600 次请求，避免密集循环调用；命中 `429` 要退避重试。
- **本助手只做查询与试算**：不调用 `create-order` / `draw-lottery` / `mall-create-order`，
  不自动下单、不自动抽奖、不自动兑换积分。涉及资金或积分扣减的操作留给用户在官方 App 完成。
- 门店打烊后（`businessStatus=false`）调 `query-meals` 会报 600057，要换一家营业中的门店。
- 营养数据仅供参考，**不构成医疗或营养建议**，需明确告知用户。
- 不要把真实 Token 写进任何文件或提交到仓库。

# MCP 集成说明

本文档记录麦门助手如何接入**麦当劳中国官方 MCP Server**，以及在实际联调中踩到的坑。
所有结论都来自对 `https://mcp.mcd.cn` 的**真实调用验证**，不是照文档推测的。

---

## 1. 接入方式

| 项目 | 值 |
| --- | --- |
| Server 地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权 | 请求头 `Authorization: Bearer <MCD_MCP_TOKEN>` |
| 限流 | 每个 Token 每分钟 600 次请求 |
| SDK | 官方 `mcp` Python SDK（`>=1.9.0`） |
| 工具数量 | 35 个（本助手使用其中 13 个） |

申请 Token：<https://open.mcd.cn/mcp>

### 客户端实现

`src/mcd_buddy/mcp_client.py`：

```python
from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

http_client = create_mcp_http_client(
    headers={"Authorization": f"Bearer {token}"}
)
streams = await stack.enter_async_context(
    streamable_http_client(url, http_client=http_client)
)
read, write = streams[0], streams[1]
session = await stack.enter_async_context(ClientSession(read, write))
await session.initialize()
```

> ⚠️ **SDK 版本坑**：`mcp` 2.x 把 `streamablehttp_client` 改名为 `streamable_http_client`，
> 并且要求显式传入 `http_client`；返回的是 `(read, write)` 二元组（旧版是三元组）。
> 网上大量示例仍是旧 API，直接抄会 `ImportError`。

内置能力：
- **429 限流**：指数退避重试，最多 3 次
- **401 鉴权**：直接抛出可读的中文提示，指引去重新申请 Token
- **响应解析**：兼容 pydantic 的 `structured_content` / `structuredContent` 两种字段命名

---

## 2. 响应信封（所有工具统一）

```json
{
  "success": true,
  "code": 200,
  "message": "请求成功",
  "datetime": "2026-10-10 23:02:54",
  "traceId": "83b742f55b49339c69880e3eb315a546",
  "data": { }
}
```

业务数据在 `data` 里；`success=false` 时 `data` 不存在，`message` 是中文错误原因。

业务层统一用 `mcd_api.unwrap()` 拆信封，失败抛 `MCDApiError`；
需要「失败也不中断整体流程」的地方用 `mcd_api.safe_call()`。

### 已遇到的错误码

| code | message | 触发条件 |
| --- | --- | --- |
| 600047 | `storeCode 不能为空` / `beType必传` | 必传参数缺失 |
| 600048 | `外送场景下，beType=2/5/6时必传beCode` | 外送/团餐场景没带 `beCode` |
| 600049 | `items 不能为空` | `calculate-price` 没传商品 |
| 600056 | `未找到餐品` | 餐品编码不存在 |
| 600057 | `门店可能已关闭或不在营业时间` | 门店打烊后查菜单 |
| 600058 | `城市名或者关键词不能为空` | 门店搜索只传了 `city` 或只传了 `keyword` |
| 60006 | `商品已售罄或不可售` | 套餐 `roundList` 不完整或选了非法选项 |
| 610501 | `仅支持企业团餐场景下使用助餐服务` | `query-meal-assistance` 的 `beType != 6` |

---

## 3. 门店前置：所有菜单/价格类工具都需要门店

`query-meals`、`query-meal-detail`、`calculate-price`、`query-store-coupons`
都**必须**传 `storeCode` + `orderType` + `beType`，所以调用链一定是「先解析门店」。

### 场景矩阵

| 场景 | beType | orderType | 是否需要 beCode | 门店来源 |
| --- | --- | --- | --- | --- |
| 到店自取 | 1 | 1 | ❌ 传了会报错 | `query-nearby-stores` |
| 得来速 | 5 | 1 | ✅ | `query-nearby-stores` |
| 麦乐送 | 2 | 2 | ✅ | `delivery-query-stores` |
| 企业团餐 | 6 | 2 | ✅ | `delivery-query-stores` |

本助手主打**到店自取**（`beType=1` / `orderType=1`），这是唯一不需要地址 ID 就能打通的完整链路。

### `query-nearby-stores` 的坑

`city` 与 `keyword` **必须同时非空**。实测：

| city | keyword | 结果 |
| --- | --- | --- |
| 空 | 深圳 | ❌ 600058 |
| 深圳市 | 空 | ❌ 600058 |
| 深圳市 | 麦当劳 | ✅ |

`searchType=2` 按位置搜索，`searchType=1` 搜收藏门店。

---

## 4. 金额单位是「分」

`calculate-price` 返回的金额单位是**分**：`11450` 表示 ¥114.50。

但 `order-list` 的 `realTotalAmount` 是**元字符串**：`"13.9"`。
积分字段（`availablePoint` 等）也是**字符串**：`"192.6"`。

> 早期版本写过一个「大于 1000 就除以 100」的启发式转换，结果把 ¥4.50（返回 `450`）
> 显示成 ¥450.00。现在统一由 `mcd_api.cents_to_yuan()` 显式转换，
> `utils.money()` 只负责格式化，不做任何单位猜测。

---

## 5. `query-meals` 只给编码，不给名称和价格

真实返回：

```json
{
  "data": {
    "categories": [
      { "name": "人气热卖", "meals": [ { "code": "521954" },
                                        { "code": "9900004064", "tags": ["爆款"] } ] }
    ]
  }
}
```

没有 `name`，也没有 `price`。要拿到可读菜单，必须用 `calculate-price` 批量补全：

```python
args = {
    "storeCode": store_code, "orderType": 1, "beType": 1,
    "items": [{"productCode": code, "quantity": 1} for code in codes],
}
```

返回：

```json
{
  "data": {
    "productList": [
      { "productCode": "1440", "productName": "麦辣鸡腿汉堡",
        "quantity": 1, "originalSubtotal": 2250, "subtotal": 2250 }
    ]
  }
}
```

一次请求可算多个商品，`mcd_api.enrich_menu()` 按 50 个一批发送，
**批次失败时自动二分重试**，保证个别不可售商品不影响整体菜单。

---

## 6. 套餐组成是 `rounds[].choices[]`

`query-meal-detail` 的真实结构：

```json
{
  "data": {
    "code": "9900011056",
    "name": "全明星双人分享餐八件套",
    "rounds": [
      {
        "id": 1, "name": "选择汉堡", "quantity": 1,
        "maxQuantity": 1, "minQuantity": 1,
        "choices": [
          { "code": "1440", "name": "麦辣鸡腿汉堡", "quantity": 1,
            "isDefault": 1, "diffPrice": "+ ¥0", "supportModify": true },
          { "code": "1010", "name": "巨无霸", "quantity": 0,
            "isDefault": 0, "diffPrice": "+ ¥2.5", "supportModify": false }
        ]
      }
    ]
  }
}
```

要点：
- `isDefault=1` 表示该选项当前被选中
- `diffPrice` 是**字符串**（`"+ ¥2.5"`），要自己解析成数字
- 同名轮次会出现多次（示例里「选择小食」出现 3 次），所以**不能按名字定位轮次**

---

## 7. 改配套餐的真实定价（隐藏菜单实验室的核心）

要给「改配后的套餐」定价，得传 `roundList`：

```json
{
  "storeCode": "1420525", "orderType": 1, "beType": 1,
  "items": [{
    "productCode": "9900011056",
    "quantity": 1,
    "roundList": [
      { "round": "1", "comboItemList": [{ "code": "1440", "quantity": 1 }] },
      { "round": "2", "comboItemList": [{ "code": "1406", "quantity": 1 }] },
      { "round": "3", "comboItemList": [{ "code": "515106", "quantity": 1 }] },
      { "round": "4", "comboItemList": [{ "code": "1700", "quantity": 1 }] },
      { "round": "5", "comboItemList": [{ "code": "4810", "quantity": 2 }] },
      { "round": "6", "comboItemList": [{ "code": "3050", "quantity": 2 }] }
    ]
  }]
}
```

### 三条硬规则（实测得出）

1. **`round` 必须是轮次数字 id 的字符串**（`"1"`），不是轮次名称。
   传名称会返回 500。
2. **`roundList` 必须覆盖全部轮次**，漏一个就报 60006。
3. **只能选该轮次 `choices` 里真实存在的 code**，否则同样 60006。

### 价格公式（已用真实数据验证）

```
新价 = 套餐基准价 + Σ( diffPrice × 该轮次数量 )
```

验证记录（套餐基准价 11450 分）：

| 改动 | 期望 | 实测 |
| --- | --- | --- |
| 全默认 | 11450 | ✅ 11450 |
| 轮3 → 麦辣鸡翅2块（+¥3.5，轮次数量 1） | 11450 + 350 | ✅ 11800 |
| 轮5 → 大杯玉米杯（+¥2.5，轮次数量 2） | 11450 + 500 | ✅ 11950 |
| 轮3 + 轮5 同时改 | 11450 + 350 + 500 | ✅ 12300 |

`diffPrice` 要乘的是**轮次数量**，不是 `comboItemList` 里的数量 —— 这是最容易算错的地方。

---

## 8. 营养数据是紧凑表格字符串

`list-nutrition-foods` 返回的 `data` **不是 JSON 数组**，而是一段自定义格式的文本：

```
[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  猪柳麦满分,null,1288,308,16,16,24,781,213
  巨无霸,null,2146,513,27,26,42,961,171
  ...
```

解析要点（`mcd_api.parse_nutrition_table()`）：
- 先用 `\{(.*?)\}` 抓表头拿到列名
- 再逐行 `split(",")` 对齐列
- **`energyKcal` 才是「千卡」**，`energyKj` 是千焦，两者差 4.184 倍

### 名称归一化（重要）

菜单里叫「麦辣鸡翅**2**块」，营养表里叫「麦辣鸡翅**-**2块」。
不做归一化就会双双查不到数据，而查不到数据在「减脂」配方里会被当成 **0 卡路里**，
导致越减越离谱。`mcd_api._norm_name()` 抹掉空格、连字符、括号等噪声后再匹配。

`lookup_nutrition()` 查不到时返回**空 dict**（而不是 0 值 dict），
调用方据此区分「真的是 0 热量」和「没有数据」。

---

## 9. 优惠券 / 奖品

| 工具 | 用途 | 关键字段 |
| --- | --- | --- |
| `query-my-coupons` | 我的卡包（不校验门店） | `coupons[].title`、`discountInfo.discountValue`、`instructions.labels[].text`（状态） |
| `query-store-coupons` | 该门店 + 渠道**可用**的券 | 需 `storeCode` + `orderType` + `beType` |
| `available-coupons` | 可领取 / 已领取的营销券 | `couponName`、`couponStatus`（`CAN_GET` / `HAVING_RECEIVE`） |
| `query-my-prizes` | 抽奖所得奖品 | `prizes[].name`、`prizeTypeText`、`statusText` |

> 注意：`query-my-coupons` 返回的是「用户拥有的券」，**不承诺可用于当前订单**。
> 团餐模块会把两者都列出来，并明确标注这个区别。

---

## 10. 菜单里的「非餐品」与标签语义

线上实测的菜单并不干净，做推荐前必须先过一遍：

**类目里混着非餐品**

| 类目 | 混入的东西 | 例子 |
| --- | --- | --- |
| `小食甜品 /其他` | 周边、玩具、低价饼干 | `「葱不求人」按摩捶痒痒挠` ¥14.90、`麦当劳素龙限定饼干` ¥2.00 |
| `蘸酱炸鸡` | 蘸酱本身 | `韩式烟熏芝士风味酱` ¥3.00 |

一个只按「预算内取最便宜」的匹配器，会给预算 ¥25 的人推荐 ¥2 的饼干 —— 约束全满足，
但没有人会这么点单。所以本助手会先排掉「以『酱』结尾」和明显是周边的东西。

**标签是营销词，而且带否定式**

| 标签 | 关键词 | 期望 |
| --- | --- | --- |
| `100%纯牛肉` | 牛肉 | ✅ 命中（长串营销词里包含关键词） |
| `无咖啡因` | 咖啡 | ❌ 不命中（前缀是否定词，意思完全相反） |
| `非油炸` | 油炸 | ❌ 不命中（否则忌口会误伤本来没问题的餐品） |

实现上先找关键词在标签里的位置，再看它**前面**有没有 `无 / 非 / 不含 / 零 / 去`。
否定词出现在关键词之后不算否定（`牛肉无添加` 仍然命中「牛肉」）。

**类目顺序会影响归类**

`query-meals` 的同一个 `code` 可能出现在多个类目下。本助手以**首次出现**的类目为准，
而真实响应的类目顺序是「巨无霸 牛鱼肉堡 → 鸡肉汉堡/卷 → 小食甜品 → 饮品 → 人气热卖 → …」，
「人气热卖」排在靠后位置。演示数据刻意复刻了这个顺序，
否则中薯条会被归成「人气热卖」而不是「小食」，和线上行为不一致。

---

## 11. 本助手实际使用的工具

| 工具 | 使用模块 | 备注 |
| --- | --- | --- |
| `now-time-info` | 修行录 / 运势签 | 决定当天的签，保证同日结果一致 |
| `order-list` | 修行录 | `data.list[].orderProductList[].comboItemList[]` |
| `query-my-account` | 修行录 | 积分字段均为字符串 |
| `query-my-coupons` | 修行录 / 团餐指挥官 | |
| `query-my-prizes` | 修行录 / 运势签 | |
| `query-nearby-stores` | 团餐 / 隐藏菜单 | `city` + `keyword` 必须同时非空 |
| `query-meals` | 团餐 / 隐藏菜单 | 只给 code + tags |
| `query-meal-detail` | 隐藏菜单 | `rounds[].choices[]` |
| `calculate-price` | 团餐 / 隐藏菜单 | 补全菜单 + 整单定价 + 改配定价 |
| `query-store-coupons` | 团餐指挥官 | |
| `list-nutrition-foods` | 隐藏菜单 / 运势签 | 紧凑表格字符串 |
| `campaign-calendar` | 运势签 | `dailyList[].events[].articleDto` |
| `query-lottery-info` | 运势签 | `drawDecision.nextConsumption`、`prizes[]` |

未使用但已探明：`draw-lottery`（涉及真实扣积分，需用户明确确认，本助手不自动调用）、
`create-order` / `cancel-order`（涉及真实下单）、`party-order-*`（生日派对预约）、
`mall-*`（积分商城兑换）。

> **安全边界**：本助手只做**查询与试算**，不自动下单、不自动抽奖、不自动兑换，
> 所有涉及积分扣减或资金的操作都留给用户自己在麦当劳 App 内完成。

---

## 12. 离线演示与线上同构

`src/mcd_buddy/demo.py` 里的演示客户端**逐字段复刻**了真实响应：
同样的信封、同样的字段名、同样的错误码、同样的 `roundList` 校验规则、
同样以「分」为单位的金额、同样的紧凑营养表格字符串。

这样做的目的是让 `--demo` 与真实调用走**同一条代码路径**。
`tests/test_demo.py` 专门用来锁死这份保真度 —— 一旦演示数据和线上行为脱节，测试就会失败。

**离线演示能跑通，不等于线上能跑通；但演示和线上同构时，至少能保证代码路径一致。**

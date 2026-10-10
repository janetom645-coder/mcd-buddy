"""离线演示客户端：无需 MCP Token 即可跑通全部模块。

**重要**：这里的数据结构是对真实麦当劳 MCP 响应逐字段复刻的
（``data.categories[].meals[].code``、``rounds[].choices[].diffPrice``、
金额单位「分」、营养紧凑表格字符串……），
目的是让离线演示与线上调用走**同一条代码路径** —— 否则演示通过不等于线上能跑。

真实能力请通过 :class:`~mcd_buddy.mcp_client.MCDClient` 调用麦当劳官方 MCP。
"""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any

from .mcp_client import MCDError

# ------------------------------------------------------------------ 时间 / 账户

_NOW = {
    "timestamp": 1791644574982,
    "datetime": "2026-10-10T18:12:30.000",
    "formatted": "2026-10-10 18:12:30",
    "date": "2026-10-10",
    "year": 2026,
    "month": 10,
    "day": 10,
    "dayOfWeek": "SATURDAY",
    "timezone": "GMT+08:00",
    "offset": "+08:00",
    "utc": "2026-10-10T10:12:30.000Z",
}

_ACCOUNT = {
    "availablePoint": "2860.5",
    "accountId": "02002159202761362716460280131",
    "accumulativePoint": "5120.0",
    "currency": "麦享会积分",
    "currentMouthExpirePoint": "120.0",
    "expiredPoint": "38.5",
    "frozenPoint": "0",
    "lastMouthExpirePoint": "0",
    "nextMouthExpirePoint": "300.0",
    "usedPoint": "2260.0",
}

# ------------------------------------------------------------------ 历史订单
# 真实结构：data.list[].orderProductList[].comboItemList[]，金额 realTotalAmount 是「元」字符串

_ORDERS = {
    "list": [
        {
            "orderId": "1030609680000754932928585802",
            "orderType": "1",
            "createTime": "2026-10-10 11:35:27",
            "beType": "1",
            "beCode": "",
            "storeCode": "1421217",
            "storeName": "麦当劳深圳深大沧海餐厅",
            "orderStatus": "订单已完成",
            "realTotalAmount": "13.9",
            "orderProductList": [
                {
                    "productCode": "9900015568",
                    "productName": "精选超值随心配",
                    "quantity": 1,
                    "comboItemList": [
                        {"productCode": "521316", "name": "高达吉士双牛堡", "quantity": 1},
                        {"productCode": "3071", "name": "无糖可口可乐中杯", "quantity": 1},
                    ],
                }
            ],
        },
        {
            "orderId": "1030105130000795534718286700",
            "orderType": "1",
            "createTime": "2026-10-07 17:52:33",
            "beType": "1",
            "beCode": "",
            "storeCode": "1421217",
            "storeName": "麦当劳深圳深大沧海餐厅",
            "orderStatus": "订单已完成",
            "realTotalAmount": "13.9",
            "orderProductList": [
                {
                    "productCode": "9900013304",
                    "productName": "人气经典随心配",
                    "quantity": 1,
                    "comboItemList": [
                        {"productCode": "521316", "name": "高达吉士双牛堡", "quantity": 1},
                        {"productCode": "4106", "name": "香芋派", "quantity": 1},
                    ],
                }
            ],
        },
        {
            "orderId": "1030717190000808228796129936",
            "orderType": "1",
            "createTime": "2026-10-06 17:51:12",
            "beType": "1",
            "beCode": "",
            "storeCode": "1421217",
            "storeName": "麦当劳深圳深大沧海餐厅",
            "orderStatus": "订单已完成",
            "realTotalAmount": "13.9",
            "orderProductList": [
                {
                    "productCode": "9900013304",
                    "productName": "人气经典随心配",
                    "quantity": 1,
                    "comboItemList": [
                        {"productCode": "521316", "name": "高达吉士双牛堡", "quantity": 1},
                        {"productCode": "4106", "name": "香芋派", "quantity": 1},
                    ],
                }
            ],
        },
        {
            "orderId": "1030226480000795330657003465",
            "orderType": "1",
            "createTime": "2026-09-29 11:39:25",
            "beType": "1",
            "beCode": "",
            "storeCode": "1421217",
            "storeName": "麦当劳深圳深大沧海餐厅",
            "orderStatus": "订单已完成",
            "realTotalAmount": "13.9",
            "orderProductList": [
                {
                    "productCode": "9900013304",
                    "productName": "人气经典随心配",
                    "quantity": 1,
                    "comboItemList": [
                        {"productCode": "521316", "name": "高达吉士双牛堡", "quantity": 1},
                        {"productCode": "3071", "name": "无糖可口可乐中杯", "quantity": 1},
                    ],
                }
            ],
        },
        {
            "orderId": "1030923610000795127728192617",
            "orderType": "2",
            "createTime": "2026-09-20 16:48:30",
            "beType": "2",
            "beCode": "DLV-9f2c",
            "storeCode": "1421217",
            "storeName": "麦当劳深圳深大沧海餐厅",
            "orderStatus": "订单已完成",
            "realTotalAmount": "45.5",
            "orderProductList": [
                {
                    "productCode": "1440",
                    "productName": "麦辣鸡腿汉堡",
                    "quantity": 1,
                    "comboItemList": [],
                },
                {
                    "productCode": "4810",
                    "productName": "中薯条",
                    "quantity": 1,
                    "comboItemList": [],
                },
                {
                    "productCode": "3050",
                    "productName": "可乐中杯",
                    "quantity": 1,
                    "comboItemList": [],
                },
                {
                    "productCode": "1217",
                    "productName": "奥利奥麦旋风",
                    "quantity": 1,
                    "comboItemList": [],
                },
            ],
        },
        {
            "orderId": "1030331250000788225531017744",
            "orderType": "1",
            "createTime": "2026-09-12 08:22:10",
            "beType": "1",
            "beCode": "",
            "storeCode": "1421217",
            "storeName": "麦当劳深圳深大沧海餐厅",
            "orderStatus": "订单已完成",
            "realTotalAmount": "11.5",
            "orderProductList": [
                {
                    "productCode": "9900014021",
                    "productName": "早餐吉士蛋麦满分套餐",
                    "quantity": 1,
                    "comboItemList": [
                        {"productCode": "2001", "name": "吉士蛋麦满分", "quantity": 1},
                        {"productCode": "3200", "name": "大杯鲜萃咖啡", "quantity": 1},
                    ],
                }
            ],
        },
        {
            "orderId": "1030188220000751993303885120",
            "orderType": "1",
            "createTime": "2026-09-05 08:31:44",
            "beType": "1",
            "beCode": "",
            "storeCode": "1421217",
            "storeName": "麦当劳深圳深大沧海餐厅",
            "orderStatus": "订单已完成",
            "realTotalAmount": "11.5",
            "orderProductList": [
                {
                    "productCode": "9900014021",
                    "productName": "早餐吉士蛋麦满分套餐",
                    "quantity": 1,
                    "comboItemList": [
                        {"productCode": "2001", "name": "吉士蛋麦满分", "quantity": 1},
                        {"productCode": "3200", "name": "大杯鲜萃咖啡", "quantity": 1},
                    ],
                }
            ],
        },
        {
            "orderId": "1030074550000740211882556091",
            "orderType": "1",
            "createTime": "2026-08-28 21:47:03",
            "beType": "1",
            "beCode": "",
            "storeCode": "1421217",
            "storeName": "麦当劳深圳深大沧海餐厅",
            "orderStatus": "订单已完成",
            "realTotalAmount": "13.9",
            "orderProductList": [
                {
                    "productCode": "9900013304",
                    "productName": "人气经典随心配",
                    "quantity": 1,
                    "comboItemList": [
                        {"productCode": "521316", "name": "高达吉士双牛堡", "quantity": 1},
                        {"productCode": "4106", "name": "香芋派", "quantity": 1},
                    ],
                }
            ],
        },
    ]
}

# ------------------------------------------------------------------ 门店
# 真实结构：data[] 平铺数组，字段 storeCode / storeName / businessStatus / businessStartTime ...

_STORES = [
    {
        "storeCode": "1420525",
        "storeName": "麦当劳深圳福华一路(卓悦中心)餐厅",
        "address": "福田区福华一路348号卓悦中心B2",
        "distance": 366,
        "businessStatus": True,
        "businessStartTime": "00:00",
        "businessEndTime": "23:59",
        "longitude": 0.0,
        "latitude": 0.0,
        "reservation": True,
        "reservationTimeOptions": [
            {
                "date": "2026-10-11",
                "today": False,
                "reservationOptionText": "早餐(07:14至10:15)，午餐(10:44至14:15)，下午茶(14:44至16:45)，夜市(17:14至21:45)",
            }
        ],
    },
    {
        "storeCode": "1420453",
        "storeName": "麦当劳深圳储能大厦餐厅",
        "address": "科苑南路3099号中国储能大厦1层G号商铺",
        "distance": 125,
        "businessStatus": False,
        "businessStartTime": "07:00",
        "businessEndTime": "22:00",
        "longitude": 0.0,
        "latitude": 0.0,
        "reservation": True,
        "reservationTimeOptions": [],
    },
    {
        "storeCode": "1421217",
        "storeName": "麦当劳深圳深大沧海餐厅",
        "address": "南海大道3688号深圳大学沧海校区",
        "distance": 880,
        "businessStatus": True,
        "businessStartTime": "06:00",
        "businessEndTime": "23:00",
        "longitude": 0.0,
        "latitude": 0.0,
        "reservation": False,
        "reservationTimeOptions": [],
    },
]

# ------------------------------------------------------------------ 商品目录（内部）
# price 单位为「分」，与真实 calculate-price 返回一致

_CATALOG: dict[str, dict] = {
    # 汉堡
    "1440": {"name": "麦辣鸡腿汉堡", "price": 2250, "tags": ["辣", "鸡肉"]},
    "1406": {"name": "板烧鸡腿堡", "price": 2350, "tags": ["鸡肉", "非油炸"]},
    "521316": {"name": "高达吉士双牛堡", "price": 2600, "tags": ["牛肉", "爆款"]},
    "1010": {"name": "巨无霸", "price": 2450, "tags": ["牛肉", "经典"]},
    "1020": {"name": "吉士汉堡包", "price": 1350, "tags": ["牛肉"]},
    "1050": {"name": "麦香鱼", "price": 1750, "tags": ["鱼肉", "非辣"]},
    "1080": {"name": "麦香鸡", "price": 1550, "tags": ["鸡肉"]},
    "2001": {"name": "吉士蛋麦满分", "price": 1150, "tags": ["早餐", "鸡蛋"]},
    "2002": {"name": "猪柳麦满分", "price": 1250, "tags": ["早餐", "猪肉"]},
    # 小食
    "4810": {"name": "中薯条", "price": 1150, "tags": ["油炸", "素食"]},
    "4800": {"name": "大薯条", "price": 1350, "tags": ["油炸", "素食"]},
    "4820": {"name": "小薯条", "price": 950, "tags": ["油炸", "素食"]},
    "515106": {"name": "麦乐鸡4块", "price": 1150, "tags": ["鸡肉", "油炸"]},
    "1700": {"name": "麦辣鸡翅2块", "price": 1500, "tags": ["鸡肉", "辣", "油炸"]},
    "4438": {"name": "大杯玉米杯", "price": 1100, "tags": ["素食", "低卡"]},
    "4430": {"name": "小杯玉米杯", "price": 850, "tags": ["素食", "低卡"]},
    "4600": {"name": "脆薯饼", "price": 900, "tags": ["油炸", "早餐"]},
    "4610": {"name": "脆香油条", "price": 950, "tags": ["油炸", "早餐"]},
    # 饮品
    "3050": {"name": "可乐中杯", "price": 1000, "tags": ["冷饮", "含糖"]},
    "3040": {"name": "可乐大杯", "price": 1150, "tags": ["冷饮", "含糖"]},
    "3071": {"name": "无糖可口可乐中杯", "price": 1000, "tags": ["冷饮", "无糖"]},
    "3200": {"name": "大杯鲜萃咖啡", "price": 1250, "tags": ["热饮", "咖啡因"]},
    "3201": {"name": "小杯鲜萃咖啡", "price": 1000, "tags": ["热饮", "咖啡因"]},
    "3210": {"name": "浓缩咖啡", "price": 1050, "tags": ["热饮", "咖啡因"]},
    "3300": {"name": "锡兰红茶", "price": 1000, "tags": ["热饮", "无咖啡因"]},
    "3400": {"name": "纯牛奶（盒装）", "price": 900, "tags": ["无咖啡因", "非油炸"]},
    "3500": {"name": "热朱古力", "price": 1100, "tags": ["热饮", "含糖"]},
    # 甜品
    "1217": {"name": "奥利奥麦旋风", "price": 1350, "tags": ["冰淇淋", "含糖"]},
    "4900": {"name": "草莓麦旋风", "price": 1350, "tags": ["冰淇淋", "含糖"]},
    "4106": {"name": "香芋派", "price": 850, "tags": ["油炸", "含糖"]},
    "4110": {"name": "菠萝派", "price": 850, "tags": ["油炸", "含糖"]},
    "4000": {"name": "圆筒冰淇淋", "price": 600, "tags": ["冰淇淋", "含糖"]},
    # 套餐
    "9900011056": {"name": "全明星双人分享餐八件套", "price": 11450, "tags": ["双人", "分享装"]},
    "9900013304": {"name": "人气经典随心配", "price": 1390, "tags": ["随心配", "爆款"]},
    "9900015568": {"name": "精选超值随心配", "price": 1390, "tags": ["随心配", "爆款"]},
    "9900014021": {"name": "早餐吉士蛋麦满分套餐", "price": 1150, "tags": ["早餐", "套餐"]},
    # 真实菜单里的「坑」：低价的非正餐商品、周边、蘸酱
    # 它们混在正常类目里，用来验证推荐逻辑不会选出荒谬结果
    "521770": {"name": "麦当劳素龙限定饼干", "price": 200, "tags": ["上新"]},
    "521771": {"name": "「葱不求人」按摩捶痒痒挠", "price": 1490, "tags": ["上新"]},
    "521772": {"name": "韩式烟熏芝士风味酱", "price": 300, "tags": ["蘸酱"]},
    "521773": {"name": "蘸酱韩式甜辣酱鸡块", "price": 1190, "tags": ["蘸酱炸鸡"]},
}

# 菜单分类（真实结构：data.categories[].meals[].code + tags）
_MENU_CATEGORIES: list[tuple[str, list[str]]] = [
    # 顺序刻意与真实菜单一致：真实响应的类目顺序是
    # 巨无霸 牛鱼肉堡 → 鸡肉汉堡/卷 → 小食甜品 → 饮品 → 人气热卖 → …
    # 因为 parse_menu_codes 以「首次出现」的类目为准，
    # 把「人气热卖」放前面会让中薯条被归成热卖而不是小食，和线上不一致。
    ("汉堡", ["1010", "1440", "1406", "521316", "1020", "1050", "1080"]),
    ("超值套餐", ["9900011056", "9900014021"]),
    ("小食", ["4810", "4800", "4820", "515106", "1700", "4438", "4430"]),
    ("饮品", ["3050", "3040", "3071", "3200", "3201", "3210", "3300", "3400", "3500"]),
    ("甜品", ["1217", "4900", "4106", "4110", "4000"]),
    ("早餐", ["2001", "2002", "4600", "4610"]),
    ("人气热卖", ["9900013304", "9900015568", "521316", "1440", "4810", "1217"]),
    # 与真实菜单一致：这两个类目里混着非餐品（饼干 / 周边 / 蘸酱）
    ("小食甜品 /其他", ["521770", "521771"]),
    ("蘸酱炸鸡", ["521772", "521773"]),
]


def _menu_payload() -> dict:
    """构造 query-meals 的真实响应（只含 code + tags）。"""
    categories = []
    for name, codes in _MENU_CATEGORIES:
        meals = []
        for code in codes:
            entry: dict[str, Any] = {"code": code}
            tags = _CATALOG.get(code, {}).get("tags")
            if tags:
                entry["tags"] = list(tags)
            meals.append(entry)
        categories.append({"name": name, "meals": meals})
    return {"categories": categories}


# ------------------------------------------------------------------ 套餐详情（rounds[].choices[]）

_DETAILS: dict[str, dict] = {
    "9900011056": {
        "code": "9900011056",
        "name": "全明星双人分享餐八件套",
        "rounds": [
            {
                "id": 1, "name": "选择汉堡", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "1440", "name": "麦辣鸡腿汉堡", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "1406", "name": "板烧鸡腿堡", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "1010", "name": "巨无霸", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥2.5", "supportModify": True},
                ],
            },
            {
                "id": 2, "name": "选择主食", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "1406", "name": "板烧鸡腿堡", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "1440", "name": "麦辣鸡腿汉堡", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "521316", "name": "高达吉士双牛堡", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥3", "supportModify": True},
                ],
            },
            {
                "id": 3, "name": "选择小食", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "515106", "name": "麦乐鸡4块", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": False},
                    {"code": "1700", "name": "麦辣鸡翅2块", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥3.5", "supportModify": False},
                    {"code": "4600", "name": "脆薯饼", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": False},
                ],
            },
            {
                "id": 4, "name": "选择小食", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "1700", "name": "麦辣鸡翅2块", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": False},
                    {"code": "515106", "name": "麦乐鸡4块", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥1", "supportModify": False},
                ],
            },
            {
                "id": 5, "name": "选择小食", "quantity": 2, "maxQuantity": 2, "minQuantity": 2,
                "choices": [
                    {"code": "4810", "name": "中薯条", "quantity": 2, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": False},
                    {"code": "1217", "name": "奥利奥麦旋风", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": False},
                    {"code": "4900", "name": "草莓麦旋风", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": False},
                    {"code": "4438", "name": "大杯玉米杯", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥2.5", "supportModify": False},
                    {"code": "4430", "name": "小杯玉米杯", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": False},
                ],
            },
            {
                "id": 6, "name": "选择套餐内饮料", "quantity": 2, "maxQuantity": 2, "minQuantity": 2,
                "choices": [
                    {"code": "3050", "name": "可乐中杯", "quantity": 2, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "3071", "name": "无糖可口可乐中杯", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "3200", "name": "大杯鲜萃咖啡", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥6", "supportModify": True},
                    {"code": "3400", "name": "纯牛奶（盒装）", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥3", "supportModify": False},
                ],
            },
        ],
    },
    "9900013304": {
        "code": "9900013304",
        "name": "人气经典随心配",
        "rounds": [
            {
                "id": 1, "name": "选择汉堡", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "521316", "name": "高达吉士双牛堡", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "1440", "name": "麦辣鸡腿汉堡", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "1050", "name": "麦香鱼", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": True},
                ],
            },
            {
                "id": 2, "name": "选择小食", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "4106", "name": "香芋派", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": False},
                    {"code": "4810", "name": "中薯条", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥2", "supportModify": False},
                    {"code": "1217", "name": "奥利奥麦旋风", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥4", "supportModify": False},
                    {"code": "4430", "name": "小杯玉米杯", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": False},
                ],
            },
        ],
    },
    "9900015568": {
        "code": "9900015568",
        "name": "精选超值随心配",
        "rounds": [
            {
                "id": 1, "name": "选择汉堡", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "521316", "name": "高达吉士双牛堡", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "1020", "name": "吉士汉堡包", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": True},
                ],
            },
            {
                "id": 2, "name": "选择饮品", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "3071", "name": "无糖可口可乐中杯", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "3050", "name": "可乐中杯", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "3400", "name": "纯牛奶（盒装）", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥3", "supportModify": False},
                    {"code": "3300", "name": "锡兰红茶", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥2", "supportModify": False},
                ],
            },
        ],
    },
    "9900014021": {
        "code": "9900014021",
        "name": "早餐吉士蛋麦满分套餐",
        "rounds": [
            {
                "id": 1, "name": "选择主食", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "2001", "name": "吉士蛋麦满分", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "2002", "name": "猪柳麦满分", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥1", "supportModify": True},
                ],
            },
            {
                "id": 2, "name": "选择饮品", "quantity": 1, "maxQuantity": 1, "minQuantity": 1,
                "choices": [
                    {"code": "3200", "name": "大杯鲜萃咖啡", "quantity": 1, "isDefault": 1,
                     "diffPrice": "+ ¥0", "supportModify": True},
                    {"code": "3400", "name": "纯牛奶（盒装）", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥2", "supportModify": False},
                    {"code": "3300", "name": "锡兰红茶", "quantity": 0, "isDefault": 0,
                     "diffPrice": "+ ¥0", "supportModify": False},
                ],
            },
        ],
    },
}


def _detail_for(code: str) -> dict:
    """返回套餐详情；单品则合成一个单轮次详情。"""
    if code in _DETAILS:
        return copy.deepcopy(_DETAILS[code])
    entry = _CATALOG.get(code)
    if not entry:
        return {}
    return {
        "code": code,
        "name": entry["name"],
        "rounds": [
            {
                "id": 1,
                "name": "选择商品",
                "quantity": 1,
                "maxQuantity": 1,
                "minQuantity": 1,
                "choices": [
                    {
                        "code": code,
                        "name": entry["name"],
                        "quantity": 1,
                        "isDefault": 1,
                        "diffPrice": "+ ¥0",
                        "supportModify": False,
                    }
                ],
            }
        ],
    }


# ------------------------------------------------------------------ 营养（紧凑表格字符串）

_NUTRITION_ROWS: list[tuple[str, int, int, float, float, float, int, int]] = [
    # name, energyKj, energyKcal, protein, fat, carbohydrate, sodium, calcium
    ("猪柳麦满分", 1288, 308, 16, 16, 24, 781, 213),
    ("猪柳蛋麦满分", 1618, 387, 23, 21, 25, 846, 243),
    ("吉士蛋麦满分", 1265, 302, 17, 13, 28, 690, 231),
    ("烟肉蛋麦满分", 1089, 260, 16, 10, 24, 483, 238),
    ("中薯条", 1210, 289, 4, 12, 38, 165, 18),
    ("大薯条", 1587, 379, 6, 16, 50, 216, 23),
    ("小薯条", 877, 210, 3, 9, 28, 120, 13),
    ("圆筒冰淇淋", 391, 93, 2, 3, 14, 36, 77),
    ("麦乐鸡4块", 745, 178, 10, 10, 11, 352, 8),
    ("大杯玉米杯", 365, 87, 4, 1, 12, 2, 10),
    ("小杯玉米杯", 223, 53, 2, 1, 7, 1, 6),
    ("麦辣鸡翅2块", 937, 224, 13, 15, 9, 537, 13),
    ("奥利奥麦旋风", 1115, 266, 5, 9, 40, 116, 185),
    ("草莓麦旋风", 1234, 295, 6, 9, 47, 122, 186),
    ("香芋派", 971, 232, 2, 12, 28, 159, 7),
    ("菠萝派", 925, 221, 2, 11, 27, 147, 5),
    ("吉士汉堡包", 1231, 294, 16, 12, 30, 673, 144),
    ("麦香鸡", 1546, 369, 15, 17, 39, 731, 73),
    ("麦香鱼", 1359, 325, 16, 13, 35, 556, 99),
    ("麦辣鸡腿汉堡", 2029, 485, 24, 24, 42, 1208, 154),
    ("板烧鸡腿堡", 1638, 391, 23, 17, 35, 1041, 93),
    ("巨无霸", 2146, 513, 27, 26, 42, 961, 171),
    ("高达吉士双牛堡", 1873, 448, 26, 23, 33, 899, 168),
    ("可乐中杯", 616, 147, 0, 0, 36, 0, 10),
    ("可乐大杯", 936, 224, 0, 0, 55, 0, 15),
    ("无糖可口可乐中杯", 0, 0, 0, 0, 1, 35, 0),
    ("大杯鲜萃咖啡", 54, 13, 1, 0, 0, 3, 8),
    ("小杯鲜萃咖啡", 63, 15, 1, 0, 3, 2, 6),
    ("浓缩咖啡", 54, 13, 1, 0, 2, 0, 7),
    ("锡兰红茶", 8, 2, 0, 0, 0, 0, 5),
    ("热朱古力", 525, 125, 2, 2, 22, 107, 36),
    ("纯牛奶（盒装）", 541, 129, 7, 7, 10, 73, 231),
    ("脆薯饼", 612, 146, 1, 9, 14, 311, 7),
    ("脆香油条", 844, 202, 5, 12, 19, 230, 18),
    ("全明星双人分享餐八件套", 5680, 1358, 66, 58, 132, 2680, 420),
]


def _nutrition_text() -> str:
    columns = (
        "productName,nutritionDescription,energyKj,energyKcal,"
        "protein,fat,carbohydrate,sodium,calcium"
    )
    lines = [f"[{len(_NUTRITION_ROWS)}]{{{columns}}}:"]
    for name, kj, kcal, protein, fat, carb, sodium, calcium in _NUTRITION_ROWS:
        lines.append(
            f"  {name},null,{kj},{kcal},{protein:g},{fat:g},{carb:g},{sodium},{calcium}"
        )
    return "\n".join(lines)


# ------------------------------------------------------------------ 活动日历

_CALENDAR = {
    "currentTime": "2026-10-10 18:12:30",
    "dailyList": [
        {
            "date": "2026-10-07",
            "dateText": "2026年10月7日 往期回顾",
            "today": False,
            "events": [
                {
                    "activityCode": "45f3",
                    "activityStage": 3,
                    "eventType": 4,
                    "activityTitle": "超值9.9元早餐两件套",
                    "activityTag": "早餐",
                    "price": "9.9",
                    "priceSuffix": "起",
                    "activityBgColor": "B1B1B1",
                    "button": {"status": 1, "text": "已结束"},
                    "articleDto": {
                        "title": "超值9.9元早餐两件套陪你开工啦",
                        "content": "早八的快乐，一堡一咖已就位。10月8日至10月21日，周一至周五早餐堡轮流上早班。",
                        "highlights": "9.9元超值早餐正式上新！",
                        "buttonText": "立即领券",
                    },
                }
            ],
        },
        {
            "date": "2026-10-10",
            "dateText": "2026年10月10日 今日活动",
            "today": True,
            "events": [
                {
                    "activityCode": "9k2p",
                    "activityStage": 1,
                    "eventType": 2,
                    "activityTitle": "周六麦金喜抽奖",
                    "activityTag": "会员日",
                    "price": "24",
                    "priceSuffix": "积分",
                    "activityBgColor": "FFC72C",
                    "button": {"status": 2, "text": "立即参与"},
                    "articleDto": {
                        "title": "周六麦金喜，24 积分抽好礼",
                        "content": "消耗 24 积分即可参与一次抽奖，积分霸王餐、麦金卡、立减券等你来拿。",
                        "highlights": "本周六限定，错过再等一周",
                        "buttonText": "去抽奖",
                    },
                }
            ],
        },
        {
            "date": "2026-10-12",
            "dateText": "2026年10月12日 即将开始",
            "today": False,
            "events": [
                {
                    "activityCode": "en70",
                    "activityStage": 0,
                    "eventType": 4,
                    "activityTitle": "巨无霸 55 周年庆",
                    "activityTag": "周年庆",
                    "price": "0",
                    "priceSuffix": "起",
                    "activityBgColor": "DA291C",
                    "button": {"status": 3, "text": "即将开始"},
                    "articleDto": {
                        "title": "巨无霸 55 周年，第二份半价",
                        "content": "经典巨无霸回归初心价，10月12日至10月18日，第二份半价。",
                        "highlights": "55 年经典，一口回到 1968",
                        "buttonText": "提醒我",
                    },
                }
            ],
        },
    ],
}

# ------------------------------------------------------------------ 抽奖

_LOTTERY = {
    "status": {"code": "SUCCESS", "message": "成功"},
    "activityCode": "269t",
    "activityStatusText": "进行中",
    "activityName": "周六麦金喜抽奖",
    "beginTime": "2025-09-06 00:00:00",
    "endTime": "2030-12-31 23:59:59",
    "drawPoint": "24",
    "drawTypeText": "消耗积分抽奖",
    "availablePoint": "2860.5",
    "drawDecision": {
        "resourceEligible": True,
        "nextConsumption": {
            "type": "POINTS",
            "points": "24",
            "chances": 0,
            "text": "本次将消耗 24 积分",
        },
    },
    "prizes": [
        {"name": "积分霸王餐", "imageUrl": "", "typeText": "优惠券"},
        {"name": "麦金卡7天", "imageUrl": "", "typeText": "会员卡"},
        {"name": "早餐卡7天", "imageUrl": "", "typeText": "权益卡"},
        {"name": "下单立减3元券", "imageUrl": "", "typeText": "优惠券"},
        {"name": "麦旋风二选一7元优惠券", "imageUrl": "", "typeText": "优惠券"},
        {"name": "圆筒冰淇淋4折优惠券", "imageUrl": "", "typeText": "优惠券"},
        {"name": "麦辣鸡腿汉堡5折优惠券", "imageUrl": "", "typeText": "优惠券"},
    ],
}

# ------------------------------------------------------------------ 优惠券 / 奖品

_MY_COUPONS = {
    "coupons": [
        {
            "id": "8692944B045928451618BFF22F535D2A",
            "code": "MCD669T500115004R7079",
            "title": "中薯条买一送一",
            "subtitle": "",
            "discountInfo": {
                "discountValue": "13.5",
                "discountDesc": "用券价格",
                "discountTypePosition": 1,
                "discountTypeText": "¥",
            },
            "tradeStartDate": "2026-10-12",
            "tradeEndDate": "2026-10-16",
            "totalCount": 1,
            "totalAvailableCount": 1,
            "orderType": 1,
            "orderTypes": [1, 2],
            "tags": [
                {"type": 2, "value": "pickup", "label": "到店专用", "color": "#FFBC0D"},
                {"type": 2, "value": "delivery", "label": "外送专用", "color": "#FFBC0D"},
            ],
            "beType": 1,
            "beTypes": [1, 2, 5],
            "promotionId": "112458028",
            "instructions": {
                "labels": [{"text": "未到使用时间", "color": "#666666", "code": 2}],
                "availableTime": [
                    {"text": "2026.10.12-2026.10.16", "color": "#666666", "type": 1},
                    {"text": "10:30-23:59", "color": "#666666", "type": 1},
                ],
            },
        },
        {
            "id": "5F1A0C77B2E34D0A8C11223344556677",
            "code": "MCD669T500115004R7080",
            "title": "满 30 减 8 元券",
            "subtitle": "到店 / 外送通用",
            "discountInfo": {
                "discountValue": "8",
                "discountDesc": "立减",
                "discountTypePosition": 1,
                "discountTypeText": "¥",
            },
            "tradeStartDate": "2026-10-01",
            "tradeEndDate": "2026-10-31",
            "totalCount": 2,
            "totalAvailableCount": 2,
            "orderType": 1,
            "orderTypes": [1, 2],
            "tags": [{"type": 1, "value": "all", "label": "全渠道", "color": "#DA291C"}],
            "beType": 1,
            "beTypes": [1, 2, 5, 6],
            "promotionId": "112458029",
            "instructions": {
                "labels": [{"text": "可用", "color": "#DA291C", "code": 1}],
                "availableTime": [
                    {"text": "2026.10.01-2026.10.31", "color": "#666666", "type": 1}
                ],
            },
        },
        {
            "id": "77AA11BB22CC33DD44EE55FF66001122",
            "code": "MCD669T500115004R7081",
            "title": "早餐两件套 9.9 元",
            "subtitle": "",
            "discountInfo": {
                "discountValue": "9.9",
                "discountDesc": "用券价格",
                "discountTypePosition": 1,
                "discountTypeText": "¥",
            },
            "tradeStartDate": "2026-10-08",
            "tradeEndDate": "2026-10-21",
            "totalCount": 5,
            "totalAvailableCount": 3,
            "orderType": 1,
            "orderTypes": [1],
            "tags": [{"type": 2, "value": "pickup", "label": "到店专用", "color": "#FFBC0D"}],
            "beType": 1,
            "beTypes": [1],
            "promotionId": "112458030",
            "instructions": {
                "labels": [{"text": "可用", "color": "#DA291C", "code": 1}],
                "availableTime": [
                    {"text": "2026.10.08-2026.10.21", "color": "#666666", "type": 1},
                    {"text": "周一至周五 07:00-10:30", "color": "#666666", "type": 2},
                ],
            },
        },
    ]
}

_AVAILABLE_COUPONS = [
    {"couponName": "免费脆薯饼", "couponImage": "", "couponStatus": "CAN_GET", "label": "可领取"},
    {"couponName": "人气麦旋风买一送一", "couponImage": "", "couponStatus": "CAN_GET", "label": "可领取"},
    {"couponName": "9.9元中杯冰美式", "couponImage": "", "couponStatus": "HAVING_RECEIVE", "label": "已领取"},
    {"couponName": "巧克力味厚松饼猪柳蛋套餐", "couponImage": "", "couponStatus": "HAVING_RECEIVE", "label": "已领取"},
]

_MY_PRIZES = {
    "status": {"code": "SUCCESS", "message": "成功"},
    "prizes": [
        {"id": "6ac9b28a51941e69a1141bac", "name": "寒露品鉴会门票", "prizeType": 25,
         "prizeTypeText": "门票", "recordTime": "2026-10-10 11:35:38", "status": 0, "statusText": "可用"},
        {"id": "6abb32f7a4d2a20c9433eb4a", "name": "秋分品鉴会门票", "prizeType": 25,
         "prizeTypeText": "门票", "recordTime": "2026-09-29 11:39:35", "status": 0, "statusText": "可用"},
        {"id": "6a9fa2e4d0c8bc0f2cd73b1d", "name": "白露主题派对门票", "prizeType": 25,
         "prizeTypeText": "门票", "recordTime": "2026-09-08 13:53:40", "status": 0, "statusText": "可用"},
        {"id": "6a5c582bf836c95b08315f04", "name": "小暑品鉴会门票", "prizeType": 25,
         "prizeTypeText": "门票", "recordTime": "2026-07-19 12:52:58", "status": 1, "statusText": "已过期"},
    ],
}

# ------------------------------------------------------------------ 演示客户端


def _ok(data: Any) -> dict:
    """成功信封。"""
    return {
        "success": True,
        "code": 200,
        "message": "请求成功",
        "datetime": _NOW["formatted"],
        "traceId": "demo" + hashlib.md5(str(data)[:64].encode("utf-8")).hexdigest()[:16],
        "data": data,
    }


_DIFF_CENTS_RE = re.compile(r"([+-])\s*¥?\s*([\d.]+)")


def _diff_cents(text: Any) -> int:
    """把 ``"+ ¥1.5"`` 形式的差价解析为「分」。"""
    if isinstance(text, (int, float)):
        return int(round(float(text) * 100))
    if not text:
        return 0
    match = _DIFF_CENTS_RE.search(str(text))
    if not match:
        return 0
    sign, number = match.groups()
    try:
        cents = int(round(float(number) * 100))
    except ValueError:
        return 0
    return -cents if sign == "-" else cents


def _fail(code: int, message: str) -> dict:
    """失败信封。"""
    return {
        "success": False,
        "code": code,
        "message": message,
        "datetime": _NOW["formatted"],
        "traceId": "demo" + hashlib.md5(f"{code}{message}".encode()).hexdigest()[:16],
    }


class DemoMCDClient:
    """演示用客户端，返回与真实 MCP 同构的模拟数据。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def list_tools(self) -> list[str]:
        return [
            "now-time-info", "order-list", "query-my-account", "query-meals",
            "query-meal-detail", "list-nutrition-foods", "calculate-price",
            "campaign-calendar", "query-lottery-info", "query-nearby-stores",
            "query-store-coupons", "query-my-coupons", "available-coupons",
            "query-my-prizes", "query-meal-assistance", "query-promotions",
        ]

    async def aclose(self) -> None:
        return None

    async def call(self, tool: str, arguments: dict | None = None) -> Any:
        arguments = arguments or {}
        self.calls.append(tool)
        handler = getattr(self, "_h_" + tool.replace("-", "_"), None)
        if handler is None:
            raise MCDError(f"演示客户端不支持工具：{tool}")
        return handler(arguments)

    # ---------------------------------------------------------- 各工具处理器

    def _h_now_time_info(self, _args: dict) -> dict:
        return _ok(copy.deepcopy(_NOW))

    def _h_order_list(self, _args: dict) -> dict:
        return _ok(copy.deepcopy(_ORDERS))

    def _h_query_my_account(self, _args: dict) -> dict:
        return _ok(copy.deepcopy(_ACCOUNT))

    def _h_list_nutrition_foods(self, _args: dict) -> dict:
        return _ok(_nutrition_text())

    def _h_campaign_calendar(self, args: dict) -> dict:
        data = copy.deepcopy(_CALENDAR)
        anchor = str(args.get("specifiedDate") or "")
        if anchor:
            data["dailyList"] = [
                day for day in data["dailyList"] if day["date"] <= anchor
            ] or data["dailyList"]
        return _ok(data)

    def _h_query_lottery_info(self, _args: dict) -> dict:
        return _ok(copy.deepcopy(_LOTTERY))

    def _h_query_my_coupons(self, _args: dict) -> dict:
        return _ok(copy.deepcopy(_MY_COUPONS))

    def _h_available_coupons(self, _args: dict) -> dict:
        return _ok(copy.deepcopy(_AVAILABLE_COUPONS))

    def _h_query_my_prizes(self, _args: dict) -> dict:
        return _ok(copy.deepcopy(_MY_PRIZES))

    def _h_query_nearby_stores(self, args: dict) -> dict:
        city = str(args.get("city") or "").strip()
        keyword = str(args.get("keyword") or "").strip()
        if not city or not keyword:
            return _fail(600058, "城市名或者关键词不能为空")
        be_type = args.get("beType")
        if be_type not in (1, 5):
            return _fail(600047, "beType必传，1：到店自提, 5-得来速车道取餐(Drive Through)")
        rows = copy.deepcopy(_STORES)
        if be_type == 5:
            for row in rows:
                row["beCode"] = f"DT-{row['storeCode']}"
        return _ok(rows)

    def _h_query_meals(self, args: dict) -> dict:
        if not args.get("storeCode"):
            return _fail(600047, "storeCode 不能为空")
        if args.get("orderType") not in (1, 2) or args.get("beType") not in (1, 2, 5, 6):
            return _fail(600047, "orderType / beType 必传")
        if args.get("beType") in (2, 5, 6) and not args.get("beCode"):
            return _fail(600048, "外送场景下，beType=2/5/6时必传beCode")
        return _ok(_menu_payload())

    def _h_query_meal_detail(self, args: dict) -> dict:
        if not args.get("storeCode"):
            return _fail(600047, "storeCode 不能为空")
        code = str(args.get("code") or "")
        if not code:
            return _fail(600047, "code 不能为空")
        detail = _detail_for(code)
        if not detail:
            return _fail(600056, f"未找到餐品：{code}")
        return _ok(detail)

    def _h_calculate_price(self, args: dict) -> dict:
        if not args.get("storeCode"):
            return _fail(600047, "storeCode 不能为空")
        items = args.get("items") or []
        if not items:
            return _fail(600049, "items 不能为空")

        product_list = []
        original_total = 0
        total = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            code = str(item.get("productCode") or "")
            qty = int(item.get("quantity") or 1)
            entry = _CATALOG.get(code)
            if not entry:
                continue

            # 套餐改配：按 roundList 逐轮校验并叠加差价（与真实接口行为一致）
            round_list = item.get("roundList")
            if round_list:
                computed = self._price_round_list(code, round_list)
                if computed is None:
                    return _fail(
                        60006,
                        "商品已售罄或不可售，换一个商品或检查orderType/beType",
                    )
                unit = computed
            else:
                unit = entry["price"]

            subtotal = unit * qty
            original_total += subtotal
            total += subtotal
            product_list.append(
                {
                    "productCode": code,
                    "productName": entry["name"],
                    "quantity": qty,
                    "originalSubtotal": subtotal,
                    "subtotal": subtotal,
                }
            )
        if not product_list:
            return _fail(600056, "没有可计算价格的商品")

        return _ok(
            {
                "productOriginalPrice": original_total,
                "productPrice": total,
                "originalPrice": original_total,
                "discount": original_total - total,
                "price": total,
                "productList": product_list,
                "takeWayList": [
                    {"code": "eat-in", "title": "堂食", "subtitle": "店内用餐"},
                    {"code": "take-in-store", "title": "外带", "subtitle": "店内自提"},
                ],
            }
        )

    @staticmethod
    def _price_round_list(code: str, round_list: list) -> int | None:
        """按 roundList 逐轮校验并叠加差价；不合法返回 None（对应真实 60006）。

        真实规则：
          * roundList 必须覆盖**全部**轮次
          * ``round`` 是轮次数字 id 的字符串
          * 只能选该轮次 ``choices`` 里真实存在的 code
        """
        entry = _CATALOG.get(code)
        detail = _DETAILS.get(code)
        if entry is None or detail is None:
            return None

        rounds = detail.get("rounds") or []
        by_id = {str(r.get("id")): r for r in rounds}
        if len(round_list) != len(rounds):
            return None

        total = entry["price"]
        seen: set[str] = set()
        for raw in round_list:
            if not isinstance(raw, dict):
                return None
            round_id = str(raw.get("round"))
            round_ = by_id.get(round_id)
            if round_ is None or round_id in seen:
                return None
            seen.add(round_id)

            combo_items = raw.get("comboItemList") or []
            if not combo_items:
                return None
            for combo_item in combo_items:
                if not isinstance(combo_item, dict):
                    return None
                chosen_code = str(combo_item.get("code") or "")
                match = next(
                    (c for c in round_.get("choices", []) if str(c.get("code")) == chosen_code),
                    None,
                )
                if match is None:
                    return None
                qty = int(combo_item.get("quantity") or 1)
                total += _diff_cents(match.get("diffPrice")) * qty
        return max(total, 0)

    def _h_query_store_coupons(self, args: dict) -> dict:
        if not args.get("storeCode"):
            return _fail(600047, "storeCode 不能为空")
        # 演示：到店场景有券，外送场景无券（贴近真实返回）
        if args.get("orderType") == 1 and args.get("beType") == 1:
            return _ok(
                [
                    {
                        "id": "5F1A0C77B2E34D0A8C11223344556677",
                        "code": "MCD669T500115004R7080",
                        "title": "满 30 减 8 元券",
                        "discountInfo": {
                            "discountValue": "8",
                            "discountDesc": "立减",
                            "discountTypeText": "¥",
                        },
                        "tradeStartDate": "2026-10-01",
                        "tradeEndDate": "2026-10-31",
                    }
                ]
            )
        return _ok([])

    def _h_query_meal_assistance(self, args: dict) -> dict:
        if args.get("beType") != 6:
            return _fail(610501, "仅支持企业团餐场景下使用助餐服务")
        if not args.get("storeCode"):
            return _fail(600047, "storeCode 不能为空")
        if not args.get("beCode"):
            return _fail(600048, "外送场景下，beType=2/5/6时必传beCode")
        return _ok(
            [
                {"gmServiceCode": "GM001", "name": "分批取餐", "desc": "支持 30 分钟内分批到店取餐"},
                {"gmServiceCode": "GM002", "name": "统一配送", "desc": "整单统一配送至指定地址"},
            ]
        )

    def _h_query_promotions(self, args: dict) -> dict:
        if args.get("beType") != 6:
            return _fail(610502, "仅支持企业团餐场景下查询促销规则")
        if not args.get("beCode"):
            return _fail(600048, "外送场景下，beType=2/5/6时必传beCode")
        return _ok(
            [
                {
                    "promotionId": "P1001",
                    "promotionType": 31,
                    "ruleCategory": "满额减",
                    "startTime": "2026-10-01 00:00:00",
                    "endTime": "2026-10-31 23:59:59",
                    "ruleDetail": "满 200 减 30",
                },
                {
                    "promotionId": "P1002",
                    "promotionType": 31,
                    "ruleCategory": "满额减",
                    "startTime": "2026-10-01 00:00:00",
                    "endTime": "2026-10-31 23:59:59",
                    "ruleDetail": "满 500 减 90",
                },
            ]
        )

    def _h_delivery_query_stores(self, args: dict) -> dict:
        if not args.get("addressId"):
            return _fail(600047, "addressId 不能为空")
        rows = copy.deepcopy(_STORES)
        for row in rows:
            row["beCode"] = f"DLV-{row['storeCode']}"
        return _ok(rows)


def demo_seed(text: str) -> int:
    """把任意文本转成稳定的整数种子（用于运势签等确定性随机）。"""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)

"""演示客户端保真度测试。

核心思路：离线演示必须和真实 MCP **同构**，
包括错误码、字段名、金额单位、roundList 校验规则。
否则「演示能跑」就完全不能说明「线上能跑」。
"""

import asyncio

from mcd_buddy.demo import DemoMCDClient
from mcd_buddy.mcd_api import unwrap

STORE = "1420525"
COMBO = "9900011056"


def call(tool, args=None):
    return asyncio.run(DemoMCDClient().call(tool, args or {}))


def raw(tool, args=None):
    """返回拆掉信封后的 data；失败则抛异常。"""
    return unwrap(call(tool, args), tool)


class TestEnvelope:
    def test_success_envelope_shape(self):
        payload = call("now-time-info")
        assert set(payload) >= {"success", "code", "message", "datetime", "traceId", "data"}
        assert payload["success"] is True
        assert payload["code"] == 200

    def test_failure_envelope_shape(self):
        payload = call("query-nearby-stores", {"beType": 1})
        assert payload["success"] is False
        assert payload["code"] == 600058
        assert "data" not in payload


class TestRealFieldNames:
    def test_now_time_info(self):
        data = raw("now-time-info")
        assert data["date"] == "2026-10-10"
        assert data["dayOfWeek"] == "SATURDAY"

    def test_account_values_are_strings(self):
        # 真实接口里积分是字符串，不是数字
        data = raw("query-my-account")
        assert isinstance(data["availablePoint"], str)
        assert isinstance(data["accumulativePoint"], str)

    def test_orders_use_combo_item_list(self):
        data = raw("order-list")
        first = data["list"][0]
        assert first["realTotalAmount"] == "13.9"
        assert isinstance(first["realTotalAmount"], str)
        combo = first["orderProductList"][0]
        assert combo["comboItemList"][0]["name"]

    def test_nutrition_is_compact_table_string(self):
        data = raw("list-nutrition-foods")
        assert isinstance(data, str)
        assert data.startswith("[")
        assert "productName,nutritionDescription,energyKj" in data

    def test_stores_are_flat_list(self):
        data = raw("query-nearby-stores", {"beType": 1, "searchType": 2, "city": "深圳市", "keyword": "麦当劳"})
        assert isinstance(data, list)
        assert {"storeCode", "storeName", "businessStatus", "businessStartTime", "businessEndTime"} <= set(data[0])

    def test_menu_only_has_code_and_tags(self):
        data = raw("query-meals", {"storeCode": STORE, "orderType": 1, "beType": 1})
        meal = data["categories"][0]["meals"][0]
        assert "code" in meal
        assert "name" not in meal  # 真实接口不给名称
        assert "price" not in meal  # 也不给价格

    def test_meal_detail_uses_rounds(self):
        data = raw("query-meal-detail", {"storeCode": STORE, "orderType": 1, "beType": 1, "code": COMBO})
        assert data["rounds"]
        round_ = data["rounds"][0]
        assert {"id", "name", "quantity", "choices"} <= set(round_)
        choice = round_["choices"][0]
        assert {"code", "name", "quantity", "isDefault", "diffPrice"} <= set(choice)
        assert choice["diffPrice"].startswith("+")

    def test_price_amounts_are_cents(self):
        data = raw(
            "calculate-price",
            {"storeCode": STORE, "orderType": 1, "beType": 1, "items": [{"productCode": "1440", "quantity": 1}]},
        )
        assert data["price"] == 2250  # 分
        assert data["productList"][0]["subtotal"] == 2250

    def test_lottery_shape(self):
        data = raw("query-lottery-info")
        assert data["activityStatusText"] == "进行中"
        assert data["drawDecision"]["nextConsumption"]["points"] == "24"
        assert data["prizes"][0]["typeText"]

    def test_calendar_shape(self):
        data = raw("campaign-calendar")
        day = data["dailyList"][0]
        assert {"date", "dateText", "events", "today"} <= set(day)
        assert day["events"][0]["articleDto"]["title"]


class TestRealValidationRules:
    def test_nearby_stores_requires_city_and_keyword(self):
        assert call("query-nearby-stores", {"beType": 1, "searchType": 2, "keyword": "深圳"})["code"] == 600058
        assert call("query-nearby-stores", {"beType": 1, "searchType": 2, "city": "深圳市"})["code"] == 600058

    def test_delivery_requires_be_code(self):
        payload = call("query-meals", {"storeCode": STORE, "orderType": 2, "beType": 2})
        assert payload["code"] == 600048

    def test_assistance_only_for_group(self):
        assert call("query-meal-assistance", {"storeCode": STORE})["code"] == 610501

    def test_unknown_meal_code(self):
        payload = call("query-meal-detail", {"storeCode": STORE, "orderType": 1, "beType": 1, "code": "999999999"})
        assert payload["code"] == 600056


class TestRoundListValidation:
    """roundList 是改配套餐定价的关键，校验规则必须和线上一致。"""

    DEFAULT_ROUNDS = [
        ("1", "1440", 1), ("2", "1406", 1), ("3", "515106", 1),
        ("4", "1700", 1), ("5", "4810", 2), ("6", "3050", 2),
    ]

    def _price(self, overrides=None, rounds=None):
        overrides = overrides or {}
        source = rounds or self.DEFAULT_ROUNDS
        round_list = [
            {"round": rid, "comboItemList": [{"code": overrides.get(rid, code), "quantity": qty}]}
            for rid, code, qty in source
        ]
        data = raw(
            "calculate-price",
            {
                "storeCode": STORE,
                "orderType": 1,
                "beType": 1,
                "items": [{"productCode": COMBO, "quantity": 1, "roundList": round_list}],
            },
        )
        return data["price"]

    def test_full_default_round_list_matches_base_price(self):
        assert self._price() == 11450

    def test_diff_price_multiplies_by_quantity(self):
        # 轮5 数量 2，大杯玉米杯 diffPrice +¥2.5 → +500 分
        assert self._price({"5": "4438"}) == 11450 + 500

    def test_round3_diff(self):
        # 轮3 数量 1，麦辣鸡翅2块 diffPrice +¥3.5 → +350 分
        assert self._price({"3": "1700"}) == 11450 + 350

    def test_combined_diffs(self):
        assert self._price({"3": "1700", "5": "4438"}) == 11450 + 350 + 500

    def test_zero_diff_swap_keeps_price(self):
        # 奥利奥麦旋风在轮5 的 diffPrice 是 +¥0（与真实数据一致）
        assert self._price({"5": "1217"}) == 11450

    def test_incomplete_round_list_is_rejected(self):
        payload = call(
            "calculate-price",
            {
                "storeCode": STORE,
                "orderType": 1,
                "beType": 1,
                "items": [
                    {
                        "productCode": COMBO,
                        "quantity": 1,
                        "roundList": [{"round": "1", "comboItemList": [{"code": "1440", "quantity": 1}]}],
                    }
                ],
            },
        )
        assert payload["code"] == 60006

    def test_invalid_choice_for_round_is_rejected(self):
        # 3300（锡兰红茶）不在「选择汉堡」轮次的可选范围内
        payload = call(
            "calculate-price",
            {
                "storeCode": STORE,
                "orderType": 1,
                "beType": 1,
                "items": [
                    {
                        "productCode": COMBO,
                        "quantity": 1,
                        "roundList": [
                            {"round": rid, "comboItemList": [{"code": {"1": "3300"}.get(rid, code), "quantity": q}]}
                            for rid, code, q in self.DEFAULT_ROUNDS
                        ],
                    }
                ],
            },
        )
        assert payload["code"] == 60006

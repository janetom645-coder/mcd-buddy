"""业务层（mcd_api）单元测试。

这里覆盖的全是「真实接口和直觉不一致」的地方 —— 每一个断言都对应一次线上踩坑。
"""

import asyncio

import pytest

from mcd_buddy.demo import DemoMCDClient
from mcd_buddy.mcd_api import (
    BE_DELIVERY,
    BE_DINE_IN,
    BE_DRIVE_THRU,
    BE_GROUP,
    MCDApiError,
    cents_to_yuan,
    default_composition,
    extract_rounds,
    fetch_menu,
    fetch_my_coupons,
    lookup_nutrition,
    parse_diff_price,
    parse_menu_codes,
    parse_nutrition_table,
    resolve_store,
    safe_call,
    search_stores,
    to_float,
    unwrap,
)


def run(coro):
    return asyncio.run(coro)


class TestUnwrap:
    def test_returns_data_on_success(self):
        assert unwrap({"success": True, "data": {"a": 1}}) == {"a": 1}

    def test_raises_on_failure_with_code(self):
        with pytest.raises(MCDApiError) as exc:
            unwrap({"success": False, "code": 600058, "message": "城市名或者关键词不能为空"})
        assert "600058" in str(exc.value)
        assert "城市名或者关键词不能为空" in str(exc.value)

    def test_passthrough_when_no_envelope(self):
        assert unwrap([1, 2]) == [1, 2]


class TestSafeCall:
    def test_swallows_business_error(self):
        client = DemoMCDClient()
        # 缺 city/keyword → 600058，应降级为 default 而不是抛异常
        assert run(safe_call(client, "query-nearby-stores", {"beType": 1}, default=[])) == []

    def test_returns_data_on_success(self):
        client = DemoMCDClient()
        data = run(safe_call(client, "now-time-info", {}, default={}))
        assert data["date"] == "2026-10-10"


class TestUnits:
    def test_cents_to_yuan(self):
        assert cents_to_yuan(7950) == 79.5
        assert cents_to_yuan(450) == 4.5
        assert cents_to_yuan("11450") == 114.5

    def test_cents_to_yuan_bad_input(self):
        assert cents_to_yuan(None) == 0.0
        assert cents_to_yuan("abc") == 0.0

    def test_to_float_handles_strings(self):
        # 真实接口里 realTotalAmount / availablePoint 都是字符串
        assert to_float("13.9") == 13.9
        assert to_float("192.6") == 192.6
        assert to_float("") == 0.0
        assert to_float(None, 1.5) == 1.5


class TestParseDiffPrice:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("+ ¥0", 0.0),
            ("+ ¥1.5", 1.5),
            ("- ¥2.5", -2.5),
            ("+ ¥11", 11.0),
            ("", 0.0),
            (3.5, 3.5),
            ("乱七八糟", 0.0),
        ],
    )
    def test_parses(self, text, expected):
        assert parse_diff_price(text) == expected


class TestParseNutritionTable:
    TABLE = (
        "[2]{productName,nutritionDescription,energyKj,energyKcal,"
        "protein,fat,carbohydrate,sodium,calcium}:\n"
        "  巨无霸,null,2146,513,27,26,42,961,171\n"
        "  中薯条,null,1210,289,4,12,38,165,18"
    )

    def test_parses_rows(self):
        table = parse_nutrition_table(self.TABLE)
        assert set(table) == {"巨无霸", "中薯条"}
        assert table["巨无霸"]["energyKcal"] == 513
        assert table["巨无霸"]["protein"] == 27
        assert table["中薯条"]["sodium"] == 165

    def test_accepts_envelope_dict(self):
        table = parse_nutrition_table({"data": self.TABLE})
        assert "巨无霸" in table

    def test_garbage_returns_empty(self):
        assert parse_nutrition_table("不是表格") == {}
        assert parse_nutrition_table(None) == {}


class TestLookupNutrition:
    TABLE = {
        "麦辣鸡翅-2块": {"name": "麦辣鸡翅-2块", "energyKcal": 224.0},
        "纯牛奶（盒装）": {"name": "纯牛奶（盒装）", "energyKcal": 129.0},
        "巨无霸": {"name": "巨无霸", "energyKcal": 513.0},
    }

    def test_exact(self):
        assert lookup_nutrition(self.TABLE, "巨无霸")["energyKcal"] == 513

    def test_normalises_hyphen_difference(self):
        # 菜单叫「麦辣鸡翅2块」，营养表叫「麦辣鸡翅-2块」
        assert lookup_nutrition(self.TABLE, "麦辣鸡翅2块")["energyKcal"] == 224

    def test_normalises_bracket_difference(self):
        assert lookup_nutrition(self.TABLE, "纯牛奶")["energyKcal"] == 129

    def test_missing_returns_empty(self):
        # 关键：查不到必须返回空 dict，让调用方能区分「0 热量」和「没数据」
        assert lookup_nutrition(self.TABLE, "不存在的商品") == {}


class TestParseMenuCodes:
    def test_reads_categories_and_tags(self):
        data = {
            "categories": [
                {"name": "人气热卖", "meals": [{"code": "521954"}, {"code": "9900004064", "tags": ["爆款"]}]},
                {"name": "冷饮", "meals": [{"code": "6352", "tags": ["冷饮"]}]},
            ]
        }
        items = parse_menu_codes(data)
        assert [i.code for i in items] == ["521954", "9900004064", "6352"]
        assert items[1].tags == ["爆款"]
        assert items[2].category == "冷饮"

    def test_dedupes_codes(self):
        data = {"categories": [{"name": "A", "meals": [{"code": "1"}]}, {"name": "B", "meals": [{"code": "1"}]}]}
        assert len(parse_menu_codes(data)) == 1

    def test_garbage_returns_empty(self):
        assert parse_menu_codes(None) == []
        assert parse_menu_codes({"categories": "不是列表"}) == []


DETAIL = {
    "code": "9900011056",
    "name": "全明星双人分享餐八件套",
    "rounds": [
        {
            "id": 1,
            "name": "选择汉堡",
            "quantity": 1,
            "maxQuantity": 1,
            "minQuantity": 1,
            "choices": [
                {"code": "1440", "name": "麦辣鸡腿汉堡", "quantity": 1, "isDefault": 1,
                 "diffPrice": "+ ¥0", "supportModify": True},
                {"code": "1010", "name": "巨无霸", "quantity": 0, "isDefault": 0,
                 "diffPrice": "+ ¥2.5", "supportModify": False},
            ],
        },
        {
            "id": 5,
            "name": "选择小食",
            "quantity": 2,
            "maxQuantity": 2,
            "minQuantity": 2,
            "choices": [
                {"code": "4810", "name": "中薯条", "quantity": 2, "isDefault": 1,
                 "diffPrice": "+ ¥0", "supportModify": False},
                {"code": "4438", "name": "大杯玉米杯", "quantity": 0, "isDefault": 0,
                 "diffPrice": "+ ¥2.5", "supportModify": False},
            ],
        },
    ],
}


class TestExtractRounds:
    def test_reads_rounds_and_choices(self):
        rounds = extract_rounds(DETAIL)
        assert len(rounds) == 2
        assert rounds[0].name == "选择汉堡"
        assert [c.name for c in rounds[0].choices] == ["麦辣鸡腿汉堡", "巨无霸"]

    def test_parses_default_and_diff(self):
        first = extract_rounds(DETAIL)[0]
        assert first.default_choice.code == "1440"
        assert first.default_choice.selected is True
        assert first.choices[1].diff_price == 2.5
        assert first.choices[1].selected is False

    def test_round_quantity(self):
        assert extract_rounds(DETAIL)[1].quantity == 2

    def test_empty_detail(self):
        assert extract_rounds({}) == []


class TestDefaultComposition:
    def test_picks_default_per_round(self):
        comp = default_composition(DETAIL)
        assert [c["name"] for c in comp] == ["麦辣鸡腿汉堡", "中薯条"]
        assert comp[1]["quantity"] == 2

    def test_single_item_falls_back(self):
        comp = default_composition({"code": "1440", "name": "麦辣鸡腿汉堡"})
        assert comp == [
            {"name": "麦辣鸡腿汉堡", "code": "1440", "group": "单品", "quantity": 1, "diff_price": 0.0}
        ]


class TestSearchStores:
    def test_requires_city_and_keyword(self):
        # 真实接口：只传 keyword 或只传 city 都会报 600058
        with pytest.raises(MCDApiError):
            run(search_stores(DemoMCDClient(), city="", keyword="深圳"))
        with pytest.raises(MCDApiError):
            run(search_stores(DemoMCDClient(), city="深圳市", keyword=""))

    def test_returns_stores_when_both_given(self):
        stores = run(search_stores(DemoMCDClient(), city="深圳市", keyword="麦当劳"))
        assert stores
        assert stores[0].store_code
        assert stores[0].open_time and stores[0].close_time

    def test_drive_thru_returns_stores(self):
        stores = run(search_stores(DemoMCDClient(), city="深圳市", keyword="麦当劳", be_type=BE_DRIVE_THRU))
        assert stores
        assert all(s.store_code for s in stores)


class TestResolveStore:
    def test_prefers_open_store(self):
        store = run(resolve_store(DemoMCDClient(), city="深圳市", keyword="麦当劳"))
        assert store is not None and store.open is True

    def test_explicit_store_code_skips_search(self):
        store = run(resolve_store(DemoMCDClient(), store_code="1420525"))
        assert store is not None and store.store_code == "1420525"

    def test_raises_without_city(self):
        with pytest.raises(MCDApiError):
            run(resolve_store(DemoMCDClient(), city=""))


class TestFetchMenu:
    def test_enriches_names_and_prices(self):
        # query-meals 只给 code + tags，名称与价格要靠 calculate-price 补全
        menu = run(fetch_menu(DemoMCDClient(), "1420525"))
        assert menu
        named = [i for i in menu if i.name and i.price > 0]
        assert len(named) == len(menu), "所有菜单项都应补全名称与价格"
        burger = next(i for i in menu if i.code == "1440")
        assert burger.name == "麦辣鸡腿汉堡"
        assert burger.price == 22.5  # 分 → 元

    def test_codes_and_tags_present(self):
        menu = run(fetch_menu(DemoMCDClient(), "1420525"))
        fries = next(i for i in menu if i.code == "4810")
        assert "油炸" in fries.tags


class TestFetchCoupons:
    def test_my_coupons_parsed(self):
        coupons = run(fetch_my_coupons(DemoMCDClient()))
        assert coupons
        assert coupons[0].title
        assert coupons[0].value_text

    def test_store_coupons_empty_for_delivery(self):
        from mcd_buddy.mcd_api import fetch_store_coupons

        assert run(fetch_store_coupons(DemoMCDClient(), "1420525", order_type=2, be_type=BE_DELIVERY)) == []


class TestStoreFirstArgs:
    """外送 / 团餐场景必须带 beCode；到店自取不能带。"""

    def test_dine_in_without_be_code_ok(self):
        menu = run(fetch_menu(DemoMCDClient(), "1420525", order_type=1, be_type=BE_DINE_IN))
        assert menu

    def test_delivery_without_be_code_fails(self):
        with pytest.raises(MCDApiError):
            run(fetch_menu(DemoMCDClient(), "1420525", order_type=2, be_type=BE_DELIVERY))

    def test_group_with_be_code_ok(self):
        menu = run(fetch_menu(DemoMCDClient(), "1420525", order_type=2, be_type=BE_GROUP, be_code="GM-1"))
        assert menu

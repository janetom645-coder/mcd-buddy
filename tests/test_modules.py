"""四大模块的集成测试（使用离线演示客户端，不需要 Token）。

演示客户端与真实 MCP 同构，所以这里跑通的链路和线上是同一条代码路径。
"""

import asyncio
import os
import pathlib
import subprocess
import sys

import pytest

import mcd_buddy
from mcd_buddy.demo import DemoMCDClient
from mcd_buddy.mcd_api import BE_DINE_IN, ORDER_PICKUP, MenuItem, Store, fetch_menu
from mcd_buddy.modules import (
    FortuneModule,
    GroupMealModule,
    HiddenMenuModule,
    PracticeModule,
)
from mcd_buddy.modules.group_meal import Person, _hit, _is_meal, _match, _meal_tier
from mcd_buddy.modules.hidden_menu import recipe_code
from mcd_buddy.utils import display_width

DEMO_STORE = Store(
    store_code="1420525",
    name="麦当劳深圳福华一路(卓悦中心)餐厅",
    open=True,
    open_time="00:00",
    close_time="23:59",
)

COMBO = "双人分享餐"  # 演示菜单里的「全明星双人分享餐八件套」


def run(coro):
    return asyncio.run(coro)


def assert_cards_aligned(text: str) -> None:
    """所有卡片行必须等宽，否则说明中文/emoji 宽度计算有误。"""
    box = [line for line in text.split("\n") if line[:1] in ("│", "╭", "╰")]
    assert box, "没有渲染出卡片"
    widths = {display_width(line) for line in box}
    assert len(widths) == 1, f"卡片边框未对齐：{widths}"


@pytest.fixture(scope="module")
def practice_output():
    return run(PracticeModule().run(DemoMCDClient()))


@pytest.fixture(scope="module")
def group_meal_output():
    people = [
        Person(name="小王", budget=25, want="牛肉"),
        Person(name="小李", budget=20, want="鸡肉", avoid=["辣"]),
        Person(name="小张", budget=15, want="鱼"),
    ]
    return run(GroupMealModule().run(DemoMCDClient(), people, DEMO_STORE))


@pytest.fixture(scope="module")
def hidden_menu_output():
    return run(HiddenMenuModule().run(DemoMCDClient(), DEMO_STORE.store_code, COMBO, "减脂"))


@pytest.fixture(scope="module")
def fortune_output():
    return run(FortuneModule().run(DemoMCDClient()))


class TestPracticeModule:
    def test_contains_title(self, practice_output):
        assert "麦门修行录" in practice_output

    def test_contains_stats(self, practice_output):
        assert "累计点餐" in practice_output and "当前连击" in practice_output

    def test_reads_combo_items_from_real_shape(self, practice_output):
        # 真实订单里套餐在 comboItemList 下，子项也要被统计进「本命单品」
        assert "高达吉士双牛堡" in practice_output

    def test_reads_points_as_string(self, practice_output):
        assert "2860.5 分" in practice_output

    def test_contains_achievements(self, practice_output):
        assert "成就徽章" in practice_output
        assert "七日不辍" in practice_output

    def test_cards_aligned(self, practice_output):
        assert_cards_aligned(practice_output)


class TestGroupMealModule:
    def test_contains_every_person(self, group_meal_output):
        for name in ("小王", "小李", "小张"):
            assert name in group_meal_output

    def test_respects_avoid_list(self, group_meal_output):
        # 小李忌辣，不应被推荐「麦辣鸡腿汉堡」
        li_row = next(line for line in group_meal_output.split("\n") if line.startswith("| 小李"))
        assert "麦辣鸡腿" not in li_row

    def test_prefers_want_over_budget(self, group_meal_output):
        # 小张想吃鱼，即使超预算也应优先推荐麦香鱼
        zhang_row = next(line for line in group_meal_output.split("\n") if line.startswith("| 小张"))
        assert "麦香鱼" in zhang_row

    def test_reports_budget_overflow(self, group_meal_output):
        # 超预算不能静默吞掉，必须如实说明
        assert "超预算" in group_meal_output

    def test_reports_missing_want(self):
        # 想吃的东西菜单里没有时，也要说明「已经另选了」
        out = run(
            GroupMealModule().run(
                DemoMCDClient(), [Person(name="小陈", budget=30, want="沙拉")], DEMO_STORE
            )
        )
        assert "菜单里没有「沙拉」" in out

    def test_contains_price_summary(self, group_meal_output):
        assert "应付合计" in group_meal_output and "人均分摊" in group_meal_output

    def test_shows_coupons_from_wallet(self, group_meal_output):
        assert "我的卡包" in group_meal_output

    def test_cards_aligned(self, group_meal_output):
        assert_cards_aligned(group_meal_output)

    def test_empty_menu_degrades_gracefully(self):
        closed = Store(store_code="0", name="打烊门店", open=False)
        client = DemoMCDClient()
        client._h_query_meals = lambda args: {"success": True, "code": 200, "data": {"categories": []}}
        out = run(GroupMealModule().run(client, [Person(name="A")], closed))
        assert "不可点餐" in out


class TestGroupMealRecommender:
    """推荐逻辑的质量约束。

    以前是「预算内取最便宜的一份」，在真实菜单上会把 ¥2 的饼干
    推给预算 ¥25 的人 —— 这种推荐会直接毁掉用户对工具的信任。
    """

    def _menu(self):
        return run(
            fetch_menu(DemoMCDClient(), DEMO_STORE.store_code, ORDER_PICKUP, BE_DINE_IN, "")
        )

    def test_budget_is_used_not_underspent(self):
        """25 元预算要花在像样的一份上，而不是被推 2 元饼干。"""
        item = _match(self._menu(), Person(name="阿May", budget=25))
        assert item.price >= 10
        assert item.price <= 25

    def test_never_exceeds_budget_when_affordable(self):
        menu = self._menu()
        for budget in (10, 15, 20, 25, 30, 40):
            item = _match(menu, Person(name="X", budget=budget))
            assert item.price <= budget, f"{budget} 元预算却推了 ¥{item.price}"

    def test_merch_is_never_recommended(self):
        menu = self._menu()
        for person in (Person(name="A"), Person(name="B", budget=25)):
            assert "按摩捶" not in _match(menu, person).name

    def test_sauce_is_never_recommended(self):
        menu = self._menu()
        assert not _match(menu, Person(name="A", budget=5)).name.endswith("酱")

    def test_is_meal_filters_non_food(self):
        names = {m.name for m in self._menu() if _is_meal(m)}
        assert "「葱不求人」按摩捶痒痒挠" not in names
        assert "韩式烟熏芝士风味酱" not in names
        assert "巨无霸" in names

    def test_without_budget_picks_a_main_dish(self):
        """没写预算时，推的应该是一份正经主食，而不是最贵或最便宜的那个。"""
        item = _match(self._menu(), Person(name="A"))
        assert any(hint in item.name for hint in ("堡", "卷", "餐", "随心配"))

    def test_drink_want_picks_a_drink(self):
        item = _match(self._menu(), Person(name="A", budget=40, want="咖啡"))
        assert "咖啡" in item.name

    def test_avoid_still_wins_over_budget(self):
        """忌口优先于「接近预算」：忌辣的人不能因为价格合适就被推辣堡。"""
        item = _match(self._menu(), Person(name="A", budget=25, avoid=["辣"]))
        assert "辣" not in item.name

    def test_flag_burger_is_not_ranked_as_a_side(self):
        """「巨无霸」名字里没有「堡」字，不能因此被当成小食而输给普通单品。

        这条曾经真的踩到：类目判定只看名称时，
        预算 25 想吃牛肉的人会拿到 ¥13.50 的吉士汉堡包而不是 ¥24.50 的巨无霸。
        """
        menu = self._menu()
        big_mac = next(m for m in menu if m.name == "巨无霸")
        assert _meal_tier(big_mac) == 2

        item = _match(menu, Person(name="A", budget=25, want="牛肉"))
        assert item.name == "巨无霸"

    def test_rendered_output_has_no_merch(self):
        """端到端再确认一次：渲染出来的推荐里不能出现周边。"""
        people = [Person(name="小王", budget=25), Person(name="小李", budget=40)]
        out = run(GroupMealModule().run(DemoMCDClient(), people, DEMO_STORE))
        assert "按摩捶" not in out
        assert "痒痒挠" not in out


class TestKeywordMatching:
    """`_hit` 的语义边界。

    真实菜单的标签是长串营销词（「100%纯牛肉」「非油炸」「无咖啡因」），
    既要能命中，又不能命中反义词。
    """

    @staticmethod
    def _item(name="测试品", category="小食", tags=None):
        return MenuItem(code="1", name=name, price=10.0, category=category, tags=tags or [])

    def test_matches_long_marketing_tag(self):
        """「牛肉」要能命中真实标签「100%纯牛肉」。"""
        assert _hit(self._item(tags=["单品", "100%纯牛肉", "人气"]), "牛肉")

    def test_does_not_match_negated_tag(self):
        """「咖啡」不能命中「无咖啡因」。"""
        assert not _hit(self._item(name="锡兰红茶", tags=["热饮", "无咖啡因"]), "咖啡")

    def test_does_not_match_non_fried_tag(self):
        """「油炸」不能命中「非油炸」—— 否则忌口会误伤本来没问题的餐品。"""
        assert not _hit(self._item(name="板烧鸡腿堡", tags=["鸡肉", "非油炸"]), "油炸")

    def test_matches_positive_fried_tag(self):
        assert _hit(self._item(name="中薯条", tags=["油炸", "素食"]), "油炸")

    def test_matches_name_substring(self):
        assert _hit(self._item(name="麦香鱼"), "鱼")

    def test_matches_category(self):
        assert _hit(self._item(name="某餐品", category="炸鸡"), "炸鸡")

    def test_empty_keyword_never_matches(self):
        assert not _hit(self._item(name="巨无霸"), "")
        assert not _hit(self._item(name="巨无霸"), "   ")

    def test_negation_only_counts_before_keyword(self):
        """否定词必须在关键词之前才算否定。"""
        assert _hit(self._item(tags=["牛肉无添加"]), "牛肉")
        assert not _hit(self._item(tags=["无牛肉"]), "牛肉")


class TestHiddenMenuModule:
    def test_contains_recipe_name(self, hidden_menu_output):
        assert "双人分享餐八件套" in hidden_menu_output
        assert "减脂版" in hidden_menu_output

    def test_lists_all_rounds(self, hidden_menu_output):
        assert "选择汉堡" in hidden_menu_output
        assert "选择套餐内饮料" in hidden_menu_output

    def test_contains_nutrition_delta(self, hidden_menu_output):
        assert "营养对比" in hidden_menu_output and "kcal" in hidden_menu_output

    def test_price_is_live_not_estimate(self, hidden_menu_output):
        # 完整 roundList 走通时，价格应来自 calculate-price 实时核算
        assert "已通过 calculate-price 实时核算" in hidden_menu_output

    def test_contains_share_card(self, hidden_menu_output):
        assert "分享配方卡" in hidden_menu_output

    def test_custom_swap_is_applied(self):
        out = run(
            HiddenMenuModule().run(
                DemoMCDClient(), DEMO_STORE.store_code, COMBO, None, {"1": "巨无霸"}
            )
        )
        assert "巨无霸" in out

    def test_unknown_meal_suggests_alternatives(self):
        out = run(HiddenMenuModule().run(DemoMCDClient(), DEMO_STORE.store_code, "不存在的餐品"))
        assert "没找到" in out

    def test_cards_aligned(self, hidden_menu_output):
        assert_cards_aligned(hidden_menu_output)


class TestRecipeCode:
    """配方编号必须**跨进程稳定**（回归测试）。

    编号原先由内置 ``hash()`` 生成，而 ``hash()`` 对字符串是按进程随机加盐的
    （``PYTHONHASHSEED``），于是同一份配方每次运行都得到不同编号 ——
    README / `examples/sample-outputs.md` 里的编号永远对不上，
    「一条命令即可复现」这条承诺也就直接失效了。改用 CRC32 后在这里锁死。
    """

    RECIPE = "全明星双人分享餐八件套·减脂版"
    EXPECTED = "HM-8655"

    def test_matches_expected_value(self):
        assert recipe_code(self.RECIPE) == self.EXPECTED

    def test_is_pure(self):
        # 同进程内多次调用必须一致
        assert recipe_code(self.RECIPE) == recipe_code(self.RECIPE)

    def test_differs_between_recipes(self):
        assert recipe_code(self.RECIPE) != recipe_code("全明星双人分享餐八件套·增肌版")

    def test_rendered_output_uses_the_stable_code(self, hidden_menu_output):
        assert f"配方编号：{self.EXPECTED}" in hidden_menu_output

    def test_stable_across_hash_seeds(self):
        """换 ``PYTHONHASHSEED`` 重开进程，编号必须不变。"""
        src_dir = pathlib.Path(mcd_buddy.__file__).resolve().parents[1]
        script = (
            "from mcd_buddy.modules.hidden_menu import recipe_code;"
            f"print(recipe_code({self.RECIPE!r}))"
        )
        codes = set()
        for seed in ("0", "1", "12345"):
            env = {
                **os.environ,
                "PYTHONHASHSEED": seed,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONPATH": str(src_dir),
            }
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                env=env,
                check=True,
            )
            codes.add(proc.stdout.strip())
        assert codes == {self.EXPECTED}, f"配方编号跨进程不稳定：{codes}"


class TestPresetSemantics:
    """预设配方必须「只在该动的轮次动手」——这些是真实数据上踩过的坑。"""

    def _changes(self, preset):
        out = run(HiddenMenuModule().run(DemoMCDClient(), DEMO_STORE.store_code, COMBO, preset))
        block = out.split("▍ 🔧 改配说明")[1].split("▍ 🍔 配方组成")[0]
        return [line for line in block.split("\n") if line.startswith("- ")]

    def test_清醒_only_touches_drink_round(self):
        # 咖啡因配方不应该去改汉堡 / 小食轮次
        changes = self._changes("清醒")
        assert changes
        assert all("饮料" in line or "饮品" in line for line in changes)

    def test_减脂_reduces_calories(self):
        out = run(HiddenMenuModule().run(DemoMCDClient(), DEMO_STORE.store_code, COMBO, "减脂"))
        assert "能量" in out
        # 变化列应出现负值
        energy_row = next(line for line in out.split("\n") if "🔥 能量" in line)
        assert "-" in energy_row.split("|")[-2]

    def test_解馋_increases_calories(self):
        out = run(HiddenMenuModule().run(DemoMCDClient(), DEMO_STORE.store_code, COMBO, "解馋"))
        energy_row = next(line for line in out.split("\n") if "🔥 能量" in line)
        assert "+" in energy_row.split("|")[-2]

    def test_增肌_increases_protein(self):
        out = run(HiddenMenuModule().run(DemoMCDClient(), DEMO_STORE.store_code, COMBO, "增肌"))
        protein_row = next(line for line in out.split("\n") if "💪 蛋白质" in line)
        assert "+" in protein_row.split("|")[-2]

    def test_unknown_nutrition_is_not_treated_as_zero(self):
        # 把某轮次的一个选项从营养表里「藏起来」，它就不该被当成 0 热量选中
        client = DemoMCDClient()
        original = client._h_list_nutrition_foods

        def hide_burger(_args):
            payload = original({})
            payload["data"] = "\n".join(
                line for line in payload["data"].split("\n") if "板烧鸡腿堡" not in line
            )
            return payload

        client._h_list_nutrition_foods = hide_burger
        out = run(HiddenMenuModule().run(client, DEMO_STORE.store_code, COMBO, "减脂"))
        # 麦辣鸡腿汉堡（485 kcal）仍在表里，所以减脂版不应退化成「没数据就算 0 卡」
        energy_row = next(line for line in out.split("\n") if "🔥 能量" in line)
        after = energy_row.split("|")[4]
        assert "0 kcal" not in after


class TestFortuneModule:
    def test_contains_sign(self, fortune_output):
        assert "麦门灵签" in fortune_output

    def test_contains_daily_guidance(self, fortune_output):
        assert "今日宜吃" in fortune_output and "抽奖吉时" in fortune_output

    def test_uses_real_lottery_fields(self, fortune_output):
        assert "周六麦金喜抽奖" in fortune_output

    def test_uses_real_calendar_fields(self, fortune_output):
        assert "今日活动" in fortune_output

    def test_deterministic_for_same_date(self, fortune_output):
        again = run(FortuneModule().run(DemoMCDClient()))
        assert fortune_output == again

    def test_cards_aligned(self, fortune_output):
        assert_cards_aligned(fortune_output)

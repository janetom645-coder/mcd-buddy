"""CLI 入口测试。"""

import json

import pytest

from mcd_buddy.cli import _load_people, build_parser, main
from mcd_buddy.mcd_api import MCDApiError


def test_practice_runs_in_demo_mode(capsys):
    assert main(["practice", "--demo"]) == 0
    assert "麦门修行录" in capsys.readouterr().out


def test_fortune_runs_in_demo_mode(capsys):
    assert main(["fortune", "--demo"]) == 0
    assert "麦门灵签" in capsys.readouterr().out


def test_group_meal_runs_in_demo_mode(capsys):
    assert main(["group-meal", "--demo"]) == 0
    assert "团餐指挥官" in capsys.readouterr().out


def test_hidden_menu_runs_in_demo_mode(capsys):
    assert main(["hidden-menu", "--meal", "双人分享餐", "--preset", "减脂", "--demo"]) == 0
    assert "隐藏菜单实验室" in capsys.readouterr().out


def test_hidden_menu_list_flag(capsys):
    assert main(["hidden-menu", "--list", "--demo"]) == 0
    out = capsys.readouterr().out
    assert "餐品" in out and "编码" in out


def test_json_flag_after_subcommand(capsys):
    assert main(["fortune", "--demo", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "fortune"
    assert payload["demo"] is True
    assert "now-time-info" in payload["tools"]
    assert payload["markdown"]


def test_json_flag_before_subcommand(capsys):
    assert main(["--json", "practice", "--demo"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "practice"


def test_json_records_raw_tool_payloads(capsys):
    assert main(["hidden-menu", "--meal", "双人分享餐", "--demo", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "query-meal-detail" in payload["tools"]
    assert "calculate-price" in payload["tools"]
    # 记录的必须是未拆信封的原始返回
    assert payload["tools"]["query-meal-detail"]["success"] is True


def test_tools_command_lists_mcp_tools(capsys):
    assert main(["tools", "--demo"]) == 0
    out = capsys.readouterr().out
    assert "now-time-info" in out and "query-meals" in out


def test_missing_token_reports_error(capsys, monkeypatch):
    monkeypatch.delenv("MCD_MCP_TOKEN", raising=False)
    assert main(["fortune"]) == 1
    assert "MCP Token" in capsys.readouterr().err


def test_group_meal_accepts_inline_json(capsys):
    people = '[{"name":"小明","budget":30,"want":"牛肉"}]'
    assert main(["group-meal", "--people", people, "--demo"]) == 0
    assert "小明" in capsys.readouterr().out


def test_store_options_available_on_all_subcommands():
    parser = build_parser()
    for command in ("practice", "fortune", "group-meal", "hidden-menu", "tools"):
        args = parser.parse_args([command, "--city", "北京市", "--keyword", "国贸", "--store", "123"])
        assert args.city == "北京市"
        assert args.keyword == "国贸"
        assert args.store == "123"


class TestPeopleParsing:
    """--people 的简写解析。

    这块以前只吃 JSON，用户写「阿May:25:不要辣」会直接抛
    JSONDecodeError 堆栈 —— 对命令行工具来说是硬伤。
    """

    def test_semicolon_separated_people(self):
        people = _load_people("阿May:25:不要辣;老王:40:要咖啡;小林:30")
        assert [p.name for p in people] == ["阿May", "老王", "小林"]
        assert people[0].budget == 25.0
        assert people[0].avoid == ["辣"]
        assert people[1].want == "咖啡"
        assert people[2].budget == 30.0

    def test_comma_separated_people(self):
        people = _load_people("阿May:预算25:不要辣,老王:预算40:要咖啡")
        assert [p.name for p in people] == ["阿May", "老王"]
        assert people[0].budget == 25.0
        assert people[1].want == "咖啡"

    def test_comma_inside_one_person_is_not_a_separator(self):
        """「不要辣,不要香菜」是同一个人，不该被拆成两个人。"""
        people = _load_people("阿May:25:不要辣,不要香菜")
        assert len(people) == 1
        assert people[0].name == "阿May"
        assert people[0].avoid == ["辣", "香菜"]

    def test_whitespace_separated_fields(self):
        people = _load_people("小明 预算30 不要冰")
        assert people[0].name == "小明"
        assert people[0].budget == 30.0
        assert people[0].avoid == ["冰"]

    def test_key_value_form(self):
        people = _load_people("name=小B;budget=35;want=咖啡;avoid=辣、冰")
        assert people[0].name == "小B"
        assert people[0].budget == 35.0
        assert people[0].want == "咖啡"
        assert people[0].avoid == ["辣", "冰"]

    def test_json_still_works(self):
        people = _load_people('[{"name":"小A","budget":20,"avoid":["辣"]}]')
        assert people[0].name == "小A"
        assert people[0].avoid == ["辣"]

    def test_json_object_with_people_key(self):
        people = _load_people('{"people":[{"name":"小C","budget":18}]}')
        assert people[0].name == "小C"

    def test_yuan_symbol_in_budget(self):
        assert _load_people("阿May:¥25")[0].budget == 25.0

    def test_broken_json_gives_friendly_error(self):
        with pytest.raises(MCDApiError) as exc:
            _load_people('[{"name": 小A}]')
        assert "JSON" in str(exc.value)
        assert "用法" in str(exc.value)

    def test_missing_name_gives_friendly_error(self):
        with pytest.raises(MCDApiError) as exc:
            _load_people("预算25:不要辣")
        assert "没解析出名字" in str(exc.value)

    def test_empty_input_gives_friendly_error(self):
        with pytest.raises(MCDApiError):
            _load_people("   ")

    def test_missing_file_gives_friendly_error(self):
        with pytest.raises(MCDApiError) as exc:
            _load_people("@不存在的文件.json")
        assert "读不到文件" in str(exc.value)

    def test_cli_reports_bad_people_without_traceback(self, capsys):
        """CLI 层必须给出可读错误，而不是把堆栈甩给用户。"""
        assert main(["group-meal", "--people", "预算25", "--demo"]) == 1
        err = capsys.readouterr().err
        assert "❌" in err
        assert "Traceback" not in err

    def test_cli_accepts_friendly_people(self, capsys):
        assert main(["group-meal", "--people", "阿May:25:不要辣;老王:40", "--demo"]) == 0
        out = capsys.readouterr().out
        assert "阿May" in out and "老王" in out

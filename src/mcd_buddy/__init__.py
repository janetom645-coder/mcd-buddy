"""麦门四重奏 McQuartet —— 基于麦当劳中国 MCP 的多玩法 AI 助手。

四大模块：
  - practice    修行录：点餐即打卡，解锁成就与段位
  - group_meal  团餐指挥官：多人点单自动凑最优团餐
  - hidden_menu 隐藏菜单实验室：重组套餐生成可分享配方卡
  - fortune     每日运势签：今天宜吃啥 + 抽奖吉时

本包通过 MCP（Model Context Protocol）协议调用麦当劳中国官方 MCP 服务，
接入地址 https://mcp.mcd.cn 。
"""

__version__ = "0.1.0"
__all__ = ["__version__"]

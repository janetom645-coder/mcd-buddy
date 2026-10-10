"""麦门助手四大功能模块。"""

from .fortune import FortuneModule
from .group_meal import GroupMealModule
from .hidden_menu import HiddenMenuModule
from .practice import PracticeModule

__all__ = [
    "PracticeModule",
    "GroupMealModule",
    "HiddenMenuModule",
    "FortuneModule",
]

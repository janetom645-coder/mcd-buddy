"""pytest 公共配置：把 src 加入路径，并固定输出为无色模式。"""

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

# 测试断言依赖纯文本输出，强制关闭 ANSI 颜色
os.environ["NO_COLOR"] = "1"

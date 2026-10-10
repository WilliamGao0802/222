"""core —— 纯 Python 业务逻辑层。

铁律：本包内任何模块都**不得** import streamlit。
UI 只通过 core 暴露的纯函数读写数据，因此同一套逻辑可被
Streamlit 版、桌面版、未来的 HTTP API 复用，并且可以离线单测。
"""

from . import config  # noqa: F401

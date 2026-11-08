# -*- coding: utf-8 -*-
"""主题系统：深色/浅色双调色板 + 参数化 QSS。

用法：
- theme.set_theme('light') 会更新模块级颜色常量（theme.ACCENT 等），
  自绘控件随后调用 self.update() 即可用新色重绘；
- QApplication 需要重新 setPalette(build_palette()) + setStyleSheet(build_qss())。
"""
import os

from PySide6.QtGui import QColor

# ---------- 调色板定义 ----------
DARK = {
    "NAME": "dark",
    "BG": "#171a21",           # 窗口底
    "BG_SIDEBAR": "#1f232d",   # 侧栏
    "CARD": "#232833",         # 卡片
    "CARD_2": "#2c313d",       # 卡片内嵌/描边
    "BORDER": "#363c4a",
    "TEXT": "#e6e9ef",
    "TEXT_DIM": "#9aa3b2",
    "ACCENT": "#6fcf7c",       # 主题绿（树）
    "ACCENT_DIM": "#4f9e5b",
    "GOLD": "#e8a33d",         # 金币
    "DANGER": "#e06c5f",
    "FOCUS_COLOR": "#e06c5f",      # 专注阶段（番茄红）
    "SHORT_BREAK_COLOR": "#6fcf7c",
    "LONG_BREAK_COLOR": "#5aa7e0",
    "BAR": "#4b5468",          # 普通柱/次要条
    "OVERLAY": (23, 26, 33, 236),  # 迷你窗半透明卡
    "TRACK": "#2c313d",        # 进度环底环
}

LIGHT = {
    "NAME": "light",
    "BG": "#f4f6fa",
    "BG_SIDEBAR": "#ffffff",
    "CARD": "#ffffff",
    "CARD_2": "#eef1f6",
    "BORDER": "#dfe4ec",
    "TEXT": "#22272e",
    "TEXT_DIM": "#68707c",
    "ACCENT": "#3f9d5a",
    "ACCENT_DIM": "#33804a",
    "GOLD": "#d99a2b",
    "DANGER": "#d9534f",
    "FOCUS_COLOR": "#d9534f",
    "SHORT_BREAK_COLOR": "#3f9d5a",
    "LONG_BREAK_COLOR": "#3d84c6",
    "BAR": "#c3cad6",
    "OVERLAY": (255, 255, 255, 242),
    "TRACK": "#e2e7ee",
}

PALETTES = {"dark": DARK, "light": LIGHT}

# 当前生效的调色板：模块级常量直接来自它（set_theme 时整体替换）
P = dict(DARK)
globals().update(P)

PHASE_COLORS = {
    "focus": FOCUS_COLOR,
    "short_break": SHORT_BREAK_COLOR,
    "long_break": LONG_BREAK_COLOR,
    "stopwatch": GOLD,
}


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def set_theme(name: str) -> None:
    """切换主题：更新模块级颜色常量（自绘控件随后 update() 即可）。"""
    global P, PHASE_COLORS
    P = dict(PALETTES.get(name, DARK))
    globals().update(P)
    PHASE_COLORS = {
        "focus": P["FOCUS_COLOR"],
        "short_break": P["SHORT_BREAK_COLOR"],
        "long_break": P["LONG_BREAK_COLOR"],
        "stopwatch": P["GOLD"],
    }
    globals()["PHASE_COLORS"] = PHASE_COLORS


# 项目根（开发时=仓库根；PyInstaller 打包后 _MEIPASS 下同样有 app/ 与 assets/）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK_ICON = os.path.join(_PROJECT_ROOT, "assets", "check.png")


def build_palette():
    """与调色板同步的 QPalette：兜底所有未被 QSS 覆盖的原生部件（托盘菜单等）。"""
    from PySide6.QtGui import QColor, QPalette
    p = QPalette()
    p.setColor(QPalette.Window, QColor(P["BG"]))
    p.setColor(QPalette.WindowText, QColor(P["TEXT"]))
    p.setColor(QPalette.Base, QColor(P["CARD"]))
    p.setColor(QPalette.AlternateBase, QColor(P["CARD_2"]))
    p.setColor(QPalette.Text, QColor(P["TEXT"]))
    p.setColor(QPalette.Button, QColor(P["CARD"]))
    p.setColor(QPalette.ButtonText, QColor(P["TEXT"]))
    p.setColor(QPalette.Highlight, QColor(P["ACCENT"]))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ToolTipBase, QColor(P["CARD_2"]))
    p.setColor(QPalette.ToolTipText, QColor(P["TEXT"]))
    p.setColor(QPalette.PlaceholderText, QColor(P["TEXT_DIM"]))
    p.setColor(QPalette.BrightText, QColor(P["DANGER"]))
    p.setColor(QPalette.Link, QColor(P["LONG_BREAK_COLOR"]))
    return p


def build_qss() -> str:
    """根据当前调色板生成 QSS。切换主题后需重新调用。"""
    p = P
    return f"""
* {{
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
    color: {p['TEXT']};
}}
QMainWindow, QDialog {{ background: {p['BG']}; }}
QWidget#sidebar {{ background: {p['BG_SIDEBAR']}; }}
QFrame#card {{
    background: {p['CARD']}; border-radius: 12px;
    border: 1px solid {_rgba(p['BORDER'], 0.7)};
}}
QFrame#stat_card {{
    background: {p['CARD']}; border-radius: 12px;
    border: 1px solid {_rgba(p['BORDER'], 0.7)};
}}
QLabel#title {{ font-size: 17px; font-weight: bold; }}
QLabel#muted, QLabel#muted2 {{ color: {p['TEXT_DIM']}; }}
QLabel#muted2 {{ font-size: 12px; }}
QLabel#h1 {{ font-size: 26px; font-weight: bold; }}
QLabel#h2 {{ font-size: 20px; font-weight: bold; }}

QPushButton {{
    background: {p['CARD_2']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: {p['BORDER']}; }}
QPushButton:pressed {{ background: {p['BORDER']}; padding-top: 8px; padding-bottom: 6px; }}
QPushButton:disabled {{ color: {p['TEXT_DIM']}; background: {p['CARD']}; }}
QPushButton#primary {{
    background: {p['ACCENT']}; border: none; color: #ffffff; font-weight: bold;
}}
QPushButton#primary:hover {{ background: {p['ACCENT_DIM']}; }}
QPushButton#danger {{
    background: transparent; border: 1px solid {p['DANGER']}; color: {p['DANGER']};
}}
QPushButton#danger:hover {{ background: {_rgba(p['DANGER'], 0.15)}; }}
QPushButton#nav {{
    background: transparent; border: none; border-radius: 10px;
    padding: 12px 14px; text-align: left; font-size: 14px; color: {p['TEXT_DIM']};
}}
QPushButton#nav:hover {{ background: {_rgba(p['TEXT_DIM'], 0.12)}; color: {p['TEXT']}; }}
QPushButton#nav:checked {{
    background: {_rgba(p['ACCENT'], 0.16)}; color: {p['ACCENT']}; font-weight: bold;
    border-left: 3px solid {p['ACCENT']}; padding-left: 11px;
}}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateTimeEdit {{
    background: {p['CARD']}; border: 1px solid {p['BORDER']}; border-radius: 8px;
    padding: 6px 10px; selection-background-color: {p['ACCENT_DIM']};
    color: {p['TEXT']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDateTimeEdit:focus {{
    border-color: {p['ACCENT']};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {p['CARD']}; border: 1px solid {p['BORDER']};
    selection-background-color: {p['ACCENT_DIM']}; color: {p['TEXT']};
}}

QListWidget {{
    background: {p['CARD']}; border-radius: 10px; border: none; padding: 4px;
    color: {p['TEXT']};
}}
QListWidget::item {{ padding: 2px; border-radius: 8px; }}
QListWidget::item:selected {{ background: {p['CARD_2']}; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 17px; height: 17px; border-radius: 5px;
    border: 1px solid {p['BORDER']}; background: {p['CARD_2']};
}}
QCheckBox::indicator:hover {{ border-color: {p['ACCENT']}; }}
QCheckBox::indicator:checked {{
    background: {p['ACCENT']}; border-color: {p['ACCENT']};
    image: url({CHECK_ICON.replace(chr(92), '/')});
}}

QSlider::groove:horizontal {{
    height: 6px; border-radius: 3px; background: {p['CARD_2']};
}}
QSlider::handle:horizontal {{
    width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
    background: {p['ACCENT']};
}}
QSlider::sub-page:horizontal {{ background: {_rgba(p['ACCENT'], 0.5)}; border-radius: 3px; }}

QTabWidget::pane {{ border: none; background: transparent; top: -1px; }}
QTabBar::tab {{
    background: {p['CARD']}; color: {p['TEXT_DIM']};
    padding: 7px 22px; margin-right: 6px;
    border: 1px solid {p['BORDER']}; border-bottom: none;
    border-top-left-radius: 8px; border-top-right-radius: 8px;
}}
QTabBar::tab:selected {{
    background: {p['CARD_2']}; color: {p['ACCENT']}; font-weight: bold;
}}
QTabBar::tab:hover:!selected {{ background: {p['CARD_2']}; }}

QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {p['BORDER']}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {p['TEXT_DIM']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {p['BORDER']}; border-radius: 4px; min-width: 30px;
}}

QMessageBox {{ background: {p['BG_SIDEBAR']}; }}

QMenu {{
    background: {p['CARD']}; color: {p['TEXT']};
    border: 1px solid {p['BORDER']}; border-radius: 10px; padding: 6px;
}}
QMenu::item {{
    padding: 8px 26px 8px 14px; border-radius: 6px; background: transparent;
}}
QMenu::item:selected {{ background: {_rgba(p['ACCENT'], 0.16)}; color: {p['ACCENT']}; }}
QMenu::item:pressed {{ background: {_rgba(p['ACCENT'], 0.3)}; }}
QMenu::separator {{ height: 1px; background: {p['BORDER']}; margin: 6px 10px; }}
QMenu::icon {{ padding-left: 10px; }}
QMenuBar {{ background: {p['BG_SIDEBAR']}; color: {p['TEXT']}; }}
QMenuBar::item:selected {{ background: {_rgba(p['ACCENT'], 0.16)}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

QToolTip {{
    background: {p['CARD_2']}; color: {p['TEXT']}; border: 1px solid {p['BORDER']};
    padding: 4px 8px; border-radius: 6px;
}}
"""


# 兼容旧引用：导入即可用 theme.QSS（初始为深色）；切主题后用 build_qss()
QSS = build_qss()

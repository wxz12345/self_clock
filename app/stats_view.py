# -*- coding: utf-8 -*-
"""统计页：概览（卡片+30天柱状图+分心原因+应用使用+分类分布）、周趋势（含热力图）、周回顾。"""
import math
from datetime import date, timedelta

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QScrollArea, QTabWidget, QToolTip,
                               QVBoxLayout, QWidget)

from core import gamify

from . import theme

WEEKDAY_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _fmt_minutes(minutes: float) -> str:
    total = int(minutes)
    return f"{total // 60}h {total % 60:02d}m" if total >= 60 else f"{total} 分钟"


class _StatCard(QFrame):
    def __init__(self, caption: str):
        super().__init__()
        self.setObjectName("stat_card")
        # 注意：滚动容器内不要挂 QGraphicsDropShadowEffect（滚动重绘会撕裂），
        # 立体感由 QSS 细边框提供
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(4)
        self.value_label = QLabel("–")
        self.value_label.setObjectName("h1")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName("muted")
        self.caption_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)
        layout.addWidget(self.caption_label)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)


class BarChart(QWidget):
    """柱状图：Y 轴刻度 + 悬浮提示，可由日数据（近 N 天）或现成序列驱动。"""

    def __init__(self, tooltip_fmt=None):
        super().__init__()
        self._series: list[tuple[str, float, str]] = []  # (label, value, key)
        self._highlight_key: str | None = None
        self._tooltip_fmt = tooltip_fmt or (lambda v: f"{v:.0f} 分钟")
        self._hover_idx = -1
        self.setMinimumHeight(180)
        self.setMouseTracking(True)

    def set_data(self, daily: dict[str, float], days: int = 30) -> None:
        today = date.today()
        series = []
        for i in range(days - 1, -1, -1):
            day = today - timedelta(days=i)
            key = day.isoformat()
            series.append((day.strftime("%m-%d"), daily.get(key, 0.0), key))
        self.set_series(series, highlight_key=today.isoformat())

    def set_series(self, series: list[tuple[str, float, str]],
                   highlight_key: str | None = None) -> None:
        self._series = series
        self._highlight_key = highlight_key
        self.update()

    # ---------- 几何（绘制与命中检测共用） ----------
    def _plot_geometry(self):
        w, h = self.width(), self.height()
        left, right, top, bottom = 46, 8, 14, 24
        return w, h, left, right, top, bottom

    def _bar_rect(self, i: int, n: int, plot_w: int, plot_h: int,
                  left: int, h: int, bottom: int):
        max_val = max((v for _, v, _ in self._series), default=0) or 1
        gap = 4 if n > 15 else 10
        bar_w = max(3.0, (plot_w - gap * (n - 1)) / n)
        value = self._series[i][1]
        bar_h = (value / max_val) * (plot_h - 10) if value else 0
        x = left + i * (bar_w + gap)
        return QRectF(x, h - bottom - bar_h, bar_w, max(bar_h, 2))

    def _nice_max(self, max_val: float) -> float:
        if max_val <= 0:
            return 1.0
        step = 10 ** math.floor(math.log10(max_val / 4))
        return math.ceil(max_val / 4 / step) * 4 * step

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, left, right, top, bottom = self._plot_geometry()
        plot_w, plot_h = w - left - right, h - top - bottom

        if not self._series:
            p.setPen(QPen(QColor(theme.BORDER), 1))
            p.drawLine(left, int(h - bottom), w - right, int(h - bottom))
            p.setPen(QColor(theme.TEXT_DIM))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "暂无数据")
            p.end()
            return
        n = len(self._series)
        max_val = self._nice_max(max((v for _, v, _ in self._series), default=0))

        # Y 轴网格与刻度（4 段）
        p.setFont(QFont())
        for i in range(4, -1, -1):
            value = max_val * i / 4
            y = h - bottom - (value / max_val) * (plot_h - 10)
            p.setPen(QPen(QColor(theme.BORDER), 1, Qt.DotLine))
            p.drawLine(left, int(y), w - right, int(y))
            p.setPen(QColor(theme.TEXT_DIM))
            p.drawText(QRectF(0, y - 8, left - 6, 16),
                       Qt.AlignVCenter | Qt.AlignRight, self._y_label(value))

        # 基线
        p.setPen(QPen(QColor(theme.BORDER), 1))
        p.drawLine(left, h - bottom, w - right, h - bottom)

        p.setPen(Qt.NoPen)
        for i, (label, value, key) in enumerate(self._series):
            rect = self._bar_rect(i, n, plot_w, plot_h, left, h, bottom)
            highlighted = (self._highlight_key is not None
                           and key == self._highlight_key)
            hovered = i == self._hover_idx
            color = QColor(theme.ACCENT if highlighted else theme.BAR)
            if hovered and not highlighted:
                color = QColor(theme.ACCENT).lighter(115)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(rect, 2, 2)
            if n <= 15 or i % 5 == 0 or highlighted:
                p.setPen(QColor(theme.TEXT_DIM))
                p.drawText(QRectF(rect.x() - 14, h - bottom + 4,
                                  rect.width() + 28, 16),
                           Qt.AlignCenter, label)

        # 悬浮柱子的数值标签（直接画在柱子上方，无系统 tooltip 延迟）
        if 0 <= self._hover_idx < len(self._series):
            _, value, _ = self._series[self._hover_idx]
            rect = self._bar_rect(self._hover_idx, n, plot_w, plot_h,
                                  left, h, bottom)
            p.setPen(QColor(theme.TEXT))
            p.drawText(QRectF(rect.x() - 34, rect.top() - 22,
                              rect.width() + 68, 18),
                       Qt.AlignHCenter | Qt.AlignVCenter,
                       self._tooltip_fmt(value))
        p.end()

    def _y_label(self, value: float) -> str:
        if value >= 60 and value % 60 == 0 and value >= 120:
            return f"{int(value // 60)}h"
        if value == int(value):
            return f"{int(value)}"
        return f"{value:.0f}"

    # ---------- 悬浮（只在柱子上显示数值） ----------
    def mouseMoveEvent(self, event) -> None:
        idx = self._hit_bar(event.position().toPoint())
        if idx != self._hover_idx:
            self._hover_idx = idx
            self.update()

    def leaveEvent(self, event) -> None:
        self._hover_idx = -1
        self.update()

    def _hit_bar(self, pos) -> int:
        if not self._series:
            return -1
        w, h, left, right, top, bottom = self._plot_geometry()
        n = len(self._series)
        plot_w = w - left - right
        for i in range(n):
            rect = self._bar_rect(i, n, plot_w, h - top - bottom, left, h, bottom)
            # 只命中柱子本身：横向外扩 3px，纵向从柱顶延伸到基线
            bar_top = min(rect.top(), h - bottom - 2)
            hit = QRectF(rect.x() - 3, bar_top, rect.width() + 6,
                         h - bottom - bar_top)
            if hit.contains(pos):
                return i
        return -1


class ReasonBars(QWidget):
    """横向条形排行（分心原因 / 应用使用）：悬浮显示明细。"""

    PALETTE = ["#e06c5f", "#e8a33d", "#5aa7e0", "#6fcf7c", "#b58ee0", "#e07aa8"]

    def __init__(self, empty_text: str = "还没有分心记录——继续保持 🎉",
                 value_fmt=None):
        super().__init__()
        self._rows: list[tuple[str, float, float]] = []  # (label, value, pct)
        self._empty_text = empty_text
        self._value_fmt = value_fmt or (lambda v: f"{v:.0f} 次")
        self._hover_idx = -1
        self.setMinimumHeight(120)
        self.setMouseTracking(True)

    def set_rows(self, counts: list[tuple[str, float]]) -> None:
        total = sum(v for _, v in counts) or 1
        self._rows = [(label, v, v / total) for label, v in counts]
        self.setMinimumHeight(max(60, 34 * len(self._rows)))
        self._hover_idx = -1
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if not self._rows:
            p.setPen(QColor(theme.TEXT_DIM))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, self._empty_text)
            p.end()
            return
        row_h = h / len(self._rows)
        label_w = min(150.0, w * 0.3)
        bar_x = label_w + 8
        bar_w_max = w - bar_x - 110
        for i, (label, value, pct) in enumerate(self._rows):
            cy = i * row_h + row_h / 2
            p.setPen(QColor(theme.TEXT))
            p.drawText(QRectF(0, cy - row_h / 2, label_w, row_h),
                       Qt.AlignVCenter | Qt.AlignLeft, label)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(theme.CARD_2)))
            p.drawRoundedRect(QRectF(bar_x, cy - 7, bar_w_max, 14), 7, 7)
            color = QColor(self.PALETTE[i % len(self.PALETTE)])
            if i == self._hover_idx:
                color = color.lighter(130)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(
                QRectF(bar_x, cy - 7, max(10, bar_w_max * pct), 14), 7, 7)
            p.setPen(QColor(theme.TEXT_DIM))
            p.drawText(QRectF(bar_x + bar_w_max + 8, cy - row_h / 2, 100, row_h),
                       Qt.AlignVCenter | Qt.AlignLeft,
                       f"{self._value_fmt(value)} · {pct:.0%}")
        p.end()

    # ---------- 悬浮 ----------
    def mouseMoveEvent(self, event) -> None:
        y = event.position().y()
        idx = -1
        if self._rows:
            row_h = self.height() / len(self._rows)
            idx = min(int(y / row_h), len(self._rows) - 1)
        if idx != self._hover_idx:
            self._hover_idx = idx
            self.update()
        if 0 <= idx < len(self._rows):
            label, value, pct = self._rows[idx]
            QToolTip.showText(event.globalPosition().toPoint(),
                              f"{label}: {self._value_fmt(value)}（{pct:.0%}）",
                              self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, event) -> None:
        self._hover_idx = -1
        QToolTip.hideText()
        self.update()


class Heatmap(QWidget):
    """专注时段热力图：星期 × 小时，颜色深浅 = 专注分钟。"""

    def __init__(self):
        super().__init__()
        self._data: dict[tuple[int, int], float] = {}
        self._max_val = 0.0
        self.setMinimumHeight(190)
        self.setMouseTracking(True)

    def set_rows(self, rows: list[tuple[int, int, float]]) -> None:
        self._data = {(wd, hr): m for wd, hr, m in rows}
        self._max_val = max((m for _, _, m in rows), default=0.0) or 1.0
        self.update()

    def _geometry(self):
        w, h = self.width(), self.height()
        left, top, bottom = 40, 6, 20
        cw = (w - left - 8) / 24
        ch = (h - top - bottom) / 7
        return w, h, left, top, bottom, cw, ch

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h, left, top, bottom, cw, ch = self._geometry()
        small = QFont()
        small.setPixelSize(11)
        p.setFont(small)
        base = QColor(theme.CARD_2)
        peak = QColor(theme.ACCENT)
        for wd in range(7):
            y = top + wd * ch
            p.setPen(QColor(theme.TEXT_DIM))
            p.drawText(QRectF(0, y, left - 6, ch), Qt.AlignVCenter | Qt.AlignRight,
                       WEEKDAY_NAMES[wd])
            for hr in range(24):
                minutes = self._data.get((wd, hr), 0.0)
                if minutes > 0:
                    t = min(1.0, math.sqrt(minutes / self._max_val))
                    color = QColor(
                        int(base.red() + (peak.red() - base.red()) * t),
                        int(base.green() + (peak.green() - base.green()) * t),
                        int(base.blue() + (peak.blue() - base.blue()) * t))
                else:
                    color = base
                p.setPen(Qt.NoPen)
                p.setBrush(QBrush(color))
                rect = QRectF(left + hr * cw + 1, y + 1, cw - 2, ch - 2)
                p.drawRoundedRect(rect, 2, 2)
        p.setPen(QColor(theme.TEXT_DIM))
        for hr in (0, 6, 12, 18):
            x = left + hr * cw
            p.drawText(QRectF(x - 10, h - bottom + 2, cw + 20, 16),
                       Qt.AlignCenter, f"{hr}时")
        p.end()

    # ---------- 悬浮 ----------
    def mouseMoveEvent(self, event) -> None:
        w, h, left, top, bottom, cw, ch = self._geometry()
        pos = event.position()
        hr = int((pos.x() - left) / cw)
        wd = int((pos.y() - top) / ch)
        if 0 <= hr < 24 and 0 <= wd < 7:
            minutes = self._data.get((wd, hr), 0.0)
            tip = (f"{WEEKDAY_NAMES[wd]} {hr}时: {_fmt_minutes(minutes)}"
                   if minutes else f"{WEEKDAY_NAMES[wd]} {hr}时: 无记录")
            QToolTip.showText(event.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, event) -> None:
        QToolTip.hideText()


class StatsView(QWidget):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        title = QLabel("统计")
        title.setObjectName("title")
        root.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._scrollable(self._build_overview_tab()), "概览")
        self.tabs.addTab(self._scrollable(self._build_weekly_tab()), "周趋势")
        self.tabs.addTab(self._scrollable(self._build_review_tab()), "周回顾")
        root.addWidget(self.tabs, stretch=1)

    @staticmethod
    def _scrollable(page: QWidget) -> QWidget:
        """内容超出可视高度时可滚动，不再挤压图表。"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(page)
        return scroll

    # ---------- 概览 ----------
    def _card(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        return frame

    # ---------- 概览 ----------
    def _build_overview_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.card_today_focus = _StatCard("今日专注")
        self.card_today_pomo = _StatCard("今日番茄")
        self.card_total_pomo = _StatCard("累计番茄")
        self.card_rate = _StatCard("完成率")
        for c in (self.card_today_focus, self.card_today_pomo,
                  self.card_total_pomo, self.card_rate):
            cards.addWidget(c)
        layout.addLayout(cards)

        chart_card = self._card()
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(16, 12, 16, 10)
        chart_title = QLabel("近 30 天专注分钟")
        chart_title.setObjectName("muted")
        chart_layout.addWidget(chart_title)
        self.bar_chart = BarChart()
        chart_layout.addWidget(self.bar_chart, stretch=1)
        layout.addWidget(chart_card, stretch=1)

        reason_card = self._card()
        reason_layout = QVBoxLayout(reason_card)
        reason_layout.setContentsMargins(16, 12, 16, 10)
        reason_title = QLabel("分心原因排行（近 30 天）")
        reason_title.setObjectName("muted")
        reason_layout.addWidget(reason_title)
        self.reason_bars = ReasonBars()
        reason_layout.addWidget(self.reason_bars, stretch=1)
        layout.addWidget(reason_card, stretch=1)

        app_card = self._card()
        app_layout = QVBoxLayout(app_card)
        app_layout.setContentsMargins(16, 12, 16, 10)
        app_title = QLabel("专注期间应用使用 Top 8（近 30 天，按前台窗口时长统计）")
        app_title.setObjectName("muted")
        app_layout.addWidget(app_title)
        self.app_bars = ReasonBars(
            empty_text="还没有记录——完成一次专注就会看到你的时间去哪儿了",
            value_fmt=lambda v: f"{int(round(v))} 分钟")
        app_layout.addWidget(self.app_bars, stretch=1)
        layout.addWidget(app_card, stretch=1)

        category_card = self._card()
        category_layout = QVBoxLayout(category_card)
        category_layout.setContentsMargins(16, 12, 16, 10)
        category_title = QLabel("计时分类分布（近 30 天专注分钟）")
        category_title.setObjectName("muted")
        category_layout.addWidget(category_title)
        self.category_bars = ReasonBars(
            empty_text="还没有记录——开始专注时选一个分类试试",
            value_fmt=_fmt_minutes)
        category_layout.addWidget(self.category_bars, stretch=1)
        layout.addWidget(category_card, stretch=1)
        return page

    # ---------- 周趋势 ----------
    def _build_weekly_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.card_week_now = _StatCard("本周专注（进行中）")
        self.card_week_prev = _StatCard("上周专注")
        self.card_week_avg = _StatCard("周平均")
        for c in (self.card_week_now, self.card_week_prev, self.card_week_avg):
            cards.addWidget(c)
        layout.addLayout(cards)

        self.week_compare = QLabel("")
        self.week_compare.setObjectName("muted")
        self.week_compare.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.week_compare)

        chart_card = self._card()
        chart_layout = QVBoxLayout(chart_card)
        chart_layout.setContentsMargins(16, 12, 16, 10)
        chart_title = QLabel("近 8 周每周专注小时（横轴为周一起始日期）")
        chart_title.setObjectName("muted")
        chart_layout.addWidget(chart_title)
        self.week_chart = BarChart(tooltip_fmt=_fmt_minutes)
        chart_layout.addWidget(self.week_chart, stretch=1)
        layout.addWidget(chart_card, stretch=1)

        heat_card = self._card()
        heat_layout = QVBoxLayout(heat_card)
        heat_layout.setContentsMargins(16, 12, 16, 10)
        heat_title = QLabel("专注时段热力图（近 90 天，星期 × 小时，颜色越深专注越久）")
        heat_title.setObjectName("muted")
        heat_layout.addWidget(heat_title)
        self.heatmap = Heatmap()
        heat_layout.addWidget(self.heatmap, stretch=1)
        layout.addWidget(heat_card, stretch=1)
        return page

    # ---------- 周回顾 ----------
    def _build_review_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(16)

        self.review_summary = QLabel("")
        self.review_summary.setObjectName("h2")
        self.review_summary.setAlignment(Qt.AlignCenter)
        self.review_summary.setWordWrap(True)
        layout.addWidget(self.review_summary)

        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.card_week_total = _StatCard("本周专注")
        self.card_week_daily = _StatCard("日均专注")
        self.card_week_best = _StatCard("最佳专注日")
        self.card_week_streak = _StatCard("连续达标")
        for c in (self.card_week_total, self.card_week_daily,
                  self.card_week_best, self.card_week_streak):
            cards.addWidget(c)
        layout.addLayout(cards)

        detail_card = self._card()
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(16, 12, 16, 10)
        detail_title = QLabel("本周分心原因与计时分类")
        detail_title.setObjectName("muted")
        detail_layout.addWidget(detail_title)
        self.review_distraction = ReasonBars(
            empty_text="本周没有分心记录——太棒了 🎉")
        detail_layout.addWidget(self.review_distraction, stretch=1)
        self.review_category = ReasonBars(
            empty_text="本周还没有分类记录",
            value_fmt=_fmt_minutes)
        detail_layout.addWidget(self.review_category, stretch=1)
        layout.addWidget(detail_card, stretch=1)
        layout.addStretch(1)
        return page

    # ---------- 数据 ----------
    def _weekly_minutes(self, daily: dict[str, float]) -> tuple[list, list]:
        """返回 (8 周序列 [(label, minutes, week_start_iso)], 逐周分钟列表)。"""
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        series = []
        for i in range(7, -1, -1):
            start = monday - timedelta(weeks=i)
            total = sum(daily.get((start + timedelta(days=d)).isoformat(), 0.0)
                        for d in range(7))
            series.append((start.strftime("%m-%d"), total, start.isoformat()))
        return series

    def refresh(self) -> None:
        # 概览
        today_m, total_m, rate = self._store.focus_summary()
        self.card_today_focus.set_value(_fmt_minutes(today_m))
        self.card_today_pomo.set_value(f"{self._store.today_pomodoros()}")
        self.card_total_pomo.set_value(f"{self._store.total_pomodoros()}")
        self.card_rate.set_value(f"{rate:.0%}")
        daily = dict(self._store.daily_focus_minutes(60))
        self.bar_chart.set_data(daily, 30)
        self.reason_bars.set_rows(
            [(r["reason"], r["n"])
             for r in self._store.distraction_reason_counts(30)])
        # 应用使用：秒 -> 分钟
        self.app_bars.set_rows(
            [(r["process"], r["s"] / 60.0)
             for r in self._store.top_app_usage(30, 8)])
        # 分类分布
        self.category_bars.set_rows(
            [(r["cat"], r["m"]) for r in self._store.category_minutes(30)])
        # 热力图
        self.heatmap.set_rows(self._store.weekday_hour_minutes(90))
        # 周趋势
        series = self._weekly_minutes(daily)
        self.week_chart.set_series(series,
                                   highlight_key=series[-1][2] if series else None)
        now = series[-1][1]
        prev = series[-2][1] if len(series) >= 2 else 0.0
        self.card_week_now.set_value(_fmt_minutes(now))
        self.card_week_prev.set_value(_fmt_minutes(prev))
        finished_weeks = [v for _, v, k in series[:-1] if v > 0]
        avg = sum(finished_weeks) / len(finished_weeks) if finished_weeks else 0.0
        self.card_week_avg.set_value(_fmt_minutes(avg))
        if prev > 0:
            delta = (now - prev) / prev
            arrow = "↑" if delta >= 0 else "↓"
            color = theme.ACCENT if delta >= 0 else theme.DANGER
            self.week_compare.setText(
                f"本周比上周{'多' if delta >= 0 else '少'}专注了 "
                f"{_fmt_minutes(abs(now - prev))}（{arrow} {abs(delta):.0%}）")
            self.week_compare.setStyleSheet(f"color: {color};")
        elif now > 0:
            self.week_compare.setText("上周没有记录——这周已经开个好头了")
            self.week_compare.setStyleSheet("")
        else:
            self.week_compare.setText("还没有足够数据，先专注一个番茄吧")
            self.week_compare.setStyleSheet("")
        self._refresh_review(daily)

    def _refresh_review(self, daily: dict[str, float]) -> None:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        elapsed_days = (today - monday).days + 1
        week_total = sum(
            daily.get((monday + timedelta(days=i)).isoformat(), 0.0)
            for i in range(7))
        prev_monday = monday - timedelta(weeks=1)
        prev_total = sum(
            daily.get((prev_monday + timedelta(days=i)).isoformat(), 0.0)
            for i in range(elapsed_days))
        self.card_week_total.set_value(_fmt_minutes(week_total))
        self.card_week_daily.set_value(_fmt_minutes(week_total / elapsed_days))
        best = self._store.best_focus_day(7)
        self.card_week_best.set_value(
            _fmt_minutes(best["m"]) if best else "–")
        streak = gamify.streak(self._store.daily_pomodoros(400),
                               self._store.get_int("daily_goal", 6))
        self.card_week_streak.set_value(f"{streak} 天")

        if prev_total > 0:
            delta = (week_total - prev_total) / prev_total
            arrow = "↑" if delta >= 0 else "↓"
            self.review_summary.setText(
                f"本周已专注 {_fmt_minutes(week_total)}"
                f"（日均 {_fmt_minutes(week_total / elapsed_days)}），"
                f"比上周同期{'多' if delta >= 0 else '少'} "
                f"{_fmt_minutes(abs(week_total - prev_total))}（{arrow} {abs(delta):.0%}）")
        elif week_total > 0:
            self.review_summary.setText(
                f"本周已专注 {_fmt_minutes(week_total)}"
                f"（日均 {_fmt_minutes(week_total / elapsed_days)}）——继续保持！")
        else:
            self.review_summary.setText("本周还没有专注记录，从一个番茄开始吧 🍅")
        self.review_distraction.set_rows(
            [(r["reason"], r["n"])
             for r in self._store.distraction_reason_counts(7)])
        self.review_category.set_rows(
            [(r["cat"], r["m"]) for r in self._store.category_minutes(7)])

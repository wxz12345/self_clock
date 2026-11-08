# -*- coding: utf-8 -*-
"""main_window 接线补丁：迷你窗双窗口结构。"""
path = "app/main_window.py"
src = open(path, encoding="utf-8").read()
n0 = len(src)

# 1) 导入 MiniControls
src = src.replace(
    "from .mini_overlay import MiniOverlay",
    "from .mini_overlay import MiniControls, MiniOverlay")

# 2) 初始化：overlay + controls 双窗口
src = src.replace(
    """        self._really_quit = False
        self.overlay: MiniOverlay | None = None""",
    """        self._really_quit = False
        self.overlay: MiniOverlay | None = None
        self.mini_controls: MiniControls | None = None""")

# 3) _toggle_mini 重写（双窗口显示/隐藏 + 位置联动）
old_toggle = '''    def _toggle_mini(self) -> None:
        if self.overlay is None:
            self.overlay = MiniOverlay()
            self.overlay.drag_finished.connect(self._save_mini_pos)
            self.overlay.expand_requested.connect(self._expand_mini)
        if self.overlay.isVisible():
            self._save_mini_pos()
            self.overlay.hide()
            self.tray.act_mini.setText("显示迷你窗")
        else:
            pos = self._load_mini_pos()
            if pos:
                self.overlay.move(pos[0], pos[1])
            else:
                # 首次打开默认屏幕正中（之后拖动位置自动记忆）
                screen = QApplication.primaryScreen().availableGeometry()
                self.overlay.move(
                    screen.left() + (screen.width() - self.overlay.width()) // 2,
                    screen.top() + (screen.height() - self.overlay.height()) // 2)
            self._refresh_overlay()
            self.overlay.show()
            # 迷你模式接管：主窗口隐藏，控制全部在迷你窗上进行
            self.hide()
            self.tray.act_mini.setText("隐藏迷你窗")'''
new_toggle = '''    def _toggle_mini(self) -> None:
        if self.overlay is None:
            self.overlay = MiniOverlay()
            self.mini_controls = MiniControls()
            self.mini_controls.drag_finished.connect(self._save_mini_pos)
            self.mini_controls.primary_requested.connect(self._tray_toggle)
            self.mini_controls.abandon_requested.connect(self._on_abandon_requested)
            self.mini_controls.skip_requested.connect(self._on_skip_break)
            self.mini_controls.expand_requested.connect(self._expand_mini)
            self.mini_controls.opacity_selected.connect(self._on_mini_opacity)
            last_op = self.store.get_int("mini_opacity", 100)
            self.overlay.set_opacity(last_op)
            self.mini_controls.set_opacity(last_op)
        if self.overlay.isVisible():
            self._save_mini_pos()
            self.overlay.hide()
            self.mini_controls.hide()
            self.tray.act_mini.setText("显示迷你窗")
        else:
            pos = self._load_mini_pos()
            if pos:
                self.overlay.move(pos[0], pos[1])
            else:
                # 首次打开默认屏幕正中（之后拖动位置自动记忆）
                screen = QApplication.primaryScreen().availableGeometry()
                self.overlay.move(
                    screen.left() + (screen.width() - self.overlay.width()) // 2,
                    screen.top() + (screen.height() - self.overlay.height()) // 2)
            self.mini_controls.move(self.overlay.x(),
                                    self.overlay.y() + VISUAL_H - CONTROLS_OVERLAP)
            self._refresh_overlay()
            self.overlay.show()
            self.mini_controls.show()
            # 迷你模式接管：主窗口隐藏，控制全部在迷你窗上进行
            self.hide()
            self.tray.act_mini.setText("隐藏迷你窗")'''
assert old_toggle in src, "old_toggle 未命中"
src = src.replace(old_toggle, new_toggle)

# 4) _expand_mini 隐藏两个窗口
old_expand = '''        if self.overlay is not None:
            self._save_mini_pos()
            self.overlay.hide()
            self.tray.act_mini.setText("显示迷你窗")
        self.showNormal()'''
new_expand = '''        if self.overlay is not None:
            self._save_mini_pos()
            self.overlay.hide()
            if self.mini_controls is not None:
                self.mini_controls.hide()
            self.tray.act_mini.setText("显示迷你窗")
        self.showNormal()'''
assert old_expand in src, "old_expand 未命中"
src = src.replace(old_expand, new_expand)

# 5) _refresh_overlay 顺计时分支（label 转移到 controls）
old_sw = '''            self.overlay.set_display(text, progress, "stopwatch", running, label)
            primary = "暂停" if running else ("继续" if self.stopwatch.elapsed_seconds() > 0 else "开始顺计时")
            self.overlay.set_actions(primary, True, running or
                                     self.stopwatch.elapsed_seconds() > 0, False)
            return
        t = self.timer'''
new_sw = '''            self.overlay.set_display(text, progress, "stopwatch")
            if self.mini_controls is not None:
                self.mini_controls.set_state_label(label)
                primary = "暂停" if running else ("继续" if self.stopwatch.elapsed_seconds() > 0 else "开始顺计时")
                self.mini_controls.set_actions(primary, True, running or
                                               self.stopwatch.elapsed_seconds() > 0, False)
            return
        t = self.timer'''
assert old_sw in src, "old_sw 未命中"
src = src.replace(old_sw, new_sw)

# 6) _refresh_overlay 常规分支（label 转移到 controls）
old_reg = '''        self.overlay.set_display(text, progress, t.phase.value, t.running,
                                 self._mini_state_label(t))'''
new_reg = '''        self.overlay.set_display(text, progress, t.phase.value, t.running)
        if self.mini_controls is not None:
            self.mini_controls.set_state_label(self._mini_state_label(t))'''
assert old_reg in src, "old_reg 未命中"
src = src.replace(old_reg, new_reg)

# 7) _on_tick 迷你窗更新（去掉 label 参数 + 刷 controls 标签）
old_tick = '''        if self.overlay is not None and self.overlay.isVisible():
            self.overlay.set_display(text, progress, self.timer.phase.value,
                                     True, self._mini_state_label(self.timer))
        self._update_tray(text)'''
new_tick = '''        if self.overlay is not None and self.overlay.isVisible():
            self.overlay.set_display(text, progress, self.timer.phase.value)
            if self.mini_controls is not None:
                self.mini_controls.set_state_label(self._mini_state_label(self.timer))
        self._update_tray(text)'''
assert old_tick in src, "old_tick 未命中"
src = src.replace(old_tick, new_tick)

# 8) 顺计时 tick 的迷你窗更新
old_swtick = '''        if self.overlay is not None and self.overlay.isVisible():
            self.overlay.set_display(text, min(1.0, elapsed / (45 * 60)),
                                     "stopwatch", True, "⏱ 顺计时中")
        self._update_tray(f"⏱ {int(elapsed // 60):02d}:{int(elapsed) % 60:02d}")'''
new_swtick = '''        if self.overlay is not None and self.overlay.isVisible():
            self.overlay.set_display(text, min(1.0, elapsed / (45 * 60)),
                                     "stopwatch")
            if self.mini_controls is not None:
                self.mini_controls.set_state_label("⏱ 顺计时中")
        self._update_tray(f"⏱ {int(elapsed // 60):02d}:{int(elapsed) % 60:02d}")'''
assert old_swtick in src, "old_swtick 未命中"
src = src.replace(old_swtick, new_swtick)

# 9) _teardown 隐藏 controls
old_td = '''        self.sound.stop_noise()
        self._save_mini_pos()
        if self.overlay is not None:
            self.overlay.hide()
        self.monitor.stop()'''
new_td = '''        self.sound.stop_noise()
        self._save_mini_pos()
        if self.overlay is not None:
            self.overlay.hide()
        if self.mini_controls is not None:
            self.mini_controls.hide()
        self.monitor.stop()'''
assert old_td in src, "old_td 未命中"
src = src.replace(old_td, new_td)

open(path, "w", encoding="utf-8").write(src)
print(f"main_window 双窗口 glue 完成（{n0} → {len(src)} 字符）")

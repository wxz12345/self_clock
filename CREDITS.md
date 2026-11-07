# CREDITS / 素材与参考来源

本项目代码与素材均为原创或来自宽松许可的来源，明细如下。

## 原创部分

- 全部 Python 代码（`app/`、`core/`、`main.py`）
- 提示音：`assets/bell.wav / chime.wav / coin.wav / reminder.wav` 由 `assets/generate_assets.py` 以标准库（wave/struct/math）合成
- 应用图标：`assets/app.ico` 由 `assets/generate_icon.py` 生成（绘制逻辑在 `app/icons.py`，QPainter 程序化绘制）

## 外部素材（白噪音，assets/noise/）

| 文件 | 来源 |
|------|------|
| rain.mp3 雨声 | [freesound.org/s/157767](https://freesound.org/s/157767/)（128kbps/48kHz） |
| thunder.mp3 雷雨 | [freesound.org/s/157002](https://freesound.org/s/157002/)（128kbps/44.1kHz） |
| waves.mp3 海浪 | [freesound.org/s/144164](https://freesound.org/s/144164/)（128kbps/44.1kHz） |
| brown.mp3 棕噪音 | [freesound.org/s/165056](https://freesound.org/s/165056/)（128kbps/44.1kHz）；另有代码合成的 `brown.wav` 作后备 |
| wind.mp3 风声 | [freesound.org/s/263492](https://freesound.org/s/263492/)（128kbps/48kHz） |
| birds.mp3 鸟鸣 | [freesound.org/s/245774](https://freesound.org/s/245774/)（128kbps/48kHz） |
| cafe.mp3 咖啡馆 | [freesound.org/s/233280](https://freesound.org/s/233280/)（128kbps/48kHz） |
| fire.mp3 篝火 | [RainyBird](https://github.com/Everloom-129/RainyBird) `sounds/fireplace-with-crackling-sounds.mp3`（256kbps/44.1kHz） |

## 设计思想参考（未复制代码）

以下开源项目在调研阶段提供了思路参考，特此致谢：

| 项目 | 许可证 | 参考内容 |
|------|--------|----------|
| [Flowkeeper](https://github.com/flowkeeper-org/fk-desktop) | GPL-3.0 | 核心逻辑与 UI 解耦的架构思想（仅参考设计，未复制代码） |
| [Koncentro](https://github.com/kun-codes/Koncentro) | GPL-3.0 | PySide6 深色界面实践方向 |
| [Focuser](https://github.com/aadeshrao123/Focuser) | MIT | 前台/进程检测的匹配策略、温和提醒思路 |
| [FocusFlow](https://github.com/haldaranup/Focus-Flow) | MIT | "放弃必须填原因 + 全量日志"的产品验证 |
| [Tomodoro](https://github.com/lazy-guy/tomodoro) | MIT | 白噪音/小窗等候选功能 inspiration |
| [forest-productivity](https://github.com/Sriram-Nambiar/forest-productivity) | — | Forest 式游戏化玩法参考 |

完整调研与候选功能清单见 `docs/参考功能汇总.md`。

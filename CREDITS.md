# CREDITS / 素材与参考来源

本项目代码与素材均为原创或来自宽松许可的来源，明细如下。

## 原创部分

- 全部 Python 代码（`app/`、`core/`、`main.py`）
- 提示音：`assets/bell.wav / chime.wav / coin.wav / reminder.wav` 由 `assets/generate_assets.py` 以标准库（wave/struct/math）合成
- 应用图标：`assets/app.ico` 由 `assets/generate_icon.py` 生成（绘制逻辑在 `app/icons.py`，QPainter 程序化绘制）

## 外部素材（白噪音，assets/noise/）

全部来自 [Freesound.org](https://freesound.org)（128kbps MP3 预览规格）与
[RainyBird](https://github.com/Everloom-129/RainyBird) 仓库（MIT）。

**开源发布提示**：除纯雷声为 NC（禁止商用）外，其余均为 CC0 / CC-BY / MIT，可随项目分发；
CC-BY 条目分发时保留本文件即为署名。

| 文件 | 音色 | 声音（作者） | 许可证 | 时长 |
|------|------|--------------|--------|------|
| rain.mp3 | 雨声·车顶 | [Rain on Car Roof (parked car)](https://freesound.org/s/752219/) by gsparrysound | CC-BY 4.0 | 2 min |
| pure_rain1.mp3 | 纯雨声① | [Rain Storm](https://freesound.org/s/548381/) by Vanalosswen | CC0 | 10 min |
| pure_rain2.mp3 | 纯雨声② | [rain in the forest atmo field recording](https://freesound.org/s/536843/) by Garuda1982 | CC0 | 10 min |
| pure_rain3.mp3 | 纯雨声③ | [Central Texas Spring Hard Rain Mild Thunder Rolls](https://freesound.org/s/519573/) by DynamicAlgorhythm | CC0 | 10 min |
| storm1.mp3 | 雷雨① | [Rain with Moderate Thunder](https://freesound.org/s/737922/) by BobVoldar | CC-BY 4.0 | 24 min |
| storm2.mp3 | 雷雨② | [Heavy rain Heavy thunderstorms](https://freesound.org/s/859141/) by Hinoki.owo | CC-BY 4.0 | 7.6 min |
| storm3.mp3 | 雷雨③ | [33 Minute Thunderstorm](https://freesound.org/s/817285/) by BobVoldar | CC-BY 4.0 | 34 min |
| storm4.mp3 | 雷雨④ | [Rain and Thunder Ambience Tübingen](https://freesound.org/s/369547/) by Sheyvan | CC0 | 14 min |
| storm5.mp3 | 雷雨⑤ | [Night thunderstorm on suburbs](https://freesound.org/s/874803/) by kevp888 | CC-BY 4.0 | 41 min |
| pure_thunder.mp3 | 纯雷声 | [Thunderstorm_June](https://freesound.org/s/338374/) by DaveOfDefeat2248 | **CC-BY-NC**（仅限个人使用；**未随本仓库与安装包分发**，作者本地自用） | 18 min |
| crickets.mp3 | 虫鸣 | [Frogs and birds chirping in the fields at midnight after a rain](https://freesound.org/s/746877/) by lastraindrop | CC0 | 12 min |
| waves.mp3 | 海浪 | [Waves and birdsong](https://freesound.org/s/144164/) by juskiddink | CC-BY 4.0 | 10 min |
| fire.mp3 | 篝火 | [RainyBird](https://github.com/Everloom-129/RainyBird) `sounds/fireplace-with-crackling-sounds.mp3` | MIT（随仓库） | ~4 min |
| wind.mp3 | 风声 | [winter ambience leaves, wind, crow, birds](https://freesound.org/s/263492/) by lwdickens | CC0 | ~8 min |
| birds.mp3 | 鸟鸣 | [End Summer forest NL](https://freesound.org/s/245774/) by klankbeel | CC-BY 4.0 | ~7 min |
| cafe.mp3 | 咖啡馆 | [Ambience Coffee Shop 1](https://freesound.org/s/233280/) by JarredGibb | CC0 | ~7 min |
| brown.mp3 | 棕噪音 | [Brown Noise](https://freesound.org/s/165056/) by theundecided | CC0 | 5 min |

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

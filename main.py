# -*- coding: utf-8 -*-
"""自律番茄钟入口：单实例保护、主题、存储与主窗口。"""
import os
import sys
import traceback

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

try:  # QLocalServer/Socket 属于 QtNetwork；个别环境缺失时降级为无单实例保护
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    SINGLE_INSTANCE_AVAILABLE = True
except ImportError:  # pragma: no cover
    SINGLE_INSTANCE_AVAILABLE = False

# ---- 路径：兼容 PyInstaller 打包（onedir）----
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)          # exe 旁边存 data/
    ASSET_DIR = os.path.join(sys._MEIPASS, "assets")    # 只读资源
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSET_DIR = os.path.join(BASE_DIR, "assets")
sys.path.insert(0, BASE_DIR)

SINGLE_INSTANCE_KEY = "self_clock_single_instance"


def _install_crash_logger() -> None:
    """pythonw / 打包无控制台，崩溃信息落到 data/crash.log 便于排查。"""
    def hook(exc_type, exc_value, exc_tb):
        path = os.path.join(BASE_DIR, "data", "crash.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write("".join(traceback.format_exception(
                exc_type, exc_value, exc_tb)) + "\n" + "-" * 60 + "\n")
        sys.__excepthook__(exc_type, exc_value, exc_tb)
    sys.excepthook = hook


def _another_instance_running() -> bool:
    if not SINGLE_INSTANCE_AVAILABLE:
        return False
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_KEY)
    running = socket.waitForConnected(300)
    if running:
        socket.write(b"show\n")
        socket.flush()
        socket.waitForBytesWritten(300)
    socket.disconnectFromServer()
    return running


def main() -> int:
    _install_crash_logger()
    app = QApplication(sys.argv)
    app.setApplicationName("自律番茄钟")
    app.setApplicationDisplayName("自律番茄钟")

    # ---- 单实例保护：第二个实例唤起已有实例后直接退出 ----
    if _another_instance_running():
        return 0
    from core.store import Store  # noqa: E402
    from app import theme  # noqa: E402

    store = Store(os.path.join(BASE_DIR, "data"))
    theme.set_theme(store.get_setting("theme", "dark"))
    app.setPalette(theme.build_palette())
    app.setStyleSheet(theme.build_qss())

    from app import icons  # noqa: E402
    from app.main_window import MainWindow  # noqa: E402
    from core.backup import auto_backup  # noqa: E402
    from core.sound import SoundPlayer  # noqa: E402

    app.setWindowIcon(icons.load_app_icon())
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)

    data_dir = os.path.join(BASE_DIR, "data")
    window = MainWindow(store, SoundPlayer(ASSET_DIR), data_dir, ASSET_DIR)
    window.show()
    window.raise_()
    window.activateWindow()

    # 每日自动备份（静默）
    try:
        auto_backup(store.db_path, os.path.join(data_dir, "backups"), keep=14)
    except OSError:
        pass

    # 本地服务器：接收第二实例的 "show" 消息，把自己带到前台
    if SINGLE_INSTANCE_AVAILABLE:
        QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
        server = QLocalServer()
        server.listen(SINGLE_INSTANCE_KEY)

        def _on_new_connection() -> None:
            socket = server.nextPendingConnection()
            if socket and socket.waitForReadyRead(300):
                if b"show" in socket.readAll():
                    window.showNormal()
                    window.raise_()
                    window.activateWindow()
        server.newConnection.connect(_on_new_connection)

    code = app.exec()
    # 音频/监控线程偶发阻塞进程退出：数据均已同步落库，直接结束进程
    os._exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())

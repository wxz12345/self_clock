# -*- coding: utf-8 -*-
"""单实例握手：存活实例回复 ok -> 视为运行中；无回复的残留管道 -> 视为无实例。"""
import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalServer

import main as app_main


@pytest.fixture(scope="module")
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


@pytest.fixture
def server(qapp, monkeypatch):
    key = "self_clock_test_key"
    monkeypatch.setattr(app_main, "SINGLE_INSTANCE_KEY", key)
    QLocalServer.removeServer(key)
    srv = QLocalServer()
    assert srv.listen(key)
    yield srv
    srv.close()


def _pump(qapp, ms=50):
    import time
    end = time.time() + ms / 1000
    while time.time() < end:
        qapp.processEvents()


def test_no_server_means_not_running(qapp, monkeypatch):
    monkeypatch.setattr(app_main, "SINGLE_INSTANCE_KEY", "self_clock_absent_key")
    assert app_main._another_instance_running() is False


def test_silent_server_is_treated_as_stale(qapp, server):
    # 接受连接但从不回复（模拟僵死进程）
    assert app_main._another_instance_running() is False


SERVER_SCRIPT = """
import sys, time
from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalServer
app = QCoreApplication([])
QLocalServer.removeServer(sys.argv[1])
srv = QLocalServer()
assert srv.listen(sys.argv[1])
def on_conn():
    sock = srv.nextPendingConnection()
    if sock and sock.waitForReadyRead(300) and b"show" in bytes(sock.readAll()):
        sock.write(b"ok\\n"); sock.flush()   # 与 main.py 的处理一致
srv.newConnection.connect(on_conn)
print("ready", flush=True)
end = time.time() + 15
while time.time() < end:
    app.processEvents(); time.sleep(0.01)
"""


def test_replying_server_is_detected(qapp, monkeypatch):
    """真实跨进程：另一个进程扮演存活实例并回复 ok。"""
    import subprocess
    import sys
    key = "self_clock_test_key_live"
    monkeypatch.setattr(app_main, "SINGLE_INSTANCE_KEY", key)
    proc = subprocess.Popen([sys.executable, "-I", "-c", SERVER_SCRIPT, key],
                            stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "ready"
        assert app_main._another_instance_running() is True
    finally:
        proc.kill()
        proc.wait()

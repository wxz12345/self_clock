# -*- coding: utf-8 -*-
"""生成 assets/app.ico：把运行时绘制的图标渲染为多尺寸 PNG 并封装进 ICO 容器。

ICO 结构：ICONDIR(6B) + N * ICONDIRENTRY(16B) + 各 PNG 数据。
256px 的宽/高字段写 0（格式规定）。需要 PySide6（复用 app.icons 的绘制）。
"""
import os
import struct
import sys

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import theme  # noqa: E402
from app.icons import _paint_pixmap  # noqa: E402

SIZES = [16, 24, 32, 48, 64, 128, 256]


def png_bytes(size: int) -> bytes:
    pm = _paint_pixmap(size, theme.ACCENT)
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    pm.save(buf, "PNG")
    return bytes(buf.data())


def build_ico(path: str) -> None:
    images = [(s, png_bytes(s)) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = b""
    offset = 6 + 16 * len(images)
    blobs = b""
    for size, data in images:
        entries += struct.pack("<BBBBHHII",
                               size % 256, size % 256, 0, 0, 1, 32,
                               len(data), offset)
        blobs += data
        offset += len(data)
    with open(path, "wb") as f:
        f.write(header + entries + blobs)
    print("written", path, os.path.getsize(path), "bytes")


def build_check(path: str) -> None:
    """checkbox 选中态的白色勾（QSS image 用，2x 尺寸保证清晰）。"""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
    pm = QPixmap(34, 34)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    path_obj = QPainterPath()
    path_obj.moveTo(7, 18)
    path_obj.lineTo(14.5, 25.5)
    path_obj.lineTo(27, 9)
    pen = QPen(QColor("#ffffff"), 4.2)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.drawPath(path_obj)
    p.end()
    pm.save(path, "PNG")
    print("written", path, os.path.getsize(path), "bytes")


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    out = os.path.dirname(os.path.abspath(__file__))
    build_ico(os.path.join(out, "app.ico"))
    build_check(os.path.join(out, "check.png"))


if __name__ == "__main__":
    main()

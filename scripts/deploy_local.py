# -*- coding: utf-8 -*-
"""把发布 zip 原地部署到桌面快捷方式指向的本地运行目录。

用法:
    python scripts/deploy_local.py dist/SelfClock_v1.1.4.1_win64.zip
    python scripts/deploy_local.py <zip> --target <其它目录>

约定（每次发布新版本后都要跑一次）：
- 桌面「自律番茄钟.lnk」固定指向 dist/SelfClock/SelfClock.exe，路径里不带版本号，
  所以「更新快捷方式」= 把新版程序文件原地部署到这个目录。
- 只写程序文件（SelfClock.exe + _internal/），**绝不触碰 data/**
  （真实使用记录、备份都在这里）。
- 覆盖前把当前程序完整备份到 dist/_backup_SelfClock_<时间戳>/。
- 正在运行的实例会锁住 exe 和部分 DLL：这类文件先重命名为 .prev 再写入新版，
  运行中的实例继续用已映射的旧代码，重启后即为新版。旧文件归档进备份目录，
  全程不做删除。

退出码：0 全部成功；1 有文件失败（可从备份目录恢复）。
"""
import argparse
import os
import shutil
import sys
import tempfile
import time
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_TARGET = os.path.join(REPO_ROOT, "dist", "SelfClock")


def backup_current(target: str, stamp: str) -> str:
    backup = os.path.join(os.path.dirname(target),
                          f"_backup_SelfClock_{stamp}")
    os.makedirs(backup, exist_ok=True)
    exe = os.path.join(target, "SelfClock.exe")
    if os.path.isfile(exe):
        shutil.copy2(exe, backup)
    internal = os.path.join(target, "_internal")
    if os.path.isdir(internal):
        shutil.copytree(internal, os.path.join(backup, "_internal"))
    return backup


def collect(zip_path: str, stage: str) -> list[tuple[str, str]]:
    """返回 [(暂存文件, 目标相对路径)]，跳过任何 data/ 内容。"""
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(stage)
    plan = []
    for dirpath, _dirs, files in os.walk(stage):
        for fn in files:
            src = os.path.join(dirpath, fn)
            rel = os.path.relpath(src, stage)
            if rel.replace("\\", "/").split("/")[0] == "data":
                continue
            plan.append((src, rel))
    return plan


def deploy(zip_path: str, target: str) -> int:
    if not os.path.isfile(zip_path):
        print(f"找不到发布包: {zip_path}", flush=True)
        return 1
    if not os.path.isdir(target):
        print(f"目标目录不存在: {target}", flush=True)
        return 1

    stamp = time.strftime("%Y%m%d_%H%M%S")
    print(f"发布包: {zip_path}", flush=True)
    print(f"目标目录: {target}", flush=True)
    print(f"data/ 保留: {os.path.isdir(os.path.join(target, 'data'))}", flush=True)

    backup = backup_current(target, stamp)
    n_backup = sum(len(f) for _, _, f in os.walk(backup))
    print(f"已备份旧版到: {backup} ({n_backup} 个文件)", flush=True)

    stage = tempfile.mkdtemp(prefix="selfclock_deploy_")
    try:
        plan = collect(zip_path, stage)
        print(f"待部署程序文件: {len(plan)} 个", flush=True)
        renamed: list[tuple[str, str]] = []
        failed: list[tuple[str, str]] = []

        for src, rel in plan:
            dst = os.path.join(target, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                shutil.copy2(src, dst)
            except PermissionError:
                # 文件被运行中的实例锁住：改名让路，再写入新版
                prev = dst + f".prev_{stamp}"
                try:
                    os.rename(dst, prev)
                    shutil.copy2(src, dst)
                    renamed.append((prev, rel))
                except Exception as exc:
                    failed.append((rel, f"{type(exc).__name__}: {exc}"))
            except Exception as exc:
                failed.append((rel, f"{type(exc).__name__}: {exc}"))

        # 把让路的旧文件归档进备份目录（只移动，不删除）
        for prev, rel in renamed:
            dest = os.path.join(backup, "_prev", rel + f".prev_{stamp}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                os.rename(prev, dest)
            except OSError:
                pass
        print(f"重命名让路的文件: {len(renamed)} 个（已归档到备份）", flush=True)

        if failed:
            print(f"失败 {len(failed)} 个:", flush=True)
            for rel, err in failed[:15]:
                print(f"  {rel}: {err}", flush=True)
            print(f"可从备份恢复: {backup}", flush=True)
            return 1

        # 校验：每个程序文件都已就位且大小一致
        mismatch = []
        for src, rel in plan:
            dst = os.path.join(target, rel)
            if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(src):
                mismatch.append(rel)
        if mismatch:
            print(f"校验失败 {len(mismatch)} 个: {mismatch[:10]}", flush=True)
            return 1

        exe = os.path.join(target, "SelfClock.exe")
        print(f"部署完成: {len(plan)} 个程序文件全部就位", flush=True)
        print(f"新版 exe: {os.path.getsize(exe)} 字节", flush=True)
        print("data/ 未改动；正在运行的旧实例需重启后才是新版", flush=True)
        return 0
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", help="发布 zip 路径")
    parser.add_argument("--target", default=DEFAULT_TARGET,
                        help="本地运行目录（默认 dist/SelfClock）")
    args = parser.parse_args()
    zip_path = (args.zip if os.path.isabs(args.zip)
                else os.path.join(REPO_ROOT, args.zip))
    return deploy(zip_path, os.path.abspath(args.target))


if __name__ == "__main__":
    sys.exit(main())

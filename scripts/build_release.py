# -*- coding: utf-8 -*-
"""从指定 git tag 构建干净的 release zip（排除运行时数据/日志/NC 素材）。

用法:
    conda run -n self_clock python scripts/build_release.py v1.1.3
    conda run -n self_clock python scripts/build_release.py v1.1.3 --upload
"""
import os
import sys
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONDA_ENV = "self_clock"
EXCLUDE_DIRS = {"data", "backups", "__pycache__", ".zcode", ".git", "build", "preview"}
EXCLUDE_EXT = {".log", ".pyc", ".db", ".spec"}
EXCLUDE_FILES = {"pure_thunder.mp3"}


def should_exclude(relpath: str) -> bool:
    parts = relpath.replace("\\", "/").split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    name = parts[-1]
    if name in EXCLUDE_FILES:
        return True
    if os.path.splitext(name)[1].lower() in EXCLUDE_EXT:
        return True
    return False


def run(cmd, cwd=None):
    print(f"  $ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    args = sys.argv[1:]
    upload = "--upload" in args
    args = [a for a in args if a != "--upload"]
    if not args:
        print("用法: python scripts/build_release.py <tag> [--upload]")
        sys.exit(1)
    tag = args[0]
    zip_name = f"SelfClock_{tag}_win64.zip"
    out_path = os.path.join(REPO_ROOT, "dist", zip_name)

    build_dir = tempfile.mkdtemp(prefix=f"selfclock_{tag}_")
    print(f"[{tag}] 构建目录: {build_dir}", flush=True)

    try:
        print(f"[{tag}] 提取源码 (git archive {tag})...", flush=True)
        archive = subprocess.run(
            ["git", "archive", "--format=tar", tag],
            cwd=REPO_ROOT, capture_output=True, check=True)
        import io
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tf:
            tf.extractall(build_dir)

        # v2.1.0 起 mp3 不入库：tag 里带有 manifest.json 时，先把素材补齐
        # （本地完整则复制，否则从 noise-assets-v1 下载并校验）。
        # 旧 tag（v1.x / v2.0.0）本身内含 mp3、没有 manifest，原样处理。
        noise_dest = os.path.join(build_dir, "assets", "noise")
        if os.path.exists(os.path.join(noise_dest, "manifest.json")):
            sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
            import noise_pack
            print(f"[{tag}] 补齐白噪音素材...", flush=True)
            noise_pack.ensure(noise_dest,
                              local_dir=os.path.join(REPO_ROOT, "assets", "noise"),
                              progress=lambda m: print(f"[{tag}] {m}", flush=True))

        print(f"[{tag}] PyInstaller 构建...", flush=True)
        run([
            "conda", "run", "-n", CONDA_ENV, "--no-capture-output",
            "pyinstaller", "--noconfirm", "--clean",
            "--name", "SelfClock", "--windowed",
            "--icon", "assets/app.ico",
            "--add-data", f"assets{os.pathsep}assets",
            "main.py",
        ], cwd=build_dir)

        dist_dir = os.path.join(build_dir, "dist", "SelfClock")
        if not os.path.isdir(dist_dir):
            print(f"[{tag}] 构建失败: {dist_dir} 不存在", flush=True)
            sys.exit(1)

        print(f"[{tag}] 打包 (排除 data/log/db/NC)...", flush=True)
        os.makedirs(os.path.join(REPO_ROOT, "dist"), exist_ok=True)
        excluded = []
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(dist_dir):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for fn in files:
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, dist_dir)
                    if should_exclude(rel):
                        excluded.append(rel)
                        continue
                    zf.write(full, rel)
        if excluded:
            print(f"[{tag}] 已排除 {len(excluded)} 个文件: {excluded[:5]}...", flush=True)

        size_mb = os.path.getsize(out_path) / 1024 / 1024
        print(f"[{tag}] 完成: {out_path} ({size_mb:.1f} MB)", flush=True)

        # 验证：zip 内无敏感文件
        with zipfile.ZipFile(out_path) as zf:
            bad = [n for n in zf.namelist() if should_exclude(n)]
            if bad:
                print(f"[{tag}] 警告: zip 内仍有敏感文件: {bad}", flush=True)
                sys.exit(1)
        print(f"[{tag}] 验证通过: 无 data/db/log/NC 文件", flush=True)

        if upload:
            print(f"[{tag}] 上传到 GitHub release...", flush=True)
            # 删除旧附件
            result = subprocess.run(
                ["gh", "release", "view", tag, "--json", "assets", "-q",
                 ".assets[].name"],
                cwd=REPO_ROOT, capture_output=True, text=True)
            for old_name in result.stdout.strip().splitlines():
                if old_name:
                    print(f"[{tag}] 删除旧附件: {old_name}", flush=True)
                    run(["gh", "release", "delete-asset", tag, old_name, "--yes"],
                        cwd=REPO_ROOT)
            # 上传新附件
            run(["gh", "release", "upload", tag, out_path, "--clobber"],
                cwd=REPO_ROOT)
            print(f"[{tag}] 上传完成", flush=True)

    finally:
        shutil.rmtree(build_dir, ignore_errors=True)
        print(f"[{tag}] 清理构建目录", flush=True)


if __name__ == "__main__":
    main()
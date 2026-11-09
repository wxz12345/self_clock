# -*- coding: utf-8 -*-
"""白噪音素材的独立分发（v2.1.0 起 mp3 不再入库，避免仓库膨胀）。

素材作为单独的 GitHub Release 资产（tag: noise-assets-v1）托管；仓库里只保留一个
很小的 `assets/noise/manifest.json`（每个文件的 sha256/大小 + 下载地址）。

用法:
    python scripts/noise_pack.py fetch     # 从源码运行前：下载并校验素材到 assets/noise/
    python scripts/noise_pack.py verify    # 只校验本地素材是否完整、未损坏
    python scripts/noise_pack.py pack      # 维护者：把本地 mp3 打成 zip 并重写 manifest.json

已发布的 v1.x / v2.0.0 及其 git 历史里仍内含 mp3，保持原样；构建这些旧 tag 时不需要本脚本。
纯雷声(pure_thunder, CC-BY-NC)禁止商用分发，永远不进入素材包。
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile

REPO = "wxz12345/self_clock"
TAG = "noise-assets-v1"
ZIP_NAME = f"{TAG}.zip"
DEFAULT_URL = f"https://github.com/{REPO}/releases/download/{TAG}/{ZIP_NAME}"
NC_EXCLUDE = {"pure_thunder.mp3"}      # 许可证为 NC：不随素材包分发

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOISE_DIR = os.path.join(REPO_ROOT, "assets", "noise")
MANIFEST_NAME = "manifest.json"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(noise_dir: str = NOISE_DIR) -> dict:
    with open(os.path.join(noise_dir, MANIFEST_NAME), encoding="utf-8") as f:
        return json.load(f)


def problems(dest: str, manifest: dict) -> list[str]:
    """返回 dest 里缺失或哈希不符的文件名列表（空 = 完整）。"""
    bad = []
    for name, meta in manifest["files"].items():
        path = os.path.join(dest, name)
        if (not os.path.isfile(path)
                or os.path.getsize(path) != meta["size"]
                or sha256_file(path) != meta["sha256"]):
            bad.append(name)
    return bad


# ---------------------------------------------------------------- pack
def pack(noise_dir: str = NOISE_DIR, out_dir: str | None = None,
         url: str = DEFAULT_URL) -> str:
    """打包素材并重写 manifest.json，返回 zip 路径。"""
    out_dir = out_dir or os.path.join(REPO_ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    names = sorted(n for n in os.listdir(noise_dir)
                   if n.lower().endswith(".mp3") and n not in NC_EXCLUDE)
    if not names:
        raise SystemExit(f"{noise_dir} 里没有可打包的 mp3")
    zip_path = os.path.join(out_dir, ZIP_NAME)
    files = {}
    # mp3 已是压缩格式，STORED 即可（再压缩没有收益且更慢）
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for n in names:
            p = os.path.join(noise_dir, n)
            zf.write(p, n)
            files[n] = {"sha256": sha256_file(p), "size": os.path.getsize(p)}
    manifest = {
        "version": TAG,
        "url": url,
        "zip_sha256": sha256_file(zip_path),
        "zip_size": os.path.getsize(zip_path),
        "files": files,
    }
    with open(os.path.join(noise_dir, MANIFEST_NAME), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    return zip_path


# --------------------------------------------------------------- fetch
def fetch(dest: str, manifest: dict, url: str | None = None,
          progress=lambda msg: None) -> None:
    """下载素材包到临时文件 → 校验 zip 哈希 → 只解出清单里的文件 → 逐个校验。"""
    url = url or manifest["url"]
    os.makedirs(dest, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="noise_pack_")
    try:
        zip_path = os.path.join(tmp, ZIP_NAME)
        progress(f"下载 {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "SelfClock-noise-fetch"})
        with urllib.request.urlopen(req, timeout=60) as resp, \
                open(zip_path, "wb") as out:
            shutil.copyfileobj(resp, out, 1 << 20)
        if sha256_file(zip_path) != manifest["zip_sha256"]:
            raise RuntimeError("素材包校验失败（sha256 不符），已放弃，未写入任何文件")
        with zipfile.ZipFile(zip_path) as zf:
            members = set(zf.namelist())
            for name in manifest["files"]:
                if name not in members:
                    raise RuntimeError(f"素材包缺少 {name}")
                # 只按清单里的文件名写入，不信任 zip 内的任意路径
                with zf.open(name) as src, open(os.path.join(dest, name), "wb") as dst:
                    shutil.copyfileobj(src, dst, 1 << 20)
        bad = problems(dest, manifest)
        if bad:
            raise RuntimeError(f"解压后校验失败: {bad}")
        progress(f"完成：{len(manifest['files'])} 个文件已就位 -> {dest}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def ensure(dest: str, manifest: dict | None = None, local_dir: str | None = None,
           progress=print) -> None:
    """让 dest 里有完整素材：已完整则跳过；本地目录完整则复制；否则下载。"""
    manifest = manifest or load_manifest(dest)
    bad = problems(dest, manifest)
    if not bad:
        progress("素材已完整，跳过")
        return
    if local_dir and os.path.isdir(local_dir) and not problems(local_dir, manifest):
        os.makedirs(dest, exist_ok=True)
        for name in manifest["files"]:
            shutil.copy2(os.path.join(local_dir, name), os.path.join(dest, name))
        progress(f"从本地 {local_dir} 复制了 {len(manifest['files'])} 个文件")
        return
    fetch(dest, manifest, progress=progress)


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else ""
    if cmd == "pack":
        path = pack()
        print(f"已生成 {path}\n已更新 {os.path.join(NOISE_DIR, MANIFEST_NAME)}")
        print(f"下一步：gh release create {TAG} {path} --repo {REPO} "
              f"--title \"白噪音素材包\" --notes \"素材许可证见 CREDITS.md\"")
        return 0
    manifest = load_manifest()
    if cmd == "verify":
        bad = problems(NOISE_DIR, manifest)
        print("完整" if not bad else f"缺失/损坏: {bad}")
        return 0 if not bad else 1
    if cmd == "fetch":
        ensure(NOISE_DIR, manifest)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

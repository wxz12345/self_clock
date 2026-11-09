# -*- coding: utf-8 -*-
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "scripts"))
import noise_pack  # noqa: E402


@pytest.fixture
def pack_env(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "rain.mp3").write_bytes(b"rain-bytes" * 100)
    (src / "wind.mp3").write_bytes(b"wind-bytes" * 50)
    (src / "pure_thunder.mp3").write_bytes(b"NC-must-not-ship")
    zip_path = noise_pack.pack(str(src), str(tmp_path / "out"),
                               url=(tmp_path / "out" / noise_pack.ZIP_NAME).as_uri())
    manifest = noise_pack.load_manifest(str(src))
    return src, tmp_path, zip_path, manifest


def test_pack_excludes_nc_and_writes_manifest(pack_env):
    src, _, zip_path, manifest = pack_env
    assert sorted(manifest["files"]) == ["rain.mp3", "wind.mp3"]
    import zipfile
    with zipfile.ZipFile(zip_path) as zf:
        assert "pure_thunder.mp3" not in zf.namelist()
    assert noise_pack.problems(str(src), manifest) == []


def test_fetch_downloads_and_verifies(pack_env):
    _, tmp_path, _, manifest = pack_env
    dest = tmp_path / "dest"
    noise_pack.fetch(str(dest), manifest)
    assert noise_pack.problems(str(dest), manifest) == []
    assert sorted(os.listdir(dest)) == ["rain.mp3", "wind.mp3"]


def test_problems_detects_missing_and_corrupt(pack_env):
    src, tmp_path, _, manifest = pack_env
    dest = tmp_path / "d2"
    noise_pack.fetch(str(dest), manifest)
    (dest / "wind.mp3").write_bytes(b"tampered")
    os.remove(dest / "rain.mp3")
    assert sorted(noise_pack.problems(str(dest), manifest)) == ["rain.mp3", "wind.mp3"]


def test_fetch_rejects_tampered_zip_and_writes_nothing(pack_env):
    _, tmp_path, zip_path, manifest = pack_env
    with open(zip_path, "ab") as f:
        f.write(b"junk")                         # 破坏 zip 哈希
    dest = tmp_path / "d3"
    with pytest.raises(RuntimeError):
        noise_pack.fetch(str(dest), manifest)
    assert not any(dest.iterdir()) if dest.exists() else True


def test_ensure_prefers_local_copy_and_skips_when_complete(pack_env, monkeypatch):
    src, tmp_path, _, manifest = pack_env
    monkeypatch.setattr(noise_pack, "fetch",
                        lambda *a, **k: pytest.fail("不应联网"))
    dest = tmp_path / "d4"
    noise_pack.ensure(str(dest), manifest, local_dir=str(src), progress=lambda m: None)
    assert noise_pack.problems(str(dest), manifest) == []
    noise_pack.ensure(str(dest), manifest, local_dir=None, progress=lambda m: None)  # 已完整：跳过


def test_repo_manifest_is_well_formed_if_present():
    path = os.path.join(noise_pack.NOISE_DIR, noise_pack.MANIFEST_NAME)
    if not os.path.exists(path):
        pytest.skip("manifest 尚未生成")
    m = json.load(open(path, encoding="utf-8"))
    assert m["url"].startswith("https://github.com/wxz12345/self_clock/releases/download/")
    assert "pure_thunder.mp3" not in m["files"]
    assert all(len(v["sha256"]) == 64 for v in m["files"].values())

"""Tests for the Source Loader Service.

Covers the happy path against the real fixture zip plus the malicious-zip
fixtures the reference doc requires (§11, phase SL): zip-slip, oversized entry,
and symlink rejection are all synthesized in-test.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from artifact_loader import load_design, load_srs
from config import Settings
from exceptions import SourceLoadError
from main import app
from source_loader import load_source


@pytest.fixture()
def cfg(tmp_path: Path) -> Settings:
    """Isolated settings pointing at temp source/dest dirs."""
    src = tmp_path / "zipsrc"
    dest = tmp_path / "dest"
    srs_src = tmp_path / "srssrc"
    srs_dest = tmp_path / "srsdest"
    design_src = tmp_path / "designsrc"
    design_dest = tmp_path / "designdest"
    for d in (src, dest, srs_src, srs_dest, design_src, design_dest):
        d.mkdir()
    return Settings(
        zip_source_dir=src,
        unzip_dest_dir=dest,
        srs_source_dir=srs_src,
        srs_dest_dir=srs_dest,
        design_source_dir=design_src,
        design_dest_dir=design_dest,
    )


def _make_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


def test_happy_path(cfg: Settings) -> None:
    _make_zip(
        cfg.zip_source_dir / "app.zip",
        {"proj/main.py": b"print('hi')", "proj/util/__init__.py": b""},
    )
    result = load_source(cfg=cfg)
    assert result.status == "OK"
    assert result.file_count == 2
    assert (cfg.unzip_dest_dir / "proj" / "main.py").read_bytes() == b"print('hi')"


def test_junk_is_skipped(cfg: Settings) -> None:
    _make_zip(
        cfg.zip_source_dir / "app.zip",
        {"proj/main.py": b"x", "proj/__pycache__/main.cpython-312.pyc": b"junk"},
    )
    result = load_source(cfg=cfg)
    assert result.file_count == 1
    assert any("__pycache__" in s for s in result.skipped)


def test_zip_slip_rejected(cfg: Settings) -> None:
    zpath = cfg.zip_source_dir / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("../../escape.py", b"pwned")
    with pytest.raises(SourceLoadError) as exc:
        load_source(cfg=cfg)
    assert exc.value.code == "zip_slip"


def test_oversized_entry_rejected(cfg: Settings) -> None:
    small = Settings(
        zip_source_dir=cfg.zip_source_dir,
        unzip_dest_dir=cfg.unzip_dest_dir,
        max_file_bytes=10,
    )
    _make_zip(cfg.zip_source_dir / "big.zip", {"proj/big.py": b"x" * 100})
    with pytest.raises(SourceLoadError) as exc:
        load_source(cfg=small)
    assert exc.value.code == "entry_too_large"


def test_no_zip_found(cfg: Settings) -> None:
    with pytest.raises(SourceLoadError) as exc:
        load_source(cfg=cfg)
    assert exc.value.code == "no_zip_found"


def test_dest_reset_between_runs(cfg: Settings) -> None:
    stale = cfg.unzip_dest_dir / "stale.py"
    stale.write_text("old")
    _make_zip(cfg.zip_source_dir / "app.zip", {"proj/main.py": b"x"})
    load_source(cfg=cfg)
    assert not stale.exists()


def test_health_endpoint() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


# --- SRS artifact loader ---


def test_load_srs_any_file_type(cfg: Settings) -> None:
    (cfg.srs_source_dir / "spec.docx").write_bytes(b"binary-docx")
    (cfg.srs_source_dir / "spec.json").write_text('{"req": 1}')
    result = load_srs(cfg=cfg)
    assert result.status == "OK"
    assert result.artifact == "SRS"
    assert result.file_count == 2
    assert (cfg.srs_dest_dir / "spec.json").read_text() == '{"req": 1}'
    assert (cfg.srs_dest_dir / "spec.docx").read_bytes() == b"binary-docx"


def test_load_srs_skips_gitkeep(cfg: Settings) -> None:
    (cfg.srs_source_dir / ".gitkeep").write_text("")
    (cfg.srs_source_dir / "spec.md").write_text("# SRS")
    result = load_srs(cfg=cfg)
    assert result.file_count == 1
    assert not (cfg.srs_dest_dir / ".gitkeep").exists()


def test_load_srs_empty_is_ok(cfg: Settings) -> None:
    result = load_srs(cfg=cfg)
    assert result.status == "OK"
    assert result.file_count == 0


def test_load_srs_missing_dir_errors(cfg: Settings) -> None:
    cfg.srs_source_dir.rmdir()
    with pytest.raises(SourceLoadError) as exc:
        load_srs(cfg=cfg)
    assert exc.value.code == "no_artifact_dir"


def test_load_srs_preserves_dest_gitkeep(cfg: Settings) -> None:
    keep = cfg.srs_dest_dir / ".gitkeep"
    keep.write_text("")
    (cfg.srs_source_dir / "spec.md").write_text("# SRS")
    load_srs(cfg=cfg)
    assert keep.exists()  # structure placeholder survives the reset


# --- Design artifact loader ---


def test_load_design_multiple_file_types(cfg: Settings) -> None:
    (cfg.design_source_dir / "arch.md").write_text("# design")
    (cfg.design_source_dir / "erd.csv").write_text("a,b")
    (cfg.design_source_dir / "openapi.yml").write_text("openapi: 3.0")
    result = load_design(cfg=cfg)
    assert result.status == "OK"
    assert result.artifact == "design"
    assert result.file_count == 3
    assert (cfg.design_dest_dir / "openapi.yml").read_text() == "openapi: 3.0"


def test_load_design_missing_dir_errors(cfg: Settings) -> None:
    cfg.design_source_dir.rmdir()
    with pytest.raises(SourceLoadError) as exc:
        load_design(cfg=cfg)
    assert exc.value.code == "no_artifact_dir"

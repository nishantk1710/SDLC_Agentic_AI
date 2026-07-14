"""Tests for the Source Loader Service.

Covers the happy path plus the malicious-zip fixtures the reference doc requires
(§11, phase SL): zip-slip and oversized-entry rejection are synthesized in-test.
Sources are location strings resolved through the (local) storage backend, so
tests point them at temp dirs.
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
from storage import get_storage


@pytest.fixture()
def cfg(tmp_path: Path) -> Settings:
    """Isolated settings pointing at temp source/dest locations."""
    dirs = {
        name: tmp_path / name
        for name in ("zipsrc", "dest", "srssrc", "srsdest", "designsrc", "designdest")
    }
    for d in dirs.values():
        d.mkdir()
    return Settings(
        zip_source=str(dirs["zipsrc"]),
        unzip_dest_dir=dirs["dest"],
        srs_source=str(dirs["srssrc"]),
        srs_dest_dir=dirs["srsdest"],
        design_source=str(dirs["designsrc"]),
        design_dest_dir=dirs["designdest"],
    )


def _make_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)


# --- Source code (zip) ---


def test_happy_path(cfg: Settings) -> None:
    _make_zip(
        Path(cfg.zip_source) / "app.zip",
        {"proj/main.py": b"print('hi')", "proj/util/__init__.py": b""},
    )
    result = load_source(cfg=cfg)
    assert result.status == "OK"
    assert result.file_count == 2
    assert (cfg.unzip_dest_dir / "proj" / "main.py").read_bytes() == b"print('hi')"


def test_zip_picked_by_glob_ignores_readme(cfg: Settings) -> None:
    # A contract README.md sits alongside the zip in the handoff folder.
    (Path(cfg.zip_source) / "README.md").write_text("# contract schema")
    _make_zip(Path(cfg.zip_source) / "code.zip", {"proj/main.py": b"x"})
    result = load_source(cfg=cfg)
    assert result.status == "OK"
    assert result.zip_name == "code.zip"


def test_junk_is_skipped(cfg: Settings) -> None:
    _make_zip(
        Path(cfg.zip_source) / "app.zip",
        {"proj/main.py": b"x", "proj/__pycache__/main.cpython-312.pyc": b"junk"},
    )
    result = load_source(cfg=cfg)
    assert result.file_count == 1
    assert any("__pycache__" in s for s in result.skipped)


def test_zip_slip_rejected(cfg: Settings) -> None:
    with zipfile.ZipFile(Path(cfg.zip_source) / "evil.zip", "w") as zf:
        zf.writestr("../../escape.py", b"pwned")
    with pytest.raises(SourceLoadError) as exc:
        load_source(cfg=cfg)
    assert exc.value.code == "zip_slip"


def test_oversized_entry_rejected(cfg: Settings) -> None:
    small = Settings(
        zip_source=cfg.zip_source,
        unzip_dest_dir=cfg.unzip_dest_dir,
        max_file_bytes=10,
    )
    _make_zip(Path(cfg.zip_source) / "big.zip", {"proj/big.py": b"x" * 100})
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
    _make_zip(Path(cfg.zip_source) / "app.zip", {"proj/main.py": b"x"})
    load_source(cfg=cfg)
    assert not stale.exists()


def test_health_endpoint() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


# --- Storage backend ---


def test_unsupported_storage_backend() -> None:
    with pytest.raises(SourceLoadError) as exc:
        get_storage("s3")
    assert exc.value.code == "unsupported_storage"


# --- SRS artifact loader ---


def test_load_srs_any_file_type(cfg: Settings) -> None:
    (Path(cfg.srs_source) / "spec.docx").write_bytes(b"binary-docx")
    (Path(cfg.srs_source) / "spec.json").write_text('{"req": 1}')
    result = load_srs(cfg=cfg)
    assert result.status == "OK"
    assert result.artifact == "SRS"
    assert result.file_count == 2
    assert (cfg.srs_dest_dir / "spec.json").read_text() == '{"req": 1}'
    assert (cfg.srs_dest_dir / "spec.docx").read_bytes() == b"binary-docx"


def test_load_srs_skips_contract_docs(cfg: Settings) -> None:
    # README.md (contract schema) and .gitkeep must not be loaded as SRS.
    (Path(cfg.srs_source) / "README.md").write_text("# contract")
    (Path(cfg.srs_source) / ".gitkeep").write_text("")
    (Path(cfg.srs_source) / "spec.md").write_text("# SRS")
    result = load_srs(cfg=cfg)
    assert result.file_count == 1
    assert result.files[0].path == "spec.md"
    assert not (cfg.srs_dest_dir / "README.md").exists()


def test_load_srs_empty_is_ok(cfg: Settings) -> None:
    result = load_srs(cfg=cfg)
    assert result.status == "OK"
    assert result.file_count == 0


def test_load_srs_missing_dir_errors(cfg: Settings) -> None:
    Path(cfg.srs_source).rmdir()
    with pytest.raises(SourceLoadError) as exc:
        load_srs(cfg=cfg)
    assert exc.value.code == "no_artifact_dir"


def test_load_srs_preserves_dest_gitkeep(cfg: Settings) -> None:
    keep = cfg.srs_dest_dir / ".gitkeep"
    keep.write_text("")
    (Path(cfg.srs_source) / "spec.md").write_text("# SRS")
    load_srs(cfg=cfg)
    assert keep.exists()  # structure placeholder survives the reset


# --- Design artifact loader ---


def test_load_design_multiple_file_types(cfg: Settings) -> None:
    (Path(cfg.design_source) / "arch.md").write_text("# design")
    (Path(cfg.design_source) / "erd.csv").write_text("a,b")
    (Path(cfg.design_source) / "openapi.yml").write_text("openapi: 3.0")
    result = load_design(cfg=cfg)
    assert result.status == "OK"
    assert result.artifact == "design"
    assert result.file_count == 3
    assert (cfg.design_dest_dir / "openapi.yml").read_text() == "openapi: 3.0"


def test_load_design_missing_dir_errors(cfg: Settings) -> None:
    Path(cfg.design_source).rmdir()
    with pytest.raises(SourceLoadError) as exc:
        load_design(cfg=cfg)
    assert exc.value.code == "no_artifact_dir"

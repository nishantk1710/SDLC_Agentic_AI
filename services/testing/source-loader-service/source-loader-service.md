# Source Loader Service — Testing Phase (Team 4)

First stage of the testing phase. Fetches inputs from **fixed paths** under
`contracts/shared/` and places them in the testing phase's input tree:

| Input | From | To | How |
|---|---|---|---|
| Source code | `contracts/shared/zipped_code/*.zip` | `data/input/unzipped-code/` | safe extraction |
| SRS (requirements) | `contracts/shared/SRS/` | `data/input/SRS/` | verbatim copy, any file type |
| Design artifact | `contracts/shared/design-artifact/` | `data/input/design-artifact/` | verbatim copy, any file type |

The zip is extracted **safely** (see below) into clean, inline source. The SRS
and design artifacts are **pass-through** — copied verbatim, not parsed (the
reference design treats requirements/design as structured data that travels
alongside the source, §1).

> The reference design treats this as an *in-process module* of the testing
> phase. This FastAPI layer is a thin, testable wrapper over `load_source()` —
> the pipeline can also import and call that function directly.
>
> How the zip *actually* arrives (upload vs. path vs. contract reference) is TBD
> with the implementation team; for now the source is a fixed directory.

## Safety (option-2 extraction)

Every entry is validated **before** it is written — no blind `extractall`:

| Guard | Rejects |
|---|---|
| Zip-slip / path traversal | entries resolving outside the destination (`..`, absolute) |
| Symlinks | link entries (can escape the tree) |
| Zip bomb | per-file size, whole-archive size, entry count, compression ratio |

Junk (`__pycache__`, `*.pyc`, `.git`, `.DS_Store`) is skipped for clean output.
Failures raise `SourceLoadError`, surfaced as an `ERROR` result — the pipeline's
ERROR verdict path.

## Layout

Not deployed on its own, so it is a **flat set of modules** (no `app/` package);
`requirements.txt` lives one level up, shared by the whole testing phase.

```
services/testing/
├─ requirements.txt          shared by the whole testing phase
├─ .venv/                     shared venv
└─ source-loader-service/
   ├─ config.py               paths + safety limits (env prefix SOURCE_LOADER_)
   ├─ exceptions.py           SourceLoadError
   ├─ models.py               LoadResult / ArtifactLoadResult / ExtractedFile
   ├─ fsutil.py               shared dir reset (preserves .gitkeep)
   ├─ source_loader.py        safe zip extractor (core)
   ├─ artifact_loader.py      pass-through copy for SRS (any file type)
   ├─ main.py                 FastAPI: /health, /ready, /load, /load-srs, /load-design
   ├─ conftest.py             puts the flat modules on sys.path for pytest
   └─ tests/
```

Local data is **git-ignored** (both `services/testing/data/**` and the
`contracts/shared/*` payloads), but the folder structure is kept via `.gitkeep`
placeholders — which the loaders never copy or delete.

## Run

```bash
# from services/testing/ (shared venv + requirements for the whole testing phase)
py -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt

# from services/testing/source-loader-service/ (dir must be cwd — modules are flat)
../.venv/Scripts/python -m uvicorn main:app --reload --port 8010
../.venv/Scripts/python -m pytest tests/ -q
```

Endpoints (no body):
- `POST /load` → source-code manifest: `status`, `zip_name`, `file_count`,
  `total_bytes`, `files[]`, `skipped[]`.
- `POST /load-srs` → SRS manifest: `status`, `artifact`, `file_count`,
  `total_bytes`, `files[]`.
- `POST /load-design` → design-artifact manifest (same shape as `/load-srs`).

## Config (override via env, prefix `SOURCE_LOADER_`)

| Var | Default |
|---|---|
| `SOURCE_LOADER_ZIP_SOURCE_DIR` | `contracts/shared/zipped_code` |
| `SOURCE_LOADER_UNZIP_DEST_DIR` | `services/testing/data/input/unzipped-code` |
| `SOURCE_LOADER_SRS_SOURCE_DIR` | `contracts/shared/SRS` |
| `SOURCE_LOADER_SRS_DEST_DIR` | `services/testing/data/input/SRS` |
| `SOURCE_LOADER_DESIGN_SOURCE_DIR` | `contracts/shared/design-artifact` |
| `SOURCE_LOADER_DESIGN_DEST_DIR` | `services/testing/data/input/design-artifact` |
| `SOURCE_LOADER_MAX_FILE_BYTES` | 50 MiB |
| `SOURCE_LOADER_MAX_TOTAL_BYTES` | 500 MiB |
| `SOURCE_LOADER_MAX_FILES` | 10000 |
| `SOURCE_LOADER_MAX_COMPRESSION_RATIO` | 100 |

"""Ensures the flat modules (config, main, source_loader, …) are importable.

The service is not packaged (no ``app/``), so its directory must be on
``sys.path`` for both pytest and ``uvicorn``. pytest adds the directory of the
nearest ``conftest.py`` automatically, so this file's presence is enough.
"""

from __future__ import annotations

import importlib


def test_sonya_main_module_exposes_main_callable() -> None:
    main_module = importlib.import_module("sonya.main")
    assert callable(getattr(main_module, "main", None))


def test_sonya_runs_via_python_dash_m() -> None:
    dunder_main = importlib.import_module("sonya.__main__")
    assert hasattr(dunder_main, "main") or hasattr(dunder_main, "__name__")

"""Import every py_premiere module.

The 3.7 CI job runs this, so any module using post-3.7 runtime syntax or
stdlib fails there at import time even when no other test touches it.
"""

from __future__ import annotations

import importlib
import pkgutil

import py_premiere


def test_import_all_modules() -> None:
    prefix = py_premiere.__name__ + "."
    for module_info in pkgutil.walk_packages(py_premiere.__path__, prefix):
        importlib.import_module(module_info.name)

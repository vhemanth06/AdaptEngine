"""V2-TC2: experiments_v2 never imports from, or names paths under, experiments/."""

import ast
import os

OLD = "experiments" + "/"  # built so this file does not flag itself
V2 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _py_files():
    for d, dirs, files in os.walk(V2):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        yield from (os.path.join(d, f) for f in files if f.endswith(".py"))


def test_no_import_or_path_of_old_harness():
    bad = []
    for path in _py_files():
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                bad += [(path, a.name) for a in node.names if a.name.split(".")[0] == "experiments"]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if node.module.split(".")[0] == "experiments":
                    bad.append((path, node.module))
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                v = node.value.replace("\\", "/")
                if v.startswith(OLD) or "/" + OLD in v.split("experiments_v2")[0]:
                    bad.append((path, v))
    assert not bad, bad

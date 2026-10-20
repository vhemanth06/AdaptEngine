import ast
import os
import pytest


def get_imports(filepath, root_pkg="adaptengine"):
    """Parse a python file with AST and return resolved internal and external import names."""
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)

    norm_path = filepath.replace("\\", "/")
    # Determine the package parts relative to src/
    # e.g., src/adaptengine/learner/state.py -> ['adaptengine', 'learner']
    parts = norm_path.split("/")
    if "src" in parts:
        src_idx = parts.index("src")
        file_pkg_parts = parts[src_idx + 1 : -1]
    elif root_pkg in parts:
        root_idx = parts.index(root_pkg)
        file_pkg_parts = parts[root_idx:-1]
    else:
        file_pkg_parts = [root_pkg]

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                # Relative import
                # level 1 = current dir, level 2 = parent dir, etc.
                trim = node.level - 1
                if trim <= len(file_pkg_parts):
                    base_parts = (
                        file_pkg_parts[: len(file_pkg_parts) - trim] if trim > 0 else file_pkg_parts
                    )
                    mod_name = node.module or ""
                    full_mod = ".".join(base_parts + ([mod_name] if mod_name else []))
                    imports.add(full_mod)
                else:
                    imports.add(node.module or "")
            elif node.module:
                imports.add(node.module)
    return imports


def test_layering_and_dependency_rules():
    """Enforce strict unidirectional dependency rules:
    core <- curriculum <- learner <- diagnostic <- session / api <- cli
    """
    src_dir = "src/adaptengine"
    layer_order = {
        "core": 0,
        "curriculum": 1,
        "learner": 2,
        "diagnostic": 3,
        "planner": 3,
        "session": 4,
        "api": 4,
        "cli": 5,
    }

    for root, _, files in os.walk(src_dir):
        for file in files:
            if not file.endswith(".py") or file == "__init__.py":
                continue
            path = os.path.join(root, file)
            norm_path = path.replace("\\", "/")
            resolved_imports = get_imports(path)

            # Determine module layer
            current_layer = None
            for layer_name, layer_num in layer_order.items():
                if f"/{layer_name}/" in norm_path or norm_path.endswith(f"/{layer_name}.py"):
                    current_layer = (layer_name, layer_num)
                    break

            if current_layer is None:
                continue

            current_name, current_num = current_layer

            # Check all imports
            for imp in resolved_imports:
                for target_name, target_num in layer_order.items():
                    target_pkg = f"adaptengine.{target_name}"
                    if imp == target_pkg or imp.startswith(f"{target_pkg}."):
                        # Target must be strictly <= current_num
                        if target_num > current_num:
                            pytest.fail(
                                f"Layering violation: {norm_path} (layer {current_name}:{current_num}) "
                                f"imports from higher layer {target_name}:{target_num} ({imp})"
                            )


def test_prohibited_libraries():
    """Verify no non-deterministic libraries or prohibited external dependencies."""
    src_dir = "src/adaptengine"

    for root, _, files in os.walk(src_dir):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            norm_path = path.replace("\\", "/")
            imports = get_imports(path)

            # networkx only in curriculum/graph.py
            if any(imp == "networkx" or imp.startswith("networkx.") for imp in imports):
                assert "curriculum/graph.py" in norm_path, f"networkx illegal in {norm_path}"

            # pyBKT only in learner/ adapter file
            if any(imp.lower() == "pybkt" or imp.lower().startswith("pybkt.") for imp in imports):
                assert (
                    "learner/adapter.py" in norm_path or "learner/pybkt_adapter.py" in norm_path
                ), f"pyBKT illegal in {norm_path}"

            # Determinism checks
            top_level = {imp.split(".")[0] for imp in imports}
            for forbidden in ["time", "datetime", "random"]:
                if forbidden in top_level:
                    assert False, f"Non-deterministic module '{forbidden}' imported in {norm_path}"

            for agentic in ["openai", "anthropic", "google", "agents"]:
                if agentic in top_level:
                    assert False, f"LLM/Agentic module '{agentic}' imported in {norm_path}"


def test_tools_authoring_isolation(tmp_path):
    """Test that prohibited imports in an authoring fixture are flagged."""
    bad_code = """
import random
import time
from adaptengine.cli import main
"""
    test_file = tmp_path / "bad_authoring.py"
    test_file.write_text(bad_code)
    imports = get_imports(str(test_file))
    top_level = {imp.split(".")[0] for imp in imports}

    assert "random" in top_level
    assert "time" in top_level
    assert any(imp.startswith("adaptengine.cli") for imp in imports)

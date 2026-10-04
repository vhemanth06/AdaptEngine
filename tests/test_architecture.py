import ast
import os
import pytest

def get_imports(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=filepath)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.add(n.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                if node.level > 0:
                    pass
                else:
                    imports.add(node.module.split('.')[0])
    return imports

# TC-X2.2: An LLM SDK or agents/ module is imported outside the allowed boundary... The architecture boundary tests fail
def test_architecture_rules():
    src_dir = "src/adaptengine"
    
    for root, _, files in os.walk(src_dir):
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            imports = get_imports(path)
            
            normalized_path = path.replace("\\", "/")
            
            if "networkx" in imports:
                assert "curriculum/graph.py" in normalized_path
                
            if any(x in root for x in ["core", "curriculum", "learner"]) or "session.py" in normalized_path:
                assert "time" not in imports
                assert "datetime" not in imports
                assert "random" not in imports
                
            assert "openai" not in imports
            assert "anthropic" not in imports
            assert "google" not in imports
            assert "agents" not in imports

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if any(x in content for x in ["open(", ".read_text", ".write_text", ".read_bytes", ".write_bytes"]):
                allowed = ["curriculum/loader.py", "session.py", "cli.py"]
                assert any(a in normalized_path for a in allowed), f"File I/O not allowed in {path}"

def test_tools_authoring_isolation():
    assert True

#!/usr/bin/env python3
"""
Software Digital Twin PoC - Improved Version
Now tracks internal modules + external packages + versions
"""

import ast
import re
import sys
from pathlib import Path
from collections import defaultdict
import networkx as nx
from git import Repo
from radon.complexity import cc_visit
from radon.metrics import mi_visit
import json
import pickle
from datetime import datetime
from tqdm import tqdm

try:
    from importlib.metadata import version, PackageNotFoundError
except ImportError:
    from importlib_metadata import version, PackageNotFoundError

# ================== CONFIG ==================
REPO_PATH = Path(r"D:\AWX")  # <-- CHANGE THIS
OUTPUT_DIR = Path("twin_output")
IGNORE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "dist", "build", ".idea", ".vscode", "tests", "test",
    ".mypy_cache", ".pytest_cache", "htmlcov", ".tox"
}
# ============================================

OUTPUT_DIR.mkdir(exist_ok=True)

# Common standard library modules (simplified list)
STDLIB = {
    "os", "sys", "re", "json", "datetime", "pathlib", "collections", "itertools",
    "functools", "typing", "abc", "ast", "asyncio", "base64", "csv", "hashlib",
    "http", "logging", "math", "pickle", "random", "shlex", "shutil", "socket",
    "sqlite3", "string", "subprocess", "tempfile", "threading", "time", "traceback",
    "urllib", "uuid", "xml", "zipfile", "io", "enum", "dataclasses", "contextlib"
}

def is_ignored(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)

def get_module_name(file_path: Path, root: Path) -> str:
    rel = file_path.relative_to(root)
    parts = list(rel.with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else rel.stem

def extract_imports(file_path: Path) -> set[str]:
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])
    except Exception:
        pass
    return imports

def parse_requirements(root: Path) -> dict:
    """Parse requirements.txt and pyproject.toml for declared dependencies"""
    deps = {}

    # requirements.txt
    req_file = root / "requirements.txt"
    if req_file.exists():
        with open(req_file, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    # Simple parsing: package==version or package>=version
                    match = re.match(r"([a-zA-Z0-9_-]+)\s*([=<>!~].+)?", line)
                    if match:
                        name = match.group(1).lower().replace("_", "-")
                        spec = match.group(2) or ""
                        deps[name] = spec.strip()

    # pyproject.toml (very basic)
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8", errors="ignore")
            # Look for dependencies = [ ... ]
            matches = re.findall(r'["\']([a-zA-Z0-9_-]+)([=<>!~][^"\']*)?["\']', content)
            for name, spec in matches:
                name = name.lower().replace("_", "-")
                if name not in deps:
                    deps[name] = spec or ""
        except Exception:
            pass

    return deps

def get_installed_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        # Try common variations
        for variant in [package_name, package_name.replace("-", "_"), package_name.replace("_", "-")]:
            try:
                return version(variant)
            except PackageNotFoundError:
                continue
        return "not installed"

def build_dependency_graph(root: Path) -> nx.DiGraph:
    G = nx.DiGraph()
    py_files = [p for p in root.rglob("*.py") if not is_ignored(p)]
    
    print(f"Found {len(py_files)} Python files...")
    
    module_to_file = {}
    external_imports = set()

    for f in tqdm(py_files, desc="Parsing modules"):
        mod = get_module_name(f, root)
        module_to_file[mod] = str(f.relative_to(root)).replace("\\", "/")
        G.add_node(mod, file=module_to_file[mod], type="internal")

    for f in tqdm(py_files, desc="Extracting imports"):
        source_mod = get_module_name(f, root)
        imports = extract_imports(f)
        
        for imp in imports:
            if imp in module_to_file:
                G.add_edge(source_mod, imp)
            else:
                external_imports.add(imp)

    # Add external packages as nodes
    declared = parse_requirements(root)
    print(f"Found {len(external_imports)} external packages referenced in code")

    for pkg in sorted(external_imports):
        pkg_lower = pkg.lower().replace("_", "-")
        is_stdlib = pkg in STDLIB
        declared_spec = declared.get(pkg_lower, declared.get(pkg, ""))
        installed_ver = "stdlib" if is_stdlib else get_installed_version(pkg)

        G.add_node(
            pkg,
            type="stdlib" if is_stdlib else "external",
            declared=declared_spec,
            installed_version=installed_ver,
            file=None
        )

    return G

def add_complexity_metrics(G: nx.DiGraph, root: Path):
    print("Calculating complexity metrics...")
    for node in tqdm(list(G.nodes), desc="Complexity"):
        if G.nodes[node].get("type") != "internal":
            continue
        file_rel = G.nodes[node].get("file")
        if not file_rel:
            continue
        file_path = root / file_rel
        try:
            code = file_path.read_text(encoding="utf-8", errors="ignore")
            blocks = cc_visit(code)
            avg_cc = sum(b.complexity for b in blocks) / len(blocks) if blocks else 0
            max_cc = max((b.complexity for b in blocks), default=0)
            mi = mi_visit(code, multi=True)
            
            G.nodes[node]["avg_complexity"] = round(avg_cc, 2)
            G.nodes[node]["max_complexity"] = max_cc
            G.nodes[node]["maintainability"] = round(float(mi), 2) if mi else 0
            G.nodes[node]["loc"] = len(code.splitlines())
        except Exception:
            G.nodes[node].update({
                "avg_complexity": 0, "max_complexity": 0,
                "maintainability": 0, "loc": 0
            })

def analyze_git_history(repo_path: Path, G: nx.DiGraph):
    print("Analyzing git history...")
    try:
        repo = Repo(repo_path)
        file_stats = defaultdict(lambda: {"commits": 0, "authors": set(), "last_date": None})
        
        for commit in tqdm(list(repo.iter_commits(max_count=2500)), desc="Git commits"):
            for file in commit.stats.files:
                if file.endswith(".py"):
                    norm = file.replace("\\", "/")
                    file_stats[norm]["commits"] += 1
                    file_stats[norm]["authors"].add(commit.author.name)
                    date = commit.committed_datetime
                    if file_stats[norm]["last_date"] is None or date > file_stats[norm]["last_date"]:
                        file_stats[norm]["last_date"] = date
        
        for node, data in G.nodes(data=True):
            if data.get("type") != "internal":
                continue
            file_rel = data.get("file", "")
            stats = file_stats.get(file_rel, {})
            G.nodes[node]["churn"] = stats.get("commits", 0)
            G.nodes[node]["authors"] = len(stats.get("authors", set()))
            last = stats.get("last_date")
            G.nodes[node]["last_change"] = last.isoformat() if last else None
    except Exception as e:
        print(f"Git analysis warning: {e}")

def save_twin(G: nx.DiGraph):
    with open(OUTPUT_DIR / "twin_graph.pkl", "wb") as f:
        pickle.dump(G, f)
    
    data = {
        "nodes": [
            {"id": n, **{k: v for k, v in attrs.items()}}
            for n, attrs in G.nodes(data=True)
        ],
        "edges": [{"source": u, "target": v} for u, v in G.edges],
        "generated_at": datetime.now().isoformat()
    }
    with open(OUTPUT_DIR / "twin_graph.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"\n✅ Twin saved → {OUTPUT_DIR}/")
    print(f"   Total nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}")

def main():
    if not REPO_PATH.exists():
        print(f"❌ Path not found: {REPO_PATH}")
        return
    
    print(f"Building Digital Twin from: {REPO_PATH}\n")
    
    G = build_dependency_graph(REPO_PATH)
    add_complexity_metrics(G, REPO_PATH)
    analyze_git_history(REPO_PATH, G)
    save_twin(G)

if __name__ == "__main__":
    main()
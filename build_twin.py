#!/usr/bin/env python3
"""
Software Digital Twin PoC - Starter Kit
Builds dependency graph + complexity + git metrics from a local cloned repo.
Works on Windows + Python 3.11
"""

import ast
import os
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

# ================== CONFIG ==================
REPO_PATH = Path(r"D:\GIT\airflow\airflow-main")  # <-- CHANGE THIS
OUTPUT_DIR = Path("twin_output")
IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", 
               "dist", "build", ".idea", ".vscode", "tests", "test"}
# ============================================

OUTPUT_DIR.mkdir(exist_ok=True)

def is_ignored(path: Path) -> bool:
    return any(part in IGNORE_DIRS for part in path.parts)

def get_module_name(file_path: Path, root: Path) -> str:
    """Convert file path to dotted module name"""
    rel = file_path.relative_to(root)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else rel.stem

def extract_imports(file_path: Path) -> set[str]:
    """Extract imported modules using AST (static)"""
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

def build_dependency_graph(root: Path) -> nx.DiGraph:
    """Build module-level dependency graph"""
    G = nx.DiGraph()
    py_files = [p for p in root.rglob("*.py") if not is_ignored(p)]
    
    print(f"Found {len(py_files)} Python files...")
    
    module_to_file = {}
    for f in tqdm(py_files, desc="Parsing modules"):
        mod = get_module_name(f, root)
        module_to_file[mod] = str(f.relative_to(root))
        G.add_node(mod, file=module_to_file[mod], type="module")
    
    for f in tqdm(py_files, desc="Extracting imports"):
        source_mod = get_module_name(f, root)
        imports = extract_imports(f)
        
        for imp in imports:
            # Only keep internal dependencies
            if imp in module_to_file or any(m.startswith(imp + ".") for m in module_to_file):
                # Try exact or top-level match
                target = imp if imp in module_to_file else next(
                    (m for m in module_to_file if m.startswith(imp + ".")), None
                )
                if target and target != source_mod:
                    G.add_edge(source_mod, target)
    
    return G

def add_complexity_metrics(G: nx.DiGraph, root: Path):
    """Add cyclomatic complexity and maintainability index"""
    print("Calculating complexity metrics...")
    for node in tqdm(G.nodes, desc="Complexity"):
        file_rel = G.nodes[node].get("file")
        if not file_rel:
            continue
        file_path = root / file_rel
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
            
            # Cyclomatic complexity
            blocks = cc_visit(code)
            avg_cc = sum(b.complexity for b in blocks) / len(blocks) if blocks else 0
            max_cc = max((b.complexity for b in blocks), default=0)
            
            # Maintainability Index
            mi = mi_visit(code, multi=True)
            
            G.nodes[node]["avg_complexity"] = round(avg_cc, 2)
            G.nodes[node]["max_complexity"] = max_cc
            G.nodes[node]["maintainability"] = round(mi, 2) if isinstance(mi, (int, float)) else 0
            G.nodes[node]["loc"] = len(code.splitlines())
        except Exception:
            G.nodes[node]["avg_complexity"] = 0
            G.nodes[node]["max_complexity"] = 0
            G.nodes[node]["maintainability"] = 0
            G.nodes[node]["loc"] = 0

def analyze_git_history(repo_path: Path, G: nx.DiGraph):
    """Add churn, authors, last change from git"""
    print("Analyzing git history...")
    try:
        repo = Repo(repo_path)
        
        # File-level stats
        file_stats = defaultdict(lambda: {"commits": 0, "authors": set(), "last_date": None})
        
        for commit in tqdm(list(repo.iter_commits(max_count=2000)), desc="Git commits"):
            for file in commit.stats.files:
                if file.endswith(".py"):
                    file_stats[file]["commits"] += 1
                    file_stats[file]["authors"].add(commit.author.name)
                    date = commit.committed_datetime
                    if (file_stats[file]["last_date"] is None or 
                        date > file_stats[file]["last_date"]):
                        file_stats[file]["last_date"] = date
        
        # Map back to modules
        for node in G.nodes:
            file_rel = G.nodes[node].get("file", "")
            stats = file_stats.get(file_rel.replace("\\", "/"), {})
            G.nodes[node]["churn"] = stats.get("commits", 0)
            G.nodes[node]["authors"] = len(stats.get("authors", set()))
            G.nodes[node]["last_change"] = (
                stats["last_date"].isoformat() if stats.get("last_date") else None
            )
            
    except Exception as e:
        print(f"Git analysis warning: {e}")

def save_twin(G: nx.DiGraph):
    """Save graph in multiple formats"""
    # NetworkX pickle
    with open(OUTPUT_DIR / "twin_graph.pkl", "wb") as f:
        pickle.dump(G, f)
    
    # JSON (nodes + edges)
    data = {
        "nodes": [
            {"id": n, **{k: v for k, v in G.nodes[n].items() if k != "file"}}
            for n in G.nodes
        ],
        "edges": [{"source": u, "target": v} for u, v in G.edges],
        "generated_at": datetime.now().isoformat()
    }
    with open(OUTPUT_DIR / "twin_graph.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    # Simple GraphML
    nx.write_graphml(G, OUTPUT_DIR / "twin_graph.graphml")
    
    print(f"\n✅ Twin saved to {OUTPUT_DIR}/")
    print(f"   Nodes: {G.number_of_nodes()} | Edges: {G.number_of_edges()}")

def main():
    if not REPO_PATH.exists():
        print(f"❌ Repo path does not exist: {REPO_PATH}")
        print("Please edit REPO_PATH in the script.")
        return
    
    print(f"Building Digital Twin from: {REPO_PATH}")
    
    G = build_dependency_graph(REPO_PATH)
    add_complexity_metrics(G, REPO_PATH)
    analyze_git_history(REPO_PATH, G)
    save_twin(G)
    
    # Quick summary
    print("\n=== Quick Insights ===")
    high_cc = sorted(
        [(n, d.get("max_complexity", 0)) for n, d in G.nodes(data=True)],
        key=lambda x: x[1], reverse=True
    )[:5]
    print("Highest complexity modules:")
    for mod, cc in high_cc:
        print(f"  {mod}: {cc}")
    
    high_churn = sorted(
        [(n, d.get("churn", 0)) for n, d in G.nodes(data=True)],
        key=lambda x: x[1], reverse=True
    )[:5]
    print("\nHighest churn modules:")
    for mod, c in high_churn:
        print(f"  {mod}: {c} commits")

if __name__ == "__main__":
    main()
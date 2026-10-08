#!/usr/bin/env python3
"""
Software Digital Twin - Interactive Dashboard (Updated)
Supports searching internal modules + external packages + stdlib
"""

import streamlit as st
import networkx as nx
import pickle
import pandas as pd
from pathlib import Path
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile
import os

st.set_page_config(
    page_title="Software Digital Twin",
    page_icon="🧠",
    layout="wide"
)

st.title("🧠 Software Digital Twin")
st.caption("Dependency graph + complexity + git metrics + external packages")

GRAPH_PATH = Path("twin_output/twin_graph.pkl")

@st.cache_resource
def load_graph():
    with open(GRAPH_PATH, "rb") as f:
        return pickle.load(f)

if not GRAPH_PATH.exists():
    st.error("❌ Graph not found. Please run `python build_twin.py` first.")
    st.stop()

G = load_graph()

# ========== SIDEBAR ==========
st.sidebar.header("Controls")

search_term = st.sidebar.text_input(
    "🔍 Search modules & packages",
    placeholder="e.g. sqlalchemy, shlex, pandas, utils..."
)

st.sidebar.markdown("---")

min_complexity = st.sidebar.slider("Min complexity (internal only)", 0, 50, 0)
min_churn = st.sidebar.slider("Min churn (internal only)", 0, 100, 0)
show_only_external = st.sidebar.checkbox("Show only external / stdlib packages", value=False)
show_graph = st.sidebar.checkbox("Show interactive graph", value=False)

st.sidebar.markdown("---")
st.sidebar.info("Tip: Type part of a package name to search both internal modules and external dependencies.")

# ========== OVERVIEW METRICS ==========
col1, col2, col3, col4 = st.columns(4)

total_nodes = G.number_of_nodes()
internal_count = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "internal")
external_count = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "external")
stdlib_count = sum(1 for _, d in G.nodes(data=True) if d.get("type") == "stdlib")

col1.metric("Total Nodes", total_nodes)
col2.metric("Internal Modules", internal_count)
col3.metric("External Packages", external_count)
col4.metric("Stdlib", stdlib_count)

st.divider()

# ========== BUILD FILTERED RESULTS ==========
rows = []

for node, data in G.nodes(data=True):
    node_type = data.get("type", "unknown")

    # Filter: show only external/stdlib
    if show_only_external and node_type == "internal":
        continue

    # Filter: complexity & churn (only apply to internal modules)
    if node_type == "internal":
        if data.get("max_complexity", 0) < min_complexity:
            continue
        if data.get("churn", 0) < min_churn:
            continue

    # Search filter
    if search_term and search_term.lower() not in node.lower():
        continue

    rows.append({
        "Name": node,
        "Type": node_type,
        "Installed Version": data.get("installed_version", ""),
        "Declared Spec": data.get("declared", ""),
        "Max Complexity": data.get("max_complexity", ""),
        "Avg Complexity": data.get("avg_complexity", ""),
        "Churn": data.get("churn", ""),
        "LOC": data.get("loc", ""),
        "Authors": data.get("authors", ""),
        "Last Change": (data.get("last_change") or "")[:10]
    })

# ========== DISPLAY TABLE ==========
if search_term:
    st.subheader(f"Search results for: `{search_term}`")
else:
    st.subheader("Modules & Packages")

if rows:
    df = pd.DataFrame(rows)

    # Better sorting
    if search_term:
        # When searching, show external/stdlib first
        type_order = {"external": 0, "stdlib": 1, "internal": 2, "unknown": 3}
        df["_sort"] = df["Type"].map(type_order)
        df = df.sort_values(["_sort", "Name"]).drop(columns=["_sort"])
    else:
        df = df.sort_values(["Type", "Max Complexity"], ascending=[True, False])

    st.dataframe(df, use_container_width=True, height=520)
    st.caption(f"Showing {len(df)} items")
else:
    st.info("No matching modules or packages found. Try a different search term or adjust the filters.")

# ========== INTERACTIVE GRAPH ==========
if show_graph:
    st.divider()
    st.subheader("Dependency Graph (top connected nodes)")

    # Limit size for performance
    top_nodes = [n for n, d in sorted(G.degree, key=lambda x: x[1], reverse=True)[:60]]
    subG = G.subgraph(top_nodes).copy()

    net = Network(
        height="650px",
        width="100%",
        directed=True,
        bgcolor="#ffffff",
        font_color="#000000"
    )
    net.barnes_hut()
    net.from_nx(subG)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        with open(tmp.name, "r", encoding="utf-8") as f:
            html_content = f.read()
        components.html(html_content, height=670, scrolling=True)

    os.unlink(tmp.name)

st.sidebar.markdown("---")
st.sidebar.caption("Software Digital Twin PoC")
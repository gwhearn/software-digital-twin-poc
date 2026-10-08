#!/usr/bin/env python3
"""
Simple Digital Twin Dashboard
"""

import streamlit as st
import networkx as nx
import pickle
import pandas as pd
from pathlib import Path
from pyvis.network import Network
import streamlit.components.v1 as components

st.set_page_config(page_title="Software Digital Twin", layout="wide")
st.title("🧠 Software Digital Twin PoC")

GRAPH_PATH = Path("twin_output/twin_graph.pkl")

@st.cache_resource
def load_graph():
    with open(GRAPH_PATH, "rb") as f:
        return pickle.load(f)

if not GRAPH_PATH.exists():
    st.error("Run `python build_twin.py` first!")
    st.stop()

G = load_graph()

# Sidebar filters
st.sidebar.header("Filters")
min_complexity = st.sidebar.slider("Min max-complexity", 0, 50, 0)
min_churn = st.sidebar.slider("Min churn (commits)", 0, 100, 0)

# Metrics overview
col1, col2, col3, col4 = st.columns(4)
col1.metric("Modules", G.number_of_nodes())
col2.metric("Dependencies", G.number_of_edges())
col3.metric("Avg Complexity", 
            round(sum(d.get("avg_complexity", 0) for _, d in G.nodes(data=True)) / max(G.number_of_nodes(), 1), 2))
col4.metric("Total Churn", sum(d.get("churn", 0) for _, d in G.nodes(data=True)))

# Table of modules
st.subheader("Module Overview")
rows = []
for n, d in G.nodes(data=True):
    if d.get("max_complexity", 0) >= min_complexity and d.get("churn", 0) >= min_churn:
        rows.append({
            "Module": n,
            "Max CC": d.get("max_complexity", 0),
            "Avg CC": d.get("avg_complexity", 0),
            "Maintainability": d.get("maintainability", 0),
            "LOC": d.get("loc", 0),
            "Churn": d.get("churn", 0),
            "Authors": d.get("authors", 0),
            "Last Change": d.get("last_change", "")[:10] if d.get("last_change") else ""
        })

df = pd.DataFrame(rows).sort_values("Max CC", ascending=False)
st.dataframe(df, use_container_width=True)

# Interactive graph (limited size for performance)
st.subheader("Dependency Graph (top modules)")
if st.button("Generate Interactive Graph"):
    # Take top N by degree or complexity
    top_nodes = sorted(G.degree, key=lambda x: x[1], reverse=True)[:40]
    sub = G.subgraph([n for n, _ in top_nodes])
    
    net = Network(height="600px", width="100%", directed=True, notebook=False)
    net.from_nx(sub)
    net.save_graph("twin_output/graph.html")
    
    with open("twin_output/graph.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=620)
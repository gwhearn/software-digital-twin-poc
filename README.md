# Software Digital Twin PoC (v1)

A simple proof-of-concept that builds a **software digital twin** from a local Git repository (GitHub, Bitbucket, or any Git repo).

It analyzes your Python codebase and creates:

- A module-level dependency graph
- Cyclomatic complexity & maintainability metrics
- Git history insights (churn, authors, last change)
- An interactive Streamlit dashboard

---

## Features (v1)

- Static dependency graph of internal Python modules
- Cyclomatic complexity (average + max) per module
- Maintainability Index
- Lines of Code (LOC)
- Git churn (number of commits touching each file)
- Number of authors per module
- Last modification date
- Interactive dashboard with filtering
- Exports: `.pkl`, `.json`, `.graphml`

> **Note**: This first version only analyzes **internal** project modules.  
> It does **not** track external packages (e.g. `sqlalchemy`, `requests`) or their versions.

---

## Requirements

- Python 3.11+
- Git
- Windows / macOS / Linux (tested on Windows + Git Bash)

---

## Quick Start

### 1. Clone this project (or create the files)

```bash
mkdir software-digital-twin-poc
cd software-digital-twin-poc


2. Create & activate virtual environmentGit Bash / Linux / macOS:bash

python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
# source .venv/bin/activate       # Linux/macOS

PowerShell:powershell

python -m venv .venv
.\.venv\Scripts\Activate.ps1

3. Install dependenciesbash

pip install -r requirements.txt

4. Configure the target repositoryOpen build_twin.py and change this line:python

REPO_PATH = Path(r"C:\path\to\your\cloned\repo")

Use the full path to the repository you already cloned.5. Build the Digital Twinbash

python build_twin.py

6. Launch the dashboardbash

streamlit run dashboard.py

The dashboard will open in your browser.Project Structure

software-digital-twin-poc/
├── build_twin.py          # Main analysis script
├── dashboard.py           # Streamlit dashboard
├── requirements.txt
├── twin_output/           # Generated after running build_twin.py
│   ├── twin_graph.pkl
│   ├── twin_graph.json
│   └── twin_graph.graphml
└── README.md

Output FilesFile
Description
twin_graph.pkl
NetworkX graph (used by the dashboard)
twin_graph.json
Human-readable nodes + edges
twin_graph.graphml
Can be opened in tools like Gephi / yEd

Limitations of v1Only analyzes Python files
Only tracks internal modules (no external packages like sqlalchemy, shlex, etc.)
No version information for dependencies
No search functionality in the dashboard
Graph visualization is limited to top connected modules for performance

Next Steps / Possible ImprovementsTrack external packages and installed versions
Add search functionality
Support for more languages
Better visualization of high-risk modules (high complexity + high churn)
Integration with Bitbucket / GitHub APIs for Pull Requests

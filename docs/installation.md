# Installation

## Core Installation

```bash
# Core: Python standard library only
pip install lithos
```

Requires Python 3.10+.

## Optional Extras

Optional features require additional dependencies. Install them with:

```bash
pip install "lithos[excel]"     # XLSX via openpyxl (otherwise stdlib writer is used)
pip install "lithos[plots]"     # PNG PRISMA diagrams via matplotlib
pip install "lithos[docx]"      # DOCX reports via python-docx
pip install "lithos[yaml]"      # YAML configuration files
pip install "lithos[semantic]"  # Local semantic embeddings via sentence-transformers
pip install "lithos[all]"       # All of the above
```

## Development Installation

```bash
git clone <repository>
cd lithos
python -m venv .venv && . .venv/bin/activate
pip install -e ".[all]"
```

## Verifying Installation

```bash
lithos --version
lithos --about
lithos config
```
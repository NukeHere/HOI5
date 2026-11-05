"""Synchronize the symbol inventory and count reviewed C++ ports."""

import argparse
import ast
from collections import Counter
import csv
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "H5_CPP" / "port_progress.tsv"
FIELDS = ("python", "line", "kind", "symbol", "occurrence", "status", "cpp", "evidence")
STATES = ("ported", "partial", "missing", "unreviewed", "excluded_bot", "excluded_tool")
TOOLS = {"export_cpp_fixture.py", "headless_simulation.py", "simulate_ai.py"}


class Symbols(ast.NodeVisitor):
    def __init__(self):
        self.scope = []
        self.rows = []
        self.counts = Counter()

    def definition(self, node, kind):
        name = ".".join([*self.scope, node.name])
        self.counts[name] += 1
        self.rows.append((node.lineno, kind, name, self.counts[name]))
        self.scope.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.scope.pop()

    def visit_ClassDef(self, node):
        self.definition(node, "class")

    def visit_FunctionDef(self, node):
        self.definition(node, "function")

    visit_AsyncFunctionDef = visit_FunctionDef


def source_files():
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "H5_Python"],
        cwd=ROOT,
    ).decode("utf-8").split("\0")
    return sorted({path for path in paths if path.endswith(".py") and (ROOT / path).is_file()})


def default_status(path):
    relative = Path(path).relative_to("H5_Python")
    if relative.parts[0] in {"tests", ".codex-work"} or relative.name in TOOLS:
        return "excluded_tool"
    if relative.name.startswith("ai_"):
        return "excluded_bot"
    return "unreviewed"


def identity(row):
    return row["python"], row["symbol"], row["occurrence"]


def read_registry():
    if not REGISTRY.exists():
        return []
    with REGISTRY.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def synchronize(previous):
    entries = {identity(row): row for row in previous}
    if len(entries) != len(previous):
        raise SystemExit("Duplicate Python symbol identities in registry")
    for path in source_files():
        visitor = Symbols()
        source = (ROOT / path).read_text(encoding="utf-8-sig")
        visitor.visit(ast.parse(source, filename=path))
        for line, kind, symbol, occurrence in visitor.rows:
            row = dict(python=path, line=str(line), kind=kind, symbol=symbol, occurrence=str(occurrence),
                       status=default_status(path), cpp="", evidence="")
            if old := entries.get(identity(row)):
                for field in ("status", "cpp", "evidence"):
                    row[field] = old[field]
            yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="Refresh Python symbols while preserving review fields")
    args = parser.parse_args()
    saved = read_registry()
    rows = list(synchronize(saved))
    for row in rows:
        if row["status"] not in STATES:
            raise SystemExit(f"Unknown status for {identity(row)}: {row['status']}")
        if row["status"] in {"ported", "partial"} and not (row["cpp"] and row["evidence"]):
            raise SystemExit(f"Missing C++ reference or evidence for {identity(row)}")
    if args.sync:
        with REGISTRY.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, FIELDS, delimiter="\t", lineterminator="\n", quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)
    elif rows != saved:
        raise SystemExit("Registry is stale. Run python H5_CPP/port_progress.py --sync")
    counts = Counter(row["status"] for row in rows)
    total = len(rows) - counts["excluded_bot"] - counts["excluded_tool"]
    print(f"Confirmed progress: {counts['ported']}/{total} = {100*counts['ported']/max(1,total):.2f}%")
    print(f"Inventory: {len(rows)} symbols")
    for state in STATES:
        print(f"{state}: {counts[state]}")


if __name__ == "__main__":
    main()

"""Keep generated logs within a shared size budget, pruning whole runs."""
from pathlib import Path
import shutil


LOG_BUDGET_BYTES = 100 * 1024 * 1024
GENERATED_DIRS = ("runtime", "diagnostics", "simulations")


def prune_logs(root, budget=LOG_BUDGET_BYTES, dry_run=False):
    root = Path(root).absolute()
    if root.resolve() != root:
        return []
    if not root.is_dir():
        return []
    total = sum(p.stat().st_size for p in root.iterdir() if p.is_file())
    candidates = []
    for name in GENERATED_DIRS:
        folder = root / name
        if not folder.is_dir() or folder.resolve().parent != root:
            continue
        groups = {}
        for path in folder.iterdir():
            if path.is_symlink() or path.resolve().parent != folder:
                continue
            key = path.name.split(".", 1)[0] if name == "runtime" else path.name
            groups.setdefault(key, []).append(path)
        recent_runtime = set(sorted((key for key in groups if key[:1].isdigit()), reverse=True)[:10])
        for key, paths in groups.items():
            files = [file for path in paths for file in (path.rglob("*") if path.is_dir() else (path,))
                     if file.is_file() and file.resolve().is_relative_to(root)]
            size = sum(file.stat().st_size for file in files)
            total += size
            if name == "runtime" and (key == "latest" or key in recent_runtime):
                continue
            if name != "runtime" and (not all(path.is_dir() for path in paths)
                                      or any(file.suffix in {".py", ".ps1", ".md"} for file in files)):
                continue
            candidates.append((max((file.stat().st_mtime for file in files), default=0), paths, size))
    removed = []
    for _, paths, size in sorted(candidates, key=lambda entry: entry[0]):
        if total <= budget:
            break
        for path in paths:
            if path.is_symlink() or path.resolve().parent not in (root / name for name in GENERATED_DIRS):
                continue
            if not dry_run:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            removed.append(path)
        total -= size
    return removed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    for removed_path in prune_logs(Path(__file__).resolve().parent / "logs", dry_run=args.dry_run):
        print(removed_path)

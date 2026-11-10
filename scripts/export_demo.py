"""Write deterministic synthetic CSVs for local import testing, never real student data."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.demo import demo_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "demo-input")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results, curriculum, metadata = demo_files()
    (args.output / "results.csv").write_bytes(results)
    (args.output / "curriculum.csv").write_bytes(curriculum)
    (args.output / "metadata.json").write_text(metadata, encoding="utf-8")
    print(f"Synthetic demo: 120 students, 6 topics, 1440 results. Files: {args.output.resolve()}")

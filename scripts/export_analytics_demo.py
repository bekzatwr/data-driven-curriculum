"""Run from repository root: python -m scripts.export_analytics_demo --output-dir PATH."""
import argparse
from pathlib import Path
from analytics.demo import demo_files


def main():
    parser = argparse.ArgumentParser(description='Export the explicitly synthetic Toni demo CSVs.')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results, curriculum, metadata = demo_files()
    (args.output_dir / 'results.csv').write_bytes(results)
    (args.output_dir / 'curriculum.csv').write_bytes(curriculum)
    (args.output_dir / 'metadata.json').write_text(metadata + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

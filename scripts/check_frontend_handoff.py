"""Check source prerequisites only; never claim a build/browser test was executed."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default='web')
    args = parser.parse_args()
    root = Path(args.directory)
    blockers = []
    for name in ('package.json', 'package-lock.json', 'tsconfig.json'):
        if not (root / name).is_file():
            blockers.append('Missing ' + str(root / name))
    if not (root / 'src').is_dir():
        blockers.append('Missing React source directory ' + str(root / 'src'))
    if (root / 'package.json').is_file():
        try:
            package = json.loads((root / 'package.json').read_text(encoding='utf-8-sig'))
            for name in ('test', 'typecheck', 'lint', 'build'):
                if not package.get('scripts', {}).get(name):
                    blockers.append('Missing npm script: ' + name)
            if 'react' not in {**package.get('dependencies', {}), **package.get('devDependencies', {})}:
                blockers.append('React dependency not declared')
        except (ValueError, OSError, AttributeError, TypeError) as exc:
            blockers.append('Invalid package.json: ' + str(exc))
    print(json.dumps({'source_prerequisites_met': not blockers, 'blockers': blockers,
                      'tests_typecheck_lint_build': 'not_run', 'browser_and_mobile': 'not_run'}, indent=2))
    return 2 if blockers else 0


if __name__ == '__main__':
    raise SystemExit(main())

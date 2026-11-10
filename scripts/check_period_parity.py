"""Compare Python allocator with the actual installed frontend TypeScript module.

Usage: python scripts/check_period_parity.py ../combined-checkout/web
Run npm ci in that web directory first. No browser or network calls are made.
"""
import json
from pathlib import Path
import random
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from planner.period import allocate_period


def main():
    web = Path(sys.argv[1]).resolve()
    rng = random.Random(20261110)
    cases = []
    for _ in range(200):
        items = []
        for i in range(rng.randint(1, 12)):
            items.append(dict(topic_id=str(i), topic_name=str(i), topic_order=i,
                              current_hours=rng.randint(1, 20), min_hours=rng.randint(0, 1),
                              max_hours=25, importance=rng.randint(1, 3), is_locked=rng.choice([True, False]),
                              mean_post_pct=rng.choice([None, 0, 50, 69.999, 70, 79.999, 80, 100])))
        rng.shuffle(items)
        cases.append(items)
    javascript = r'''
const fs = require('fs'), path = require('path'), vm = require('vm');
const web = process.argv[1];
const ts = require(path.join(web, 'node_modules/typescript'));
function load(file) {
  const source = fs.readFileSync(file, 'utf8');
  const js = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
  const exports = {};
  vm.runInNewContext(js, {exports, require: (name) => load(path.resolve(path.dirname(file), name + '.ts'))});
  return exports;
}
const {buildPeriodPlan} = load(path.join(web, 'src/lib/periodPlan.ts'));
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(cases.map(items => buildPeriodPlan(items, items.reduce((s, i) => s + i.current_hours, 0), 70, 80))));
'''
    result = subprocess.run(['node', '-e', javascript, str(web)], input=json.dumps(cases),
                            text=True, capture_output=True, check=True)
    expected = json.loads(result.stdout)
    fields = ('topic_id', 'topic_name', 'topic_order', 'current_hours', 'min_hours', 'max_hours', 'importance', 'is_locked')
    for index, (items, frontend) in enumerate(zip(cases, expected)):
        actual = allocate_period(items, [{k: i[k] for k in fields} for i in items])
        assert {i['topic_id']: i['proposed_hours'] for i in actual['items']} == frontend['hours'], index
        assert frontend['overflow'] == frontend['leftover'] == 0
    print(f'{len(cases)} real TypeScript/Python parity cases passed')


if __name__ == '__main__':
    main()

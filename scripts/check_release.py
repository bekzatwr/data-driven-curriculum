"""Read-only release precheck; never deploys, seeds, imports or saves a plan.

HTTPS uses the default certificate/hostname verification. Redirects are rejected,
so an HTTPS URL cannot silently downgrade to HTTP or another origin.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler

MAX_RESPONSE = 4 * 1024 * 1024


class CheckFailure(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CheckFailure('Unexpected redirect; use the final canonical service URL')


class BuildHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = False
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.root |= attrs.get('id') == 'root'
        if tag == 'script' and attrs.get('type') == 'module' and attrs.get('src'):
            self.scripts.append(attrs['src'])


def check_release(base_url, *, mode='public', require_https=False, plan_id=None, opener=None, timeout=15,
                  allow_public_ai=False):
    base = base_url.rstrip('/')
    result = {'technical_precheck_passed': False, 'base_url': '<invalid URL withheld>', 'mode': mode,
              'plan_id': plan_id, 'https_verified': False, 'blockers': [], 'observed': {},
              'still_required': ['team review', 'browser/mobile acceptance',
                                 'operator restart and backup/restore evidence',
                                 'hosting/budget approval if paid']}
    try:
        parsed = urlsplit(base)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path):
            result['base_url'] = '<invalid URL withheld>'
            raise CheckFailure('Use a service origin without credentials, query or path')
        if require_https and parsed.scheme != 'https':
            raise CheckFailure('HTTPS URL required')
        result['base_url'] = base
        if mode not in {'public', 'local'} or not 0 < timeout <= 60:
            raise CheckFailure('Invalid mode or timeout')
        if plan_id is not None and not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', plan_id):
            result['plan_id'] = '<invalid ID withheld>'
            raise CheckFailure('Invalid plan ID')
        opener = opener or build_opener(NoRedirect())

        def read(path, kind='json'):
            with opener.open(base + path, timeout=timeout) as response:
                if response.geturl() != base + path:
                    raise CheckFailure('Unexpected response URL')
                data = response.read(MAX_RESPONSE + 1)
                if len(data) > MAX_RESPONSE:
                    raise CheckFailure('Response exceeds precheck size limit')
                media = response.headers.get('Content-Type', '').split(';')[0].lower()
                valid = {'json': {'application/json'}, 'html': {'text/html'},
                         'js': {'application/javascript', 'text/javascript'}, 'csv': {'text/csv'}}
                if media not in valid[kind]:
                    raise CheckFailure('Unexpected content type for ' + path)
                return json.loads(data) if kind == 'json' else data

        health, capabilities, schema = (read('/api/health'), read('/api/capabilities'), read('/openapi.json'))
        public = mode == 'public'
        blockers = result['blockers']
        if health.get('database') != 'ok':
            blockers.append('database health')
        if health.get('read_only_demo') is not public or capabilities.get('mode') != ('read_only_demo' if public else 'local'):
            blockers.append('mode does not match ' + mode)
        features = capabilities['features']
        for feature in ('csv_import', 'import_preview', 'package_restore', 'plan_save'):
            if features.get(feature) is not (not public):
                blockers.append('write policy: ' + feature)
        if public:
            # --allow-public-ai: the operator enabled AI_PUBLIC_DEMO on purpose; writes stay strict.
            ai_features = () if allow_public_ai else ('ai_explain',)
            if not allow_public_ai and read('/api/ai/status').get('configured') is not False:
                blockers.append('AI must be offline in public demo')
            for feature in ('comments_write', *ai_features):
                if features.get(feature) is not False:
                    blockers.append('public policy: ' + feature)
            if allow_public_ai:
                result['observed']['public_ai_explain'] = features.get('ai_explain') is True
        for feature in ('analytics', 'textbook_comparison', 'plan_preview', 'plan_report', 'plan_csv'):
            if features.get(feature) is not True:
                blockers.append('feature: ' + feature)
        for path in ('/api/datasets/{dataset_id}/overview', '/api/datasets/{dataset_id}/topics/{topic_id}',
                     '/api/datasets/{dataset_id}/comparison'):
            if 'get' not in schema['paths'].get(path, {}):
                blockers.append('GET ' + path)
        html = read('/', 'html')
        build = BuildHTML()
        build.feed(html.decode('utf-8'))
        if not build.root or not build.scripts or b'packaging probe only' in html.lower():
            raise CheckFailure('Real React build is missing')
        for asset in build.scripts:
            url = urlsplit(urljoin(base + '/', asset))
            if (url.scheme, url.netloc) != (parsed.scheme, parsed.netloc) or url.query or url.fragment:
                raise CheckFailure('Frontend module must use this service origin')
            if not read(url.path, 'js'):
                raise CheckFailure('Empty frontend module')
        result['observed']['frontend_sha256'] = hashlib.sha256(html).hexdigest()
        if plan_id:
            path = '/api/plans/' + plan_id
            plan, csv = read(path), read(path + '/export.csv', 'csv')
            if plan.get('plan_id') != plan_id or (public and plan.get('is_demo') is not True):
                raise CheckFailure('Saved report identity or synthetic-data flag mismatch')
            if not csv.startswith(b'\xef\xbb\xbf'):
                raise CheckFailure('CSV UTF-8 BOM missing')
            if read('/plans/' + plan_id, 'html') != html:
                raise CheckFailure('SPA deep link does not serve the same frontend')
            result['observed'].update({
                'report_sha256': hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
                'csv_sha256': hashlib.sha256(csv).hexdigest(),
                'dataset_id': plan.get('dataset_id'), 'spa_deep_link': True})
        result['https_verified'] = parsed.scheme == 'https'
    except CheckFailure as exc:
        result['blockers'].append(str(exc))
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        # Do not echo remote bodies, signed links, credentials or exception messages.
        result['blockers'].append('HTTP/precheck failure (' + type(exc).__name__ + ')')
    result['technical_precheck_passed'] = not result['blockers']
    return result


def compare_observations(current, previous):
    """Compare saved JSON/CSV before/after an operator-performed restart/restore."""
    if (not previous.get('technical_precheck_passed') or not previous.get('plan_id')
            or any(current.get(key) != previous.get(key) for key in ('base_url', 'mode', 'plan_id'))):
        current['blockers'].append('Baseline must be a successful check of the same origin/mode/plan')
    else:
        for key in ('report_sha256', 'csv_sha256', 'dataset_id'):
            old = previous.get('observed', {}).get(key)
            if not old or current['observed'].get(key) != old:
                current['blockers'].append('Saved report changed or unavailable: ' + key)
    current['technical_precheck_passed'] = not current['blockers']
    current['saved_report_matches_baseline'] = current['technical_precheck_passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080')
    parser.add_argument('--mode', choices=('public', 'local'), default='public')
    parser.add_argument('--require-https', action='store_true')
    parser.add_argument('--plan-id', help='Operator-prepared synthetic report to read')
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--output', type=Path, help='New local JSON evidence file; never overwritten')
    parser.add_argument('--compare-to', type=Path, help='Prior JSON evidence for the same saved plan')
    parser.add_argument('--allow-public-ai', action='store_true',
                        help='Public stand runs with AI_PUBLIC_DEMO=true: AI explanations allowed, writes still forbidden')
    args = parser.parse_args()
    result = check_release(args.base_url, mode=args.mode, require_https=args.require_https,
                           plan_id=args.plan_id, timeout=args.timeout, allow_public_ai=args.allow_public_ai)
    if args.compare_to:
        try:
            compare_observations(result, json.loads(args.compare_to.read_text(encoding='utf-8')))
        except (OSError, ValueError, TypeError, AttributeError):
            result['blockers'].append('Cannot read valid baseline evidence')
            result['technical_precheck_passed'] = False
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['technical_precheck_passed'] else 2)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Render a verified review record as an offline stack explainer and a matching chat summary.

  render_review.py record.json                  render into a new ~/.agent/reviews/<stamp>/
  render_review.py record.json --output DIR     render into a new directory DIR
  render_review.py record.json --check          validate and resolve every citation; write nothing
  render_review.py record.json --check --draft  the same for a partial record (an explorer's fragment)
  render_review.py --example                    print the compact example record
"""

import argparse
import base64
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
from string import Template
import subprocess
import sys
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diagrams  # noqa: E402

SEVERITIES = ('Critical', 'High', 'Medium', 'Low')
SHA = re.compile(r'[0-9a-f]{40}|[0-9a-f]{64}')
IDENTIFIER = re.compile(r'[A-Za-z][A-Za-z0-9_-]*')
REF = re.compile(r'(?:(?P<pr>[A-Za-z][A-Za-z0-9_-]*):)?(?P<path>[^:#@\s][^:#@]*):(?P<line>\d+)'
                 r'(?:-(?P<end>\d+))?(?:#(?P<symbol>[^@]+))?(?:@(?P<at>base|head))?')
ASSETS = Path(__file__).resolve().parents[1] / 'assets'
CLAIMS = ('requirements', 'findings', 'checks', 'dropped')
SECTIONS = (('overview', 'In 60 seconds'), ('journey', 'What changes for users'), ('architecture', 'How it works'),
            ('data', 'Data model'), ('rollout', 'Migrations and rollout'), ('contracts', 'Contracts'),
            ('lifecycle', 'States and jobs'), ('build', 'How the stack is built'), ('decisions', 'Decisions'),
            ('limits', "What this page couldn't confirm"))
PROSE = ('journey', 'architecture', 'data', 'rollout', 'contracts', 'lifecycle')
PLACEMENTS = ('overview', *PROSE)
KINDS = ('graph', 'sequence', 'schema', 'timeline', 'flow', 'table', 'svg')
REASONS = ('behaviour', 'money', 'permissions', 'security', 'data', 'migration', 'deploy order', 'concurrency',
           'contract', 'performance', 'untested')
CELL_BADGES = {'breaking': 'bad', 'removed': 'bad', 'one-way': 'bad', 'additive': 'good', 'new': 'good',
               'reversible': 'good', 'changed': 'warn', 'internal': 'quiet', 'unchanged': 'quiet'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(item, names):
    require(isinstance(item, dict), 'Expected an object')
    for name in names.split():
        require(isinstance(item.get(name), str) and item[name].strip(), f'Missing text field: {name}')


def optional_text(item, names):
    for name in names.split():
        if name in item:
            require(isinstance(item[name], str), f'{name} must be text')


class Problems:
    """Collect every validation failure so one run reports them all."""

    def __init__(self):
        self.messages = []

    def attempt(self, label, action):
        try:
            action()
        except ValueError as error:
            self.messages.append(f'{label}: {error}')

    def raise_if_any(self):
        if self.messages:
            lines = '\n'.join(f'  {n}. {m}' for n, m in enumerate(self.messages, 1))
            raise ValueError(f'{len(self.messages)} problem(s) in the record:\n{lines}')


def safe_url(url):
    if not url:
        return ''
    require(isinstance(url, str), 'URL must be text')
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname and not parsed.username
            and not parsed.password and not any(c.isspace() for c in url), 'Expected an HTTPS citation URL')
    return url


def diagram_data(svg):
    """Accept static drawing primitives only; embed a hand-written figure as an isolated image."""
    require(len(svg) <= 250_000 and '<!DOCTYPE' not in svg.upper() and '<!ENTITY' not in svg.upper(),
            'SVG must be a small static drawing without document declarations')
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as error:
        raise ValueError(f'Invalid SVG: {error}') from error
    namespace = '{http://www.w3.org/2000/svg}'
    tags = {'svg', 'g', 'title', 'desc', 'rect', 'circle', 'ellipse', 'line', 'polyline',
            'polygon', 'path', 'text', 'tspan', 'defs', 'marker'}
    attributes = set(('id viewBox width height x y x1 y1 x2 y2 dx dy cx cy r rx ry d points '
                      'fill fill-opacity stroke stroke-width stroke-opacity stroke-dasharray '
                      'stroke-linecap stroke-linejoin opacity transform font-family font-size '
                      'font-weight font-style text-anchor dominant-baseline letter-spacing '
                      'marker-start marker-mid marker-end markerWidth markerHeight refX refY '
                      'orient markerUnits preserveAspectRatio').split())
    require(root.tag in ('svg', namespace + 'svg'), 'SVG root is required')
    try:
        bounds = [float(n) for n in root.get('viewBox', '').replace(',', ' ').split()]
    except ValueError:
        bounds = []
    require(len(bounds) == 4 and all(abs(n) < 100_000 for n in bounds)
            and bounds[2] > 0 and bounds[3] > 0, 'SVG needs a finite, positive viewBox')
    ids, references = set(), set()
    for node in root.iter():
        tag = node.tag.removeprefix(namespace)
        require(tag in tags, f'Unsupported SVG element: {tag}')
        for key, value in node.attrib.items():
            require(key in attributes, f'Unsupported SVG attribute: {key}')
            if key == 'id':
                require(IDENTIFIER.fullmatch(value) and value not in ids, 'Invalid or duplicate SVG id')
                ids.add(value)
            if key in ('fill', 'stroke', 'marker-start', 'marker-mid', 'marker-end'):
                local = re.fullmatch(r'url\(#([A-Za-z][A-Za-z0-9_-]*)\)', value)
                require(local or re.fullmatch(r'#[0-9A-Fa-f]{3,8}|[A-Za-z]+', value),
                        'SVG paint and markers must use colors or local IDs')
                if local:
                    references.add(local[1])
    require(references <= ids, 'SVG contains a missing local reference')
    if root.tag == 'svg':
        root.set('xmlns', 'http://www.w3.org/2000/svg')
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    data = ET.tostring(root, encoding='utf-8')
    return 'data:image/svg+xml;base64,' + base64.b64encode(data).decode('ascii')


def parse_ref(text, owner, prs):
    """`[pr-id:]path:line[-end][#symbol][@base]` -> an inline code source."""
    match = REF.fullmatch(text.strip())
    require(match, f'Cannot read source reference {text!r}; use path:line[-end][#symbol][@base]')
    pr = match['pr'] or owner
    require(pr in prs, f'Source reference {text!r} names no known PR')
    source = {'kind': 'code', 'pr': pr, 'path': match['path'], 'line': int(match['line'])}
    if match['end']:
        source['end_line'] = int(match['end'])
    if match['symbol']:
        source['symbol'] = match['symbol'].strip()
    if match['at']:
        source['at'] = match['at']
    return source


def as_list(value):
    return value if isinstance(value, list) else [] if value is None else [value]


def normalize(record):
    """Expand the compact authoring form into the explicit record that gets validated and saved."""
    require(isinstance(record, dict), 'The record must be a JSON object')
    for name in ('prs', 'dependencies', 'evidence', 'visuals', 'decisions', *CLAIMS):
        record.setdefault(name, [])
        require(isinstance(record[name], list), f'{name} must be an array (empty is allowed)')
    for name in ('story', 'sections'):
        record.setdefault(name, {})
        require(isinstance(record[name], dict), f'{name} must be an object')
    prs = {pr.get('id'): pr for pr in record['prs'] if isinstance(pr, dict)}
    for pr in prs.values():
        if 'url' not in pr and isinstance(pr.get('repo'), str) and type(pr.get('number')) is int:
            pr['url'] = f"https://github.com/{pr['repo']}/pull/{pr['number']}"
    first_reviewed = next((key for key, pr in prs.items() if pr.get('scope') == 'reviewed'), None)
    expanded = []
    for dep in record['dependencies']:
        if isinstance(dep, dict) and 'chain' in dep:
            chain = dep['chain']
            require(isinstance(chain, list) and len(chain) >= 2, 'A dependency chain needs two or more PR ids')
            for source, target in zip(chain, chain[1:]):
                expanded.append({**{k: v for k, v in dep.items() if k != 'chain'}, 'from': source, 'to': target})
        else:
            expanded.append(dep)
    record['dependencies'] = expanded
    counters, registered = {}, {}

    def register(source, owner, hint):
        """Inline source or shorthand -> id. One object cited from several places registers once."""
        if isinstance(source, str) and ':' in source:
            source = parse_ref(source, owner, prs)
        if not isinstance(source, dict):
            return source
        if id(source) in registered:
            return registered[id(source)]
        counters[hint] = counters.get(hint, 0) + 1
        source.setdefault('pr', owner)
        source.setdefault('id', f'{hint}-e{counters[hint]}')
        registered[id(source)] = source['id']
        record['evidence'].append(source)
        return source['id']

    def cite(item, owner, hint, key='evidence'):
        if key in item or key == 'evidence':
            item[key] = [register(source, owner, hint) for source in as_list(item.get(key))]

    groups = [(name, record[name]) for name in (*CLAIMS, 'dependencies', 'decisions')]
    groups.append(('matters', record['story'].get('matters') if isinstance(record['story'].get('matters'), list) else []))
    for name, items in groups:
        for position, item in enumerate(items, 1):
            if not isinstance(item, dict):
                continue
            owner = item.get('from') if name == 'dependencies' else item.get('pr', first_reviewed)
            hint = item.get('id') if isinstance(item.get('id'), str) else f'{name}-{position}'
            cite(item, owner, hint)
    for position, visual in enumerate(record['visuals'], 1):
        if not isinstance(visual, dict):
            continue
        members = visual.get('prs') if isinstance(visual.get('prs'), list) and visual['prs'] else [first_reviewed]
        owner = members[0]
        hint = visual.get('id') if isinstance(visual.get('id'), str) else f'visual-{position}'
        cite(visual, owner, hint)
        if 'kind' not in visual:
            visual['kind'] = next((kind for key, kind in (('svg', 'svg'), ('lanes', 'flow'), ('nodes', 'graph'),
                                                          ('rows', 'table'), ('participants', 'sequence'),
                                                          ('entities', 'schema'), ('steps', 'timeline'))
                                   if key in visual), 'svg')
        for _, item, _ in diagrams.elements(visual):
            if 'src' in item:
                cite(item, item.get('pr', owner), f'{hint}-s', 'src')
    for source in record['evidence']:
        if not isinstance(source, dict):
            continue
        if 'kind' not in source and 'path' in source:
            source['kind'] = 'code'
        pr = prs.get(source.get('pr'))
        at = source.pop('at', 'head')
        require(at in ('base', 'head'), f"Evidence 'at' must be base or head, not {at!r}")
        if 'revision' not in source and pr and source.get('kind') in ('code', 'command', 'browser') \
                and isinstance(pr.get(at), str):
            source['revision'] = pr[at]
        if 'label' not in source and source.get('kind') == 'code' and isinstance(source.get('path'), str):
            span = str(source.get('line', '')) + (f"-{source['end_line']}" if source.get('end_line') else '')
            source['label'] = f"{source['path']}:{span}"
    return record


def index(items, label, problems):
    result = {}
    for position, item in enumerate(items, 1):
        try:
            fields(item, 'id')
            key = item['id']
            require(IDENTIFIER.fullmatch(key), f'Invalid {label} id: {key}')
            require(key not in result, f'Duplicate {label} id: {key}')
            result[key] = item
        except ValueError as error:
            problems.messages.append(f'{label} {position}: {error}')
    return result


class Annotator:
    """Hover text from cited sources and markers from the findings that point at an element."""
    strict = True

    def __init__(self, prs, sources, marks):
        self.prs, self.sources, self.marks_by_key = prs, sources, marks

    def tip(self, item):
        lines = []
        for key in item.get('src', []) if isinstance(item, dict) else []:
            source = self.sources.get(key)
            if isinstance(source, dict):
                pr = self.prs.get(source.get('pr'), {})
                revision = source.get('revision')
                where = f' @ {revision[:10]}' if isinstance(revision, str) else ''
                lines.append(f"Source: {source.get('label', key)}{where} · {pr.get('repo', '')} #{pr.get('number', '')}")
        return '\n'.join(lines) or None

    def marks(self, *keys):
        return [mark for key in keys if key for mark in self.marks_by_key.get(key, [])]


class Scoped(Annotator):
    def __init__(self, parent, visual_id):
        super().__init__(parent.prs, parent.sources, {})
        self.marks_by_key = {key.split('/', 1)[1]: value for key, value in parent.marks_by_key.items()
                             if key.startswith(visual_id + '/')}


def validate(record, draft=False):
    problems = Problems()
    if not draft:
        problems.attempt('record', lambda: fields(record, 'title summary'))
    if 'limitations' in record:
        problems.attempt('limitations', lambda: fields(record, 'limitations'))
    prs = index(record['prs'], 'PR', problems)
    if not any(isinstance(pr, dict) and pr.get('scope') == 'reviewed' for pr in prs.values()):
        problems.messages.append('At least one reviewed PR is required')

    def check_pr(pr):
        fields(pr, 'repo title repo_path base head scope')
        require(pr['scope'] in ('reviewed', 'context'), 'Invalid PR scope')
        require(type(pr.get('number')) is int and pr['number'] > 0, 'PR number must be positive')
        require(SHA.fullmatch(pr['base']) and SHA.fullmatch(pr['head']), 'Use full pinned base/head SHAs')
        require(Path(pr['repo_path']).is_absolute(), 'repo_path must be absolute')
        safe_url(pr.get('url', ''))
        optional_text(pr, 'role')
        if pr['scope'] == 'reviewed' and not draft:
            fields(pr, 'spec_verdict code_verdict')

    for key, pr in prs.items():
        problems.attempt(f'PR {key}', lambda pr=pr: check_pr(pr))
    sources = index(record['evidence'], 'evidence', problems)

    def check_source(source):
        fields(source, 'pr kind label')
        require(source['pr'] in prs, 'Evidence refers to an unknown PR')
        require(source['kind'] in ('code', 'command', 'browser', 'requirement'), 'Invalid evidence kind')
        safe_url(source.get('url', ''))
        if source['kind'] == 'code':
            fields(source, 'revision path')
            require(SHA.fullmatch(source['revision']), 'Code evidence needs a full SHA')
            require(not Path(source['path']).is_absolute() and '..' not in Path(source['path']).parts,
                    'Code evidence path must be repository-relative')
            require(type(source.get('line')) is int and source['line'] > 0, 'Code line must be positive')
            end = source.get('end_line', source['line'])
            require(type(end) is int and end >= source['line'], 'Invalid end line')
            require(end - source['line'] < 80, 'Keep code citations below 80 lines')
            optional_text(source, 'symbol')
        else:
            fields(source, 'detail')
        if source['kind'] in ('command', 'browser'):
            fields(source, 'revision')
            require(SHA.fullmatch(source['revision']), 'Observed evidence needs the actual full revision SHA')
        if 'image' in source:
            require(source['kind'] == 'browser', 'Images belong to browser evidence')
            fields(source, 'image')
        source.pop('image_data', None)

    for key, source in sources.items():
        problems.attempt(f'evidence {key}', lambda source=source: check_source(source))

    def references(ids, required=True):
        require(isinstance(ids, list) and all(isinstance(key, str) and key in sources for key in ids),
                'Unknown or missing evidence references')
        require(bool(ids) or not required, 'This claim needs evidence')

    def source_ok(key, kind, pr, revision):
        source = sources.get(key)
        return source and source.get('kind') in kind and source.get('pr') == pr and source.get('revision') == revision

    def check_dependency(dep):
        fields(dep, 'from to label')
        require(dep['from'] in prs and dep['to'] in prs and dep['from'] != dep['to'], 'Invalid dependency endpoints')
        references(dep['evidence'])

    for position, dep in enumerate(record['dependencies'], 1):
        problems.attempt(f'dependency {position}', lambda dep=dep: check_dependency(dep))

    def check_claim(name, item):
        fields(item, 'pr')
        require(item['pr'] in prs, f'Unknown PR in {name}')
        require(prs[item['pr']].get('scope') == 'reviewed', f'{name} cannot target a context-only PR')
        references(item['evidence'], required=name in ('requirements', 'findings'))
        if name == 'requirements':
            fields(item, 'id status text assessment')
            require(item['status'] in ('met', 'missing', 'diverged', 'not in spec'), 'Invalid requirement status')
        elif name == 'findings':
            fields(item, 'id severity title explanation impact scenario fix')
            require(item['severity'] in SEVERITIES, 'Invalid finding severity')
            require(any(source_ok(key, ('code',), item['pr'], prs[item['pr']].get('head')) for key in item['evidence']),
                    'A finding needs code evidence at its reviewed PR head')
            require(isinstance(item.get('at', []), list) and all(isinstance(a, str) for a in item.get('at', [])),
                    'at must be an array of section names or visual/element references')
        elif name == 'checks':
            fields(item, 'label status result')
            require(item['status'] in ('passed', 'failed', 'not run'), 'Invalid check status')
            if item['status'] != 'not run':
                require(any(source_ok(key, ('command', 'browser'), item['pr'], prs[item['pr']].get('head'))
                            for key in item['evidence']),
                        'A passed/failed check needs command or browser evidence at the reviewed PR head')
        else:
            fields(item, 'concern reason')

    for name in CLAIMS:
        for position, item in enumerate(record[name], 1):
            label = item.get('id') if isinstance(item, dict) and isinstance(item.get('id'), str) else str(position)
            problems.attempt(f'{name} {label}', lambda name=name, item=item: check_claim(name, item))
    index(record['requirements'] + record['findings'], 'finding/requirement', problems)
    findings = {f['id']: f for f in record['findings'] if isinstance(f, dict) and isinstance(f.get('id'), str)}

    story = record['story']

    def check_story():
        if not draft:
            fields(story, 'users')
        optional_text(story, 'users why')
        require(isinstance(story.get('deploy', []), list) and all(isinstance(s, str) and s.strip()
                                                                   for s in story.get('deploy', [])),
                'deploy must be an array of text steps')
        matters = story.get('matters', [])
        require(isinstance(matters, list), 'matters must be an array')
        for item in matters:
            fields(item, 'text')
            require(item.get('reason', 'behaviour') in REASONS, f"Unknown reason {item.get('reason')!r} "
                                                                 f"(use {', '.join(REASONS)})")
            require(item.get('finding') is None or item['finding'] in findings, 'matters item names an unknown finding')
            references(item['evidence'], required=False)

    problems.attempt('story', check_story)

    def check_sections():
        for key, text in record['sections'].items():
            require(key in PROSE, f"Unknown section {key!r} (use {', '.join(PROSE)})")
            require(isinstance(text, str), f'Section {key} must be text')

    problems.attempt('sections', check_sections)

    def check_decision(decision):
        fields(decision, 'id title why basis')
        require(decision['basis'] in ('stated', 'inferred'), 'basis is stated (from a PR body, spec or commit) or inferred')
        optional_text(decision, 'alternatives')
        references(decision['evidence'], required=decision['basis'] == 'stated')

    for key, decision in index(record['decisions'], 'decision', problems).items():
        problems.attempt(f'decision {key}', lambda decision=decision: check_decision(decision))

    visuals = index(record['visuals'], 'visual', problems)
    element_keys = {}
    for key, visual in visuals.items():
        try:
            element_keys[key] = {alias for keys, _, _ in diagrams.elements(visual) for alias in keys}
        except (AttributeError, TypeError):
            element_keys[key] = set()
    marks = {}

    def check_anchors(finding):
        for anchor in finding.get('at', []):
            if '/' in anchor:
                visual, element = anchor.split('/', 1)
                require(visual in visuals, f'at {anchor!r}: no visual {visual!r}')
                require(element in element_keys[visual], f'at {anchor!r}: visual {visual!r} has no element {element!r}')
                marks.setdefault(anchor, []).append((finding['id'], finding['severity'], finding['title']))
            else:
                require(anchor in PLACEMENTS, f"at {anchor!r}: use a section ({', '.join(PLACEMENTS)}) or visual/element")

    for key, finding in findings.items():
        problems.attempt(f'findings {key}', lambda finding=finding: check_anchors(finding))
    annotator = Annotator(prs, sources, marks)

    def check_visual(visual):
        fields(visual, 'title caption section kind')
        require(visual['id'] not in PLACEMENTS and visual['id'] != 'stack-map', 'A visual id cannot be a section name')
        require(visual['section'] in PLACEMENTS, f"Unknown section {visual['section']!r} (use {', '.join(PLACEMENTS)})")
        require(visual['kind'] in KINDS, f"Unknown visual kind {visual['kind']!r} (use {', '.join(KINDS)})")
        members = visual.get('prs', [])
        require(isinstance(members, list) and all(isinstance(key, str) and key in prs for key in members),
                'Unknown visual PRs')
        references(visual['evidence'], required=visual['kind'] == 'svg')
        for _, item, _ in diagrams.elements(visual):
            if 'src' in item:
                references(item['src'])
        if visual['kind'] == 'table':
            diagrams.table_rows(visual)
        elif visual['kind'] == 'svg':
            require(isinstance(visual.get('svg'), str), 'An svg visual needs an svg string')
            visual['_data'] = diagram_data(visual['svg'])
        else:
            svg = diagrams.BUILDERS[visual['kind']](visual, Scoped(annotator, visual['id']), f"v-{visual['id']}")
            try:
                ET.fromstring(svg)
            except ET.ParseError as error:
                raise ValueError(f'Drawing failed: {error}') from error
            visual['_svg'] = svg

    for key, visual in visuals.items():
        problems.attempt(f'visual {key}', lambda visual=visual: check_visual(visual))
    problems.raise_if_any()
    return prs, sources, annotator


def unsourced(record):
    """visual/element references for change or behaviour claims drawn without a cited source."""
    missing = []
    for visual in record['visuals']:
        for keys, item, role in diagrams.elements(visual):
            if diagrams.source_required(role, item) and not item.get('src'):
                label = keys[0] if keys else item.get('label') or item.get('title') or item.get('name') or role
                missing.append(f"{visual['id']}/{label}")
    return missing


def hydrate(record, prs):
    problems = Problems()

    def load(source):
        pr = prs[source['pr']]
        result = subprocess.run(['git', '-C', pr['repo_path'], 'show', source['revision'] + ':' + source['path']],
                                text=True, capture_output=True)
        require(result.returncode == 0, f"git show failed for {source['path']} at {source['revision'][:10]}: "
                                        f"{result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'unknown error'}")
        lines = result.stdout.splitlines()
        end = source.get('end_line', source['line'])
        require(end <= len(lines), f'file has {len(lines)} lines, cited {source["line"]}-{end}')
        source['excerpt'] = '\n'.join(lines[source['line'] - 1:end])
        if source.get('symbol'):
            require(source['symbol'] in source['excerpt'],
                    f"{source['symbol']!r} is not in {source['path']}:{source['line']}-{end} at {source['revision'][:10]}")
        pr_url = pr.get('url', '')
        if '/pull/' in pr_url:
            source['url'] = (pr_url.split('/pull/')[0] + '/blob/' + source['revision'] + '/'
                             + quote(source['path'], safe='/') + '#L' + str(source['line'])
                             + (f"-L{source['end_line']}" if source.get('end_line') else ''))

    def picture(source):
        path = Path(source['image']).expanduser().resolve()
        require(path.is_file(), f'screenshot not found: {path}')
        data = path.read_bytes()
        if data.startswith(b'\x89PNG\r\n\x1a\n'):
            mime = 'image/png'
        elif data.startswith(b'\xff\xd8\xff'):
            mime = 'image/jpeg'
        else:
            raise ValueError('Browser evidence image must be PNG or JPEG')
        source['image_data'] = 'data:' + mime + ';base64,' + base64.b64encode(data).decode('ascii')

    for source in record['evidence']:
        if source['kind'] == 'code':
            problems.attempt(f"evidence {source['id']}", lambda source=source: load(source))
        if 'image' in source:
            problems.attempt(f"evidence {source['id']}", lambda source=source: picture(source))
    problems.raise_if_any()


def e(value):
    return escape(str(value), quote=True)


def badge(label, tone=None):
    return f'<span class="badge {e(tone or label.lower().replace(" ", "-"))}">{e(label)}</span>'


def paragraphs(text):
    return ''.join(f'<p>{e(part.strip())}</p>' for part in re.split(r'\n\s*\n', text) if part.strip())


def render(record, prs, sources, annotator):
    def pr_name(key):
        pr = prs[key]
        return f"{pr['repo']} #{pr['number']}"

    def link(source):
        label = e(source['label'])
        return f'<a href="{e(source["url"])}">{label}</a>' if source.get('url') else f'<span>{label}</span>'

    def distinct(ids):
        """One entry per cited place: several elements often cite the same lines."""
        seen = {}
        for key in ids:
            source = sources[key]
            seen.setdefault((source['pr'], source['label'], source.get('revision'), source.get('detail')), key)
        return list(seen.values())

    def refs(ids):
        items = []
        for key in distinct(ids):
            source = sources[key]
            if source['kind'] == 'code':
                items.append(link(source))
            else:
                content = f'<p class="observation">{e(source["detail"])}</p>'
                if source.get('url'):
                    content += f'<a href="{e(source["url"])}">Open source</a>'
                if source.get('image_data'):
                    content += f'<img class="screenshot" src="{e(source["image_data"])}" alt="{e(source["label"])}">'
                items.append(f'<details class="source-detail"><summary>{e(source["label"])}</summary>{content}</details>')
        return '<div class="refs">' + ''.join(items) + '</div>' if items else ''

    findings = {f['id']: f for f in record['findings']}
    ordered = sorted(record['findings'], key=lambda f: (
        SEVERITIES.index(f['severity']), prs[f['pr']]['repo'], prs[f['pr']]['number'],
        [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', f['id'])]))
    placed = {}
    for finding in ordered:
        anchor = (finding.get('at') or ['overview'])[0]
        placed.setdefault(anchor.split('/', 1)[0], []).append(finding)

    def callouts(key):
        return ''.join(
            f'<aside class="callout sev-{e(f["severity"].lower())}" id="f-{e(f["id"])}">{badge(f["severity"])}'
            f'<div><strong>{e(f["id"])} · {e(f["title"])}</strong><p>{e(f["impact"])}</p>'
            f'<span class="muted">{e(pr_name(f["pr"]))}</span></div></aside>' for f in placed.get(key, []))

    def zoom(title):
        return (f'<div class="visual-controls toolbar" hidden><button type="button" data-zoom="out" aria-label="Zoom out: {e(title)}">−</button>'
                f'<button type="button" data-zoom="in" aria-label="Zoom in: {e(title)}">+</button>'
                f'<button type="button" data-zoom="reset">Fit</button><output aria-live="polite">100%</output></div>')

    def cell(text):
        tone = CELL_BADGES.get(text.strip().lower())
        return badge(text, f'cell-{tone}') if tone else e(text)

    def table(columns, rows, scoped):
        body = ''
        for cells, tone, item, keys in rows:
            marks = scoped.marks(*keys)
            pills = ''.join(f'<span class="mark sev-{e(sev.lower())}" title="{e(title)}">{e(label)}</span>'
                            for label, sev, title in marks)
            if diagrams.source_required('row', item) and not item.get('src'):
                pills += '<span class="mark unverified" title="No source cited for this row">?</span>'
            tip = annotator.tip(item)
            first = pills + cell(cells[0])
            body += (f'<tr class="tone-{e(tone)}"' + (f' title="{e(tip)}"' if tip else '') + '>'
                     + f'<td>{first}</td>' + ''.join(f'<td>{cell(c)}</td>' for c in cells[1:]) + '</tr>')
        return ('<div class="visual-table"><table><thead><tr>' + ''.join(f'<th>{e(c)}</th>' for c in columns)
                + f'</tr></thead><tbody>{body}</tbody></table></div>')

    def figure(visual):
        scoped = Scoped(annotator, visual['id'])
        ids = list(visual['evidence']) + [key for _, item, _ in diagrams.elements(visual) for key in item.get('src', [])]
        if visual['kind'] == 'table':
            columns, rows = diagrams.table_rows(visual)
            body = table(columns, [(cells, tone, item, (item.get('id'),)) for cells, tone, item in rows], scoped)
            controls = ''
        else:
            if visual['kind'] == 'svg':
                drawing = f'<img class="diagram" src="{visual["_data"]}" alt="{e(visual["caption"])}">'
            else:
                drawing = visual['_svg'].replace('<svg ', f'<svg class="diagram" role="img" aria-label="{e(visual["title"])}" ', 1)
            body = (f'<div class="visual-viewport" tabindex="0" role="region" aria-label="{e(visual["title"])}">'
                    f'{drawing}</div>')
            controls = zoom(visual['title'])
            if visual['kind'] == 'schema':
                changes = diagrams.schema_changes(visual)
                if changes:
                    body += table(['Collection', 'Field', 'Change', 'Type', 'Default', 'Index', 'Note'],
                                  [(cells, 'normal', field, (key,)) for cells, field, key in changes], scoped)
        sources_html = refs(ids)
        if sources_html:
            sources_html = (f'<details class="visual-sources"><summary>Sources ({len(distinct(ids))})</summary>'
                            f'{sources_html}</details>')
        return (f'<figure class="visual" id="v-{e(visual["id"])}"><figcaption><h3>{e(visual["title"])}</h3>'
                f'<p>{e(visual["caption"])}</p></figcaption>{controls}{body}{sources_html}'
                f'{callouts(visual["id"])}</figure>')

    def figures(section):
        return ''.join(figure(v) for v in record['visuals'] if v['section'] == section)

    story = record['story']
    reviewed = [pr for pr in prs.values() if pr['scope'] == 'reviewed']
    blocks = {}

    overview = ''
    if story.get('users'):
        overview += f'<p class="lede">{e(story["users"])}</p>'
    if story.get('why'):
        overview += f'<p class="why"><strong>Why:</strong> {e(story["why"])}</p>'
    side = ''
    if story.get('deploy'):
        side += '<h3>Deploy order</h3><ol class="deploy">' + ''.join(f'<li>{e(s)}</li>' for s in story['deploy']) + '</ol>'
    diffs = [r for r in record['requirements'] if r['status'] in ('missing', 'diverged')]
    if diffs:
        side += '<h3>Differs from the requirements</h3><ul class="diffs">' + ''.join(
            f'<li>{badge(r["status"])} {e(r["text"])} <span class="muted">— {e(r["assessment"])}</span></li>' for r in diffs) + '</ul>'
    if side:
        overview = f'<div class="glance"><div>{overview}</div><div class="glance-side">{side}</div></div>'
    if story.get('matters'):
        overview += '<h3>What matters</h3><ol class="matters">' + ''.join(
            f'<li><span class="reason">{e(item.get("reason", "behaviour"))}</span><div>{e(item["text"])}'
            + (f' <a href="#f-{e(item["finding"])}">{e(item["finding"])}</a>' if item.get('finding') else '')
            + f'{refs(item["evidence"])}</div></li>' for item in story['matters']) + '</ol>'
    blocks['overview'] = overview + figures('overview') + callouts('overview')

    for key in PROSE:
        text = record['sections'].get(key, '')
        blocks[key] = (paragraphs(text) if text else '') + figures(key) + callouts(key)

    build = ''
    if len(prs) > 1:
        stack = diagrams.stack_map(list(prs.values()), record['dependencies'])
        cited = [key for dep in record['dependencies'] for key in dep['evidence']]
        stack = stack.replace('<svg ', '<svg class="diagram" role="img" aria-label="Stack map" ', 1)
        build += (f'<figure class="visual" id="v-stack-map"><figcaption><h3>Stack map</h3><p>Pinned PRs grouped by '
                  f'repository. Solid nodes are reviewed, dashed nodes are context; every arrow is a cited dependency.'
                  f'</p></figcaption>{zoom("Stack map")}<div class="visual-viewport" tabindex="0" role="region" '
                  f'aria-label="Stack map">{stack}</div>'
                  + (f'<details class="visual-sources"><summary>Sources</summary>{refs(cited)}</details>' if cited else '')
                  + '</figure>')
    cards = ''
    for pr in prs.values():
        name = e(pr_name(pr['id']))
        if pr.get('url'):
            name = f'<a href="{e(pr["url"])}">{name}</a>'
        cards += (f'<article class="pr-node scope-{e(pr["scope"])}" id="pr-{e(pr["id"])}"><div class="node-label">{name}'
                  f'{badge(pr["scope"])}</div><h3>{e(pr["title"])}</h3>'
                  + (f'<p class="role">{e(pr["role"])}</p>' if pr.get('role') else '')
                  + f'<div class="revision">{e(pr["base"][:10])} → {e(pr["head"][:10])}</div></article>')
    blocks['build'] = build + f'<div class="pr-grid">{cards}</div>'

    blocks['decisions'] = ''.join(
        f'<article class="decision" id="d-{e(d["id"])}"><div class="decision-head"><h3>{e(d["title"])}</h3>'
        f'{badge("Stated" if d["basis"] == "stated" else "Inferred", "stated" if d["basis"] == "stated" else "inferred")}</div>'
        f'<p>{e(d["why"])}</p>'
        + (f'<p class="muted"><strong>Alternatives:</strong> {e(d["alternatives"])}</p>' if d.get('alternatives') else '')
        + f'{refs(d["evidence"])}</article>' for d in record['decisions'])

    missing = unsourced(record)
    gaps = [c for c in record['checks'] if c['status'] != 'passed']
    limitations = record.get('limitations', '')
    if not limitations and not record['checks']:
        limitations = 'Source inspection only; no runtime checks recorded.'
    limits = paragraphs(limitations) if limitations else ''
    if gaps:
        limits += '<ul class="gaps">' + ''.join(f'<li>{badge(c["status"])} {e(c["label"])}: {e(c["result"])}</li>'
                                                for c in gaps) + '</ul>'
    if missing:
        limits += (f'<p>{len(missing)} diagram element(s) carry no cited source and show a <span class="mark unverified">?</span> '
                   f'marker: {e(", ".join(missing))}.</p>')
    limits += ('<p class="muted">This page explains the change; full findings with failure scenarios and fixes are in the '
               'chat answer and review.json. Diagram sources are pinned to the PR heads listed above.</p>')
    blocks['limits'] = limits

    nav, content = '', ''
    for key, heading in SECTIONS:
        if blocks.get(key):
            nav += f'<a href="#{key}">{e(heading)}</a>'
            content += f'<section id="{key}"><h2>{e(heading)}</h2>{blocks[key]}</section>'
    counts = Counter(f['severity'] for f in record['findings'])
    repos = len({pr['repo'] for pr in prs.values()})
    stats = (f'<div><strong>{len(reviewed)}</strong><span>PRs reviewed</span></div>'
             f'<div><strong>{repos}</strong><span>repositor{"y" if repos == 1 else "ies"}</span></div>'
             f'<div><strong>{len(findings)}</strong><span>finding{"" if len(findings) == 1 else "s"}</span></div>'
             + ''.join(badge(f'{s}: {counts[s]}', s.lower()) for s in SEVERITIES if counts[s]))

    summary_lines = [record['title'], '', 'Spec'] + [f"- {pr_name(pr['id'])}: {pr['spec_verdict']}" for pr in reviewed]
    summary_lines += ['', 'Code'] + [f"- {pr_name(pr['id'])}: {pr['code_verdict']}" for pr in reviewed]
    summary_lines += ['', 'Findings: ' + ', '.join(f'{s}: {counts[s]}' for s in SEVERITIES)]
    summary_lines += [f"- {f['id']} [{f['severity']}] {pr_name(f['pr'])}: {f['title']}" for f in ordered]
    summary_limits = record.get('limitations', '')
    if not summary_limits and gaps:
        summary_limits = 'Checks incomplete: ' + '; '.join(dict.fromkeys(f"{c['label']} ({c['status']})" for c in gaps)) + '.'
    if not summary_limits and not record['checks']:
        summary_limits = 'Source inspection only; no runtime checks recorded.'
    if summary_limits:
        summary_lines += ['', 'Review limits: ' + summary_limits]
    html = Template((ASSETS / 'report.html').read_text()).substitute(
        title=e(record['title']), summary=e(record['summary']), stats=stats, nav=nav, content=content,
        generated=e(datetime.now(timezone.utc).isoformat(timespec='seconds')))
    return html, '\n'.join(summary_lines) + '\n'


def saved_record(record):
    """The audit copy keeps pinned SHAs and excerpts; embedded image bytes and render scratch stay out."""
    def strip(item):
        return {k: v for k, v in item.items() if k != 'image_data' and not k.startswith('_')}
    return {**record, 'evidence': [strip(s) for s in record['evidence']], 'visuals': [strip(v) for v in record['visuals']]}


def load(source_path, draft=False):
    record = normalize(json.loads(Path(source_path).read_text()))
    prs, sources, annotator = validate(record, draft)
    for pr in prs.values():
        repo = Path(pr['repo_path']).resolve()
        result = subprocess.run(['git', '-C', str(repo), 'rev-parse', '--show-toplevel'], text=True, capture_output=True)
        require(result.returncode == 0, f"{pr['id']}: repo_path is not a Git repository: {repo}")
        pr['_root'] = Path(result.stdout.strip()).resolve()
    hydrate(record, prs)
    return record, prs, sources, annotator


def check(source_path, draft=False):
    record, prs, sources, _ = load(source_path, draft)
    visuals = Counter(v['kind'] for v in record['visuals'])
    report = (f"OK: {len(prs)} PRs, {len(sources)} sources resolved, {len(record['findings'])} findings, "
              f"{len(record['requirements'])} requirements, {len(record['decisions'])} decisions, "
              f"{sum(visuals.values())} visuals {dict(visuals) if visuals else ''}".rstrip())
    missing = unsourced(record)
    if missing:
        report += f"\nNo source cited ({len(missing)}; the page marks them unverified): " + ', '.join(missing)
    return report


def build(source_path, output_dir):
    output_dir = Path(output_dir).resolve()
    record, prs, sources, annotator = load(Path(source_path).resolve())
    for pr in prs.values():
        require(not output_dir.is_relative_to(pr.pop('_root')), 'Write the report outside every reviewed repository')
    html, summary = render(record, prs, sources, annotator)
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / 'review.json').write_text(json.dumps(saved_record(record), ensure_ascii=False, indent=2) + '\n')
    (output_dir / 'summary.md').write_text(summary)
    page = output_dir / 'review.html'
    page.write_text(html)
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('record', type=Path, nargs='?', help='Review record JSON; see report-record.md')
    parser.add_argument('--output', type=Path, help='New directory outside reviewed repositories')
    parser.add_argument('--check', action='store_true', help='Validate and resolve citations without writing a report')
    parser.add_argument('--draft', action='store_true', help='With --check: allow a partial record without verdicts or story')
    parser.add_argument('--example', action='store_true', help='Print the compact example record and exit')
    args = parser.parse_args()
    if args.example:
        print((ASSETS / 'record.example.json').read_text(), end='')
        return
    if not args.record:
        parser.error('a record path is required')
    if args.draft and not args.check:
        parser.error('--draft only applies with --check')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    output = args.output or Path.home() / '.agent' / 'reviews' / stamp
    try:
        print(check(args.record, args.draft) if args.check else build(args.record, output))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Review render failed: {error}\n')


if __name__ == '__main__':
    main()

import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'tests'))
spec = importlib.util.spec_from_file_location('render_review', SKILL / 'scripts/render_review.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
import diagrams  # noqa: E402
from fixture import demo_record, make_repo  # noqa: E402


class ExplainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.repo = cls.root / 'repo'
        cls.shas = make_repo(cls.repo)
        (cls.repo / 'src/giftCards/redeem.ts').write_text('working tree edits must not leak into the report\n')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.record = demo_record(self.repo, self.shas)
        self.out = tempfile.TemporaryDirectory()
        self.addCleanup(self.out.cleanup)
        self.dir = Path(self.out.name)

    def write(self, record=None):
        source = self.dir / 'input.json'
        source.write_text(json.dumps(record or self.record))
        return source

    def render(self, record=None):
        page = renderer.build(self.write(record), self.dir / 'report')
        return page.read_text()

    def visual(self, key):
        return next(v for v in self.record['visuals'] if v['id'] == key)

    def test_page_explains_the_stack_in_design_doc_order(self):
        html = self.render()
        sections = re.findall(r'<section id="([a-z]+)">', html)
        self.assertEqual(sections, ['overview', 'architecture', 'data', 'rollout', 'contracts', 'lifecycle',
                                    'build', 'decisions', 'limits'])
        self.assertIn('Shoppers can pay part or all of an order', html)
        self.assertIn('shop-api #11: run the migration', html)
        self.assertIn('Inferred', html)

    def test_page_shows_no_code_diff_or_review_controls(self):
        html = self.render()
        for absent in ('<pre', '<code', '<select', '<form', 'code-block', 'Approve', 'request changes'):
            self.assertNotIn(absent, html)
        self.assertNotIn('findOne({ code', html)

    def test_summary_carries_the_verdicts_and_every_finding(self):
        self.render()
        summary = (self.dir / 'report/summary.md').read_text()
        self.assertIn('acme/shop-api #12: Changes needed: 2 High.', summary)
        for key in ('F1 [High]', 'F2 [High]', 'F3 [Medium]'):
            self.assertIn(key, summary)
        self.assertIn('Review limits: Synthetic fixture', summary)

    def test_findings_become_markers_and_one_line_callouts_where_they_bite(self):
        html = self.render()
        sequence = html.split('id="v-redeem-seq"')[1].split('</figure>')[0]
        self.assertIn('id="f-F1"', sequence)
        self.assertIn('id="f-F2"', sequence)
        self.assertIn('>F1</tspan>', sequence)
        self.assertIn("A shopper at business A can spend a card sold by business B", sequence)
        self.assertNotIn('Filter by the order', html)
        architecture = html.split('id="v-arch"')[1].split('</figure>')[0]
        self.assertIn('>F1</tspan>', architecture)
        self.assertNotIn('id="f-F1"', architecture)

    def test_element_sources_become_hover_text_at_the_pinned_head(self):
        html = self.render()
        self.assertIn(f"<title>Source: src/giftCards/redeem.ts:5 @ {self.shas['redeem'][:10]} · acme/shop-api #12</title>", html)
        self.assertIn('/blob/' + self.shas['redeem'] + '/src/giftCards/redeem.ts#L5', html)

    def test_a_cited_symbol_must_be_on_the_cited_lines(self):
        self.visual('redeem-seq')['messages'][2]['src'] = 'src/giftCards/redeem.ts:4#findOne'
        with self.assertRaisesRegex(ValueError, "'findOne' is not in src/giftCards/redeem.ts:4-4"):
            renderer.check(self.write())

    def test_a_citation_past_the_end_of_the_file_is_rejected(self):
        self.visual('data-model')['entities'][0]['fields'][0]['src'] = 'src/models/giftCard.ts:40'
        with self.assertRaisesRegex(ValueError, 'file has 13 lines'):
            renderer.check(self.write())

    def test_unsourced_change_claims_are_flagged_not_hidden(self):
        del self.visual('arch')['nodes'][2]['src']
        report = renderer.check(self.write())
        self.assertIn('No source cited (1', report)
        self.assertIn('arch/redeem', report)
        html = self.render()
        self.assertIn('No source cited for this element', html)
        self.assertIn('1 diagram element(s) carry no cited source', html)

    def test_unchanged_context_needs_no_source(self):
        report = renderer.check(self.write())
        self.assertNotIn('No source cited', report)

    def test_anchors_must_name_a_section_or_an_existing_element(self):
        self.record['findings'][0]['at'] = ['redeem-seq/99']
        self.record['findings'][1]['at'] = ['nowhere']
        with self.assertRaises(ValueError) as caught:
            renderer.check(self.write())
        self.assertIn("visual 'redeem-seq' has no element '99'", str(caught.exception))
        self.assertIn("at 'nowhere'", str(caught.exception))

    def test_shorthand_names_only_known_prs(self):
        self.record['findings'][0]['evidence'] = ['server-99:src/giftCards/redeem.ts:5']
        with self.assertRaisesRegex(ValueError, 'names no known PR'):
            renderer.check(self.write())

    def test_draft_check_accepts_an_explorer_fragment(self):
        fragment = {key: self.record[key] for key in ('prs', 'dependencies', 'visuals', 'sections', 'decisions')}
        fragment = copy.deepcopy(fragment)
        for pr in fragment['prs']:
            del pr['spec_verdict'], pr['code_verdict']
        self.assertTrue(renderer.check(self.write(fragment), draft=True).startswith('OK: 3 PRs'))
        with self.assertRaisesRegex(ValueError, 'spec_verdict'):
            renderer.check(self.write(fragment))

    def test_context_pr_cannot_receive_a_finding(self):
        self.record['prs'][0]['scope'] = 'context'
        self.record['findings'][0]['pr'] = 'server-11'
        with self.assertRaisesRegex(ValueError, 'context-only PR'):
            renderer.check(self.write())

    def test_passing_check_needs_observed_evidence_at_the_head(self):
        self.record['checks'] = [{'pr': 'server-12', 'label': 'Unit tests', 'status': 'passed', 'result': 'green'}]
        with self.assertRaisesRegex(ValueError, 'command or browser evidence'):
            renderer.check(self.write())
        self.record['checks'][0]['evidence'] = [{'kind': 'command', 'label': 'jest', 'detail': 'npx jest → 4 passed',
                                                 'at': 'base'}]
        with self.assertRaisesRegex(ValueError, 'command or browser evidence'):
            renderer.check(self.write())

    def test_every_validation_problem_is_reported_in_one_run(self):
        self.record['findings'][0]['severity'] = 'Huge'
        self.record['story']['matters'][0]['reason'] = 'vibes'
        self.visual('arch')['nodes'][1]['shape'] = 'cloud'
        self.record['decisions'][0]['basis'] = 'guessed'
        with self.assertRaises(ValueError) as caught:
            renderer.check(self.write())
        message = str(caught.exception)
        for expected in ('Invalid finding severity', "Unknown reason 'vibes'", 'Unknown shape: cloud', 'basis is stated'):
            self.assertIn(expected, message)

    def test_untrusted_text_cannot_become_markup_or_a_script(self):
        hostile = '<script>alert(1)</script><img src=x onerror=alert(2)>'
        self.record['title'] = hostile
        self.record['story']['users'] = hostile
        self.visual('arch')['nodes'][1]['label'] = hostile
        self.visual('api')['rows'][0]['cells'][0] = hostile
        html = self.render()
        self.assertEqual(html.count('<script>'), 1)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;script&gt;', html)

    def test_report_is_offline_and_written_outside_the_repository(self):
        with self.assertRaisesRegex(ValueError, 'repository'):
            renderer.build(self.write(), self.repo / 'report')
        html = self.render()
        self.assertNotRegex(html, r'(src|href)="(?!https://github\.com/|#|data:)')
        with self.assertRaises(FileExistsError):
            renderer.build(self.write(), self.dir / 'report')

    def test_saved_record_keeps_pinned_excerpts_but_no_render_scratch(self):
        self.render()
        saved = json.loads((self.dir / 'report/review.json').read_text())
        excerpts = {s['label']: s['excerpt'] for s in saved['evidence'] if s['kind'] == 'code'}
        self.assertEqual(excerpts['src/giftCards/redeem.ts:5'],
                         "  const card = await db.giftcards.findOne({ code, status: 'active' });")
        self.assertFalse(any(key.startswith('_') for visual in saved['visuals'] for key in visual))
        self.assertEqual(saved['findings'][0]['at'], ['redeem-seq/3', 'arch/redeem'])

    def test_check_mode_writes_nothing(self):
        source = self.write()
        before = sorted(p.name for p in self.dir.iterdir())
        self.assertTrue(renderer.check(source).startswith('OK: 3 PRs'))
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), before)

    def test_schema_changes_get_a_field_table(self):
        html = self.render()
        data = html.split('id="v-data-model"')[1].split('</figure>')[0]
        self.assertIn('<th>Index</th>', data)
        self.assertIn('unique with code', data)
        self.assertIn('subtracted at checkout', data)

    def test_raw_svg_is_isolated_and_rejects_active_content(self):
        good = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10" fill="#fff"/></svg>')
        self.record['visuals'].append({'id': 'hand', 'kind': 'svg', 'section': 'overview', 'title': 'Hand drawn',
                                       'caption': 'A static figure.', 'svg': good,
                                       'evidence': ['server-12:src/checkout/pay.ts:5']})
        self.assertIn('data:image/svg+xml;base64,', self.render())
        for bad in ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>alert(1)</script></svg>',
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><image href="https://x"/></svg>',
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10" onload="alert(1)"></svg>'):
            with self.assertRaises(ValueError):
                renderer.diagram_data(bad)


class DiagramTests(unittest.TestCase):
    def test_builders_wrap_labels_and_reject_bad_specs(self):
        long_title = 'A very long step title that must wrap onto several lines instead of overflowing the box'
        svg = diagrams.flow({'lanes': [{'label': 'Only lane', 'steps': [{'title': long_title, 'detail': 'x' * 120},
                                                                        {'title': 'Next', 'arrow': 'then'}]}]})
        self.assertGreaterEqual(svg.count('<tspan'), 4)
        renderer.diagram_data(svg)
        with self.assertRaisesRegex(ValueError, 'node ids'):
            diagrams.graph({'nodes': [{'id': 'a', 'label': 'A'}], 'edges': [{'from': 'a', 'to': 'zzz'}]})
        with self.assertRaisesRegex(ValueError, 'one text cell per column'):
            diagrams.table_rows({'columns': ['A', 'B'], 'rows': [['only one']]})
        with self.assertRaisesRegex(ValueError, 'tone'):
            diagrams.flow({'lanes': [{'steps': [{'title': 'x', 'tone': 'loud'}]}]})
        with self.assertRaisesRegex(ValueError, 'participant ids'):
            diagrams.sequence({'participants': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}],
                               'messages': [{'from': 'a', 'to': 'c', 'label': 'x'}]})
        with self.assertRaisesRegex(ValueError, 'field status'):
            diagrams.schema({'entities': [{'id': 'e', 'label': 'E', 'fields': [{'name': 'f', 'status': 'gone'}]}]})
        with self.assertRaisesRegex(ValueError, 'lane id'):
            diagrams.timeline({'lanes': [{'id': 'server', 'label': 'Server'}], 'steps': [{'title': 'x', 'lane': 'web'}]})

    def test_every_drawing_passes_the_static_svg_sanitizer(self):
        drawings = [
            diagrams.graph({'nodes': [{'id': 'a', 'label': 'A', 'shape': 'store', 'status': 'new'},
                                      {'id': 'b', 'label': 'B', 'shape': 'queue'}, {'id': 'c', 'label': 'C', 'shape': 'external'}],
                            'edges': [{'from': 'a', 'to': 'b'}, {'from': 'b', 'to': 'c', 'label': 'retry'},
                                      {'from': 'c', 'to': 'a', 'label': 'back', 'dashed': True}]}),
            diagrams.sequence({'participants': [{'id': 'a', 'label': 'A', 'shape': 'actor'}, {'id': 'b', 'label': 'B'}],
                               'messages': [{'from': 'a', 'to': 'b', 'label': 'call'}, {'from': 'b', 'to': 'b', 'label': 'self'},
                                            {'from': 'b', 'to': 'a', 'label': 'reply', 'reply': True}]}),
            diagrams.schema({'entities': [{'id': 'e', 'label': 'E', 'status': 'changed',
                                           'fields': [{'name': 'old', 'status': 'removed'}, {'name': 'new', 'status': 'added'}]}]}),
            diagrams.timeline({'lanes': [{'id': 's', 'label': 'Server'}, {'id': 'p', 'label': 'Portal'}],
                               'steps': [{'title': 'Migrate', 'lane': 's', 'reversible': False}, {'title': 'Ship', 'lane': 'p'}]}),
        ]
        for svg in drawings:
            renderer.diagram_data(svg)
        self.assertIn('ONE-WAY', drawings[3])
        self.assertIn('stroke-dasharray', drawings[0])

    def test_marker_ids_are_unique_per_drawing(self):
        first = diagrams.graph({'nodes': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}],
                                'edges': [{'from': 'a', 'to': 'b'}]}, prefix='v-one')
        second = diagrams.graph({'nodes': [{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}],
                                 'edges': [{'from': 'a', 'to': 'b'}]}, prefix='v-two')
        self.assertIn('id="v-one-m-wire"', first)
        self.assertIn('url(#v-two-m-wire)', second)

    def test_stack_map_draws_only_cited_dependencies(self):
        prs = [{'id': 'a', 'repo': 'acme/shop-api', 'number': 1, 'title': 'First', 'scope': 'context'},
               {'id': 'b', 'repo': 'acme/shop-api', 'number': 2, 'title': 'Second', 'scope': 'reviewed'},
               {'id': 'c', 'repo': 'acme/shop-web', 'number': 9, 'title': 'Web side', 'scope': 'reviewed'}]
        self.assertNotIn('<polyline', diagrams.stack_map(prs, []))
        connected = diagrams.stack_map(prs, [{'from': 'a', 'to': 'b', 'label': 'parent of'},
                                             {'from': 'b', 'to': 'c', 'label': 'serves the consent route used by'}])
        self.assertEqual(connected.count('<polyline'), 2)
        renderer.diagram_data(connected)
        parallel = diagrams.stack_map(prs, [{'from': 'b', 'to': 'c', 'label': 'redirects to'},
                                            {'from': 'b', 'to': 'c', 'label': 'is called back by'}])
        wires = [line.split('points="')[1].split('"')[0] for line in parallel.split('<polyline')[1:]]
        self.assertEqual(len(wires), 2)
        self.assertNotEqual(wires[0], wires[1])


class ExampleTests(unittest.TestCase):
    def test_the_printed_example_is_a_valid_draft_shape(self):
        example = json.loads(subprocess.check_output([sys.executable, str(SKILL / 'scripts/render_review.py'), '--example']))
        record = renderer.normalize(example)
        self.assertTrue(record['story']['users'])
        self.assertTrue({v['kind'] for v in record['visuals']} >= {'graph', 'sequence', 'schema', 'timeline'})


if __name__ == '__main__':
    unittest.main()

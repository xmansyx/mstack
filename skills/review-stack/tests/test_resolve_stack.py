"""Topology logic of resolve_stack.py, over fixture nodes and without network access."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
spec = importlib.util.spec_from_file_location('resolve_stack', SKILL / 'scripts/resolve_stack.py')
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ResolverFixture(unittest.TestCase):
    """Restore every patched module attribute, so test order cannot matter."""

    def patch(self, **attributes):
        for name, value in attributes.items():
            self.addCleanup(setattr, resolver, name, getattr(resolver, name))
            setattr(resolver, name, value)


def node(number, base, head, draft=False):
    return {'number': number, 'title': f'PR {number}', 'isDraft': draft, 'baseRefName': base,
            'headRefName': head, 'headRefOid': f'{number:040d}', 'baseRefOid': f'{number - 1:040d}',
            'url': f'https://example.invalid/{number}'}


class RepositoryTests(unittest.TestCase):
    def test_supported_remotes_match_the_full_identity_with_an_optional_git_suffix(self):
        for remote in ('git@github.com:Acme-Corp/seat-picker.git',
                       'git@github.com:Acme-Corp/seat-picker',
                       'https://github.com/Acme-Corp/seat-picker.git',
                       'https://github.com/acme-corp/seat-picker',
                       'ssh://git@github.com:22/Acme-Corp/seat-picker.git'):
            with self.subTest(remote=remote):
                self.assertTrue(resolver.matches_remote(remote, 'Acme-Corp/seat-picker'))

    def test_forks_other_hosts_and_suffix_matches_are_not_the_requested_repository(self):
        for remote in ('git@github.com:another-owner/shop-api.git',
                       'git@other.example:acme/shop-api.git',
                       'https://github.com/acme/other-shop-api.git',
                       'https://github.com/acme/shop-api.git-extra',
                       '/local/acme/shop-api.git'):
            with self.subTest(remote=remote):
                self.assertFalse(resolver.matches_remote(remote, 'acme/shop-api'))


class TrunkTests(ResolverFixture):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.common_dir = Path(directory.name)

    def write_stack(self, *trunks):
        (self.common_dir / 'gh-stack').write_text(json.dumps({
            'schemaVersion': 1,
            'stacks': [{'trunk': {'branch': trunk, 'head': 'a' * 40}, 'branches': []} for trunk in trunks]}))

    def test_gh_stack_trunk_takes_precedence_over_the_remote_default(self):
        self.write_stack('dev')
        self.patch(run=lambda *args, **kwargs: self.fail('gh-stack already supplies the trunk'))
        self.assertEqual(resolver.default_trunk(Path('/fixture'), self.common_dir), 'dev')

    def test_gh_stack_trunk_takes_precedence_over_a_stale_graphite_trunk(self):
        self.write_stack('dev')
        (self.common_dir / '.graphite_repo_config').write_text(json.dumps({'trunk': '1.3.0'}))
        self.patch(run=lambda *args, **kwargs: self.fail('gh-stack already supplies the trunk'))
        self.assertEqual(resolver.default_trunk(Path('/fixture'), self.common_dir), 'dev')

    def test_stacks_on_different_trunks_do_not_supply_a_repository_default(self):
        self.write_stack('dev', 'main')
        (self.common_dir / '.graphite_repo_config').write_text(json.dumps({'trunk': '1.3.0'}))
        self.assertEqual(resolver.default_trunk(Path('/fixture'), self.common_dir), '1.3.0')

    def test_a_linked_stack_leaves_no_local_file_and_falls_back(self):
        self.patch(run=lambda *args, **kwargs: 'origin/main\n')
        self.assertEqual(resolver.default_trunk(Path('/fixture'), self.common_dir), 'main')

    def test_graphite_trunk_takes_precedence_over_the_remote_default(self):
        (self.common_dir / '.graphite_repo_config').write_text(json.dumps({'trunk': '1.3.0'}))
        self.patch(run=lambda *args, **kwargs: self.fail('Graphite already supplies the trunk'))
        self.assertEqual(resolver.default_trunk(Path('/fixture'), self.common_dir), '1.3.0')

    def test_origin_head_supplies_a_default_when_no_tracker_is_configured(self):
        self.patch(run=lambda *args, **kwargs: 'origin/main\n')
        self.assertEqual(resolver.default_trunk(Path('/fixture'), self.common_dir), 'main')

    def test_missing_defaults_require_an_explicit_trunk(self):
        self.patch(run=lambda *args, **kwargs: None)
        with self.assertRaisesRegex(resolver.Failure, 'pass --trunk explicitly'):
            resolver.default_trunk(Path('/fixture'), self.common_dir)

    def test_unreadable_graphite_config_does_not_silently_choose_another_trunk(self):
        (self.common_dir / '.graphite_repo_config').write_text('{broken')
        with self.assertRaisesRegex(resolver.Failure, 'pass --trunk explicitly'):
            resolver.default_trunk(Path('/fixture'), self.common_dir)

    def test_unreadable_gh_stack_state_does_not_silently_choose_another_trunk(self):
        (self.common_dir / 'gh-stack').write_text('{broken')
        (self.common_dir / '.graphite_repo_config').write_text(json.dumps({'trunk': '1.3.0'}))
        with self.assertRaisesRegex(resolver.Failure, 'pass --trunk explicitly'):
            resolver.default_trunk(Path('/fixture'), self.common_dir)


class WalkTests(ResolverFixture):
    def setUp(self):
        # 1 -> 2 -> 3 on dev, plus an unrelated PR straight off dev.
        self.chain = [node(1, 'dev', 'a'), node(2, 'a', 'b'), node(3, 'b', 'c'), node(9, 'dev', 'z')]
        self.calls = []
        self.patch(merged_parent=lambda repo, branch: self.calls.append(branch) or None,
                   pull_request=lambda repo, number: self.fail(f'unexpected lookup of #{number}'))

    def walk(self, nodes, anchors):
        notes = []
        chain, children = resolver.walk(nodes, anchors, 'dev', 'acme/shop-api', notes)
        return [n['number'] for n in chain], [c['number'] for c in children], notes

    def test_ancestors_are_ordered_from_trunk_and_children_are_reported(self):
        order, children, notes = self.walk(self.chain, [2])
        self.assertEqual(order, [1, 2])
        self.assertEqual(children, [3])
        self.assertEqual(notes, [])

    def test_a_pr_on_trunk_resolves_to_itself_alone(self):
        order, children, _ = self.walk(self.chain, [9])
        self.assertEqual((order, children), ([9], []))

    def test_two_anchors_in_one_chain_are_not_duplicated(self):
        order, _, _ = self.walk(self.chain, [3, 2])
        self.assertEqual(order, [1, 2, 3])

    def test_a_fork_is_flagged_for_a_question(self):
        forked = self.chain + [node(4, 'b', 'd')]
        order, children, notes = self.walk(forked, [2])
        self.assertEqual(order, [1, 2])
        self.assertEqual(sorted(children), [3, 4])
        self.assertIn('FORK above #2', notes[0])
        self.assertIn('#3', notes[0])
        self.assertIn('#4', notes[0])

    def test_a_merged_parent_stops_the_chain_with_a_note(self):
        self.patch(merged_parent=lambda repo, branch: {'number': 7, 'state': 'MERGED'})
        order, _, notes = self.walk([node(8, 'landed-branch', 'h')], [8])
        self.assertEqual(order, [8])
        self.assertIn('sits on merged PR #7', notes[0])

    def test_an_unknown_base_records_desync_rather_than_guessing(self):
        order, _, notes = self.walk([node(8, 'vanished-branch', 'h')], [8])
        self.assertEqual(order, [8])
        self.assertIn('STACK DESYNC', notes[0])
        self.assertEqual(self.calls, ['vanished-branch'])

    def test_a_closed_anchor_is_looked_up_and_still_reviewed(self):
        landed = node(5, 'dev', 'e')
        self.patch(pull_request=lambda repo, number: {**landed, 'state': 'MERGED'})
        order, _, notes = self.walk(self.chain, [5])
        self.assertEqual(order, [5])
        self.assertIn('#5 is merged, not open', notes[0])


class ScopeTests(ResolverFixture):
    """Scope selection and record shape, with git and gh replaced by fixtures."""

    def setUp(self):
        self.chain = [node(1, 'dev', 'a'), node(2, 'a', 'b'), node(3, 'b', 'c', draft=True)]
        self.fetched = []
        self.checkouts = []

        def fake_run(args, **kwargs):
            if 'fetch' in args:
                self.fetched = args
                return ''
            raise AssertionError(f'unexpected run: {args}')

        def fake_git(repo, *args):
            self.checkouts.append(str(repo))
            if args[0] == 'remote':
                return 'git@github.com:acme/shop-api.git'
            if '--git-common-dir' in args:
                return '/fixture/shop-api/.git'
            if args[0] == 'rev-parse':
                return 'b' * 40
            if args[0] == 'merge-base':
                return 'b' * 40
            raise AssertionError(f'unexpected git: {args}')

        self.patch(run=fake_run, git=fake_git, is_ancestor=lambda *a: False,
                   resolvable=lambda repo, revision: revision or None,
                   open_pull_requests=lambda repo: (self.chain, 1))

    def resolve(self, scope):
        result, notes = resolver.resolve('acme/shop-api', [2], scope, 'dev', Path('/fixture/shop-api'))
        return result, notes

    def test_named_scope_reviews_only_the_anchor(self):
        result, _ = self.resolve('named')
        self.assertEqual([(p['number'], p['scope']) for p in result['prs']],
                         [(1, 'context'), (2, 'reviewed')])

    def test_stack_scope_reviews_the_chain_and_pulls_in_a_single_child(self):
        result, _ = self.resolve('stack')
        self.assertEqual([(p['number'], p['scope']) for p in result['prs']],
                         [(1, 'reviewed'), (2, 'reviewed'), (3, 'reviewed')])

    def test_the_chain_dependency_cites_one_shared_ancestry_source(self):
        result, _ = self.resolve('named')
        dependency = result['dependencies'][0]
        self.assertEqual(dependency['chain'], ['shop-api-1', 'shop-api-2'])
        self.assertEqual(dependency['label'], 'parent of')
        self.assertEqual(len(dependency['evidence']), 1)
        self.assertEqual(dependency['evidence'][0]['kind'], 'command')

    def test_every_in_scope_pr_is_fetched_into_a_disposable_review_ref(self):
        self.resolve('named')
        self.assertIn('+pull/1/head:refs/reviews/pr-1', self.fetched)
        self.assertIn('+pull/2/head:refs/reviews/pr-2', self.fetched)
        self.assertIn('+refs/heads/dev:refs/remotes/origin/dev', self.fetched)

    def test_drafts_are_named_once_and_urls_and_ids_are_filled_in(self):
        result, notes = self.resolve('stack')
        self.assertIn('draft: #3', notes)
        self.assertEqual([p['id'] for p in result['prs']], ['shop-api-1', 'shop-api-2', 'shop-api-3'])
        self.assertTrue(all(p['url'].startswith('https://') for p in result['prs']))
        self.assertEqual({p['repo'] for p in result['prs']}, {'acme/shop-api'})

    def test_a_landed_pr_is_named_rather_than_called_out_of_date(self):
        self.patch(is_ancestor=lambda *a: True)
        _, notes = self.resolve('named')
        self.assertIn('already in dev: #1, #2', notes)
        self.assertFalse([n for n in notes if 'NEEDS RESTACK' in n])

    def test_a_moved_parent_is_reported_against_the_recorded_base(self):
        self.chain[1]['baseRefOid'] = 'f' * 40      # #2 was cut before #1 advanced
        _, notes = self.resolve('named')
        restack = [n for n in notes if 'NEEDS RESTACK' in n]
        self.assertEqual(len(restack), 1)
        self.assertIn('#2 NEEDS RESTACK', restack[0])
        self.assertIn('parent #1 is now at', restack[0])

    def test_a_single_pr_scope_produces_no_dependency_edge(self):
        self.chain = [node(9, 'dev', 'z')]
        result, _ = resolver.resolve('acme/shop-api', [9], 'named', 'dev', Path('/fixture/shop-api'))
        self.assertEqual(result['dependencies'], [])

    def test_a_clone_pointing_at_another_repository_is_refused(self):
        self.patch(git=lambda repo, *args: 'git@github.com:acme/shop-web.git')
        with self.assertRaisesRegex(resolver.Failure, 'does not match github.com/acme/shop-api; pass --repo-path'):
            self.resolve('named')
        self.assertEqual(self.fetched, [])

    def test_a_bare_repository_name_is_refused_before_touching_git(self):
        with self.assertRaisesRegex(resolver.Failure, 'owner/name'):
            resolver.resolve('shop-api', [1], 'named', 'dev')
        self.assertEqual((self.checkouts, self.fetched), ([], []))

    def test_the_current_directory_is_the_default_checkout(self):
        result, _ = resolver.resolve('acme/shop-api', [2], 'named', 'dev')
        cwd = str(Path.cwd().resolve())
        self.assertEqual({p['repo_path'] for p in result['prs']}, {cwd})
        self.assertEqual(self.fetched[2], cwd)

    def test_an_explicit_clone_is_used_for_every_git_call(self):
        result, _ = resolver.resolve('acme/shop-api', [2], 'named', 'dev', Path('/fixture/other-worktree'))
        self.assertEqual([p['repo_path'] for p in result['prs']],
                         ['/fixture/other-worktree', '/fixture/other-worktree'])
        self.assertEqual(set(self.checkouts), {'/fixture/other-worktree'})
        self.assertEqual(self.fetched[2], '/fixture/other-worktree')

    def test_resolution_uses_the_checkout_default_without_an_override(self):
        self.chain = [node(9, 'main', 'z')]
        self.patch(default_trunk=lambda repo, common: 'main')
        resolver.resolve('acme/shop-api', [9], 'named', repo_path=Path('/fixture/shop-api'))
        self.assertIn('+refs/heads/main:refs/remotes/origin/main', self.fetched)

    def test_explicit_trunk_does_not_require_a_local_default(self):
        self.patch(default_trunk=lambda *args: self.fail('The explicit trunk takes precedence'))
        self.resolve('named')


class PackTests(unittest.TestCase):
    """The review pack and patch-ids, over a real fixture repository."""

    def setUp(self):
        sys.path.insert(0, str(SKILL / 'tests'))
        from fixture import make_repo
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name) / 'repo'
        self.shas = make_repo(self.repo)

    def result(self):
        prs = [{'id': f'shop-api-{n}', 'repo': 'acme/shop-api', 'number': n, 'title': title, 'scope': 'reviewed',
                'repo_path': str(self.repo), 'base': self.shas[base], 'head': self.shas[head]}
               for n, title, base, head in ((11, 'Schema', 'trunk', 'schema'), (12, 'Redeem', 'schema', 'redeem'))]
        bodies = {11: {'body': 'Implements specs/2026-11-20-gift-cards. Closes #77', 'draft': False},
                  12: {'body': 'x' * 5000, 'draft': True}}
        return {'prs': prs, 'dependencies': [], '_pack': {'trunk': 'dev', 'prs': bodies}}

    def test_the_pack_sorts_files_by_kind_and_links_the_spec(self):
        result = self.result()
        pack, notes = resolver.describe(result, {})
        self.assertNotIn('_pack', result)
        self.assertIn('| migration | `src/migrations/20261120-gift-cards.ts` | 8 | 0 |', pack)
        self.assertLess(pack.index('| migration |'), pack.index('| schema |'))
        self.assertIn('specs/2026-11-20-gift-cards, Closes #77', pack)
        self.assertIn('acme/shop-api #12 · reviewed · draft · Redeem', pack)
        self.assertIn('| route | `src/routes/giftCards.ts`', pack)
        self.assertIn('Risk surfaces by path: money', pack)
        self.assertIn('[body truncated at 4000 characters', pack)
        self.assertEqual(notes, [])

    def test_an_unchanged_patch_id_marks_the_review_reusable(self):
        first = self.result()
        resolver.describe(first, {})
        previous = {('acme/shop-api', 11): first['prs'][0]['patch_id'], ('acme/shop-api', 12): 'f' * 40}
        pack, notes = resolver.describe(self.result(), previous)
        self.assertEqual(notes, ['unchanged since the previous review (reuse its findings; rerun base-dependent '
                                 'checks): #11'])
        self.assertIn('(unchanged since the previous review)', pack)
        self.assertIn('(changed since the previous review)', pack)

    def test_paths_choose_kinds_and_surfaces(self):
        self.assertEqual(resolver.kind_of('src/__tests__/models/order.test.ts'), 'test')
        self.assertEqual(resolver.kind_of('package-lock.json'), 'generated')
        self.assertEqual(resolver.kind_of('apps/web/src/pages/Orders.tsx'), 'ui')
        self.assertEqual(resolver.kind_of('src/services/orders.ts'), 'code')
        self.assertEqual(resolver.surfaces_of(['src/styles/border.css']), [])
        self.assertEqual(resolver.surfaces_of(['src/webhooks/stripe.ts', 'src/auth/guard.ts']), ['auth', 'webhook'])


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Resolve a PR stack into the record's `prs` array, with pinned SHAs.

  resolve_stack.py acme/api 3121                          one PR reviewed, ancestry as context
  resolve_stack.py acme/api 3121 --scope stack            trunk-to-tip, every reachable PR reviewed
  resolve_stack.py acme/api 3121,3120 --scope named       only these reviewed, ancestry as context
  resolve_stack.py acme/web 42 --repo-path ~/src/web --append out.json   merge another repository
  resolve_stack.py acme/api 3121 --output prs.json --previous ~/.agent/reviews/<stamp>/review.json

The checkout is the current directory unless --repo-path names another; its
origin must be the named GitHub repository. Fetches each PR into
refs/reviews/pr-N so the pinned SHAs are readable locally; delete those refs
when the review is done.

One paginated GraphQL query gets the whole open-PR topology, so the chain is
walked locally instead of one `gh pr list` per link. Base SHAs are merge-bases
computed after a single fetch, never the raw branch tip.

Writes {"prs": [...]} to --output (default stdout) and prints a scope report,
fork warnings, and restack warnings to stderr. With --output or --append it also
writes the review pack beside that file (prs.json -> prs.pack.md): per PR, the
diff command, changed files by kind, risk surfaces, linked specs and issues, the
patch-id and the PR body. Every reviewer starts from that pack.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


REPOSITORY = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
QUERY = '''query($owner:String!,$repo:String!,$after:String){
  repository(owner:$owner,name:$repo){
    pullRequests(states:OPEN, first:100, after:$after){
      pageInfo{hasNextPage endCursor}
      nodes{number title body isDraft baseRefName headRefName headRefOid baseRefOid url}}}}'''

# Path patterns, first match wins. They sort a diff for reading; they decide nothing on their own.
FILE_KINDS = (
    ('generated', r'(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml)$|\.snap$|\.min\.(js|css)$'
                  r'|(^|/)(dist|build|generated|__generated__)/'),
    ('test', r'(^|/)(tests?|__tests__|e2e|fixtures?|__mocks__)/|\.(test|spec)\.[a-z]+$'),
    ('migration', r'migrat'),
    ('schema', r'(^|/)(models?|schemas?|entities)/|\.(model|schema|entity)\.[a-z]+$|prisma/schema|openapi|\.graphql$'),
    ('route', r'(^|/)(routes?|controllers?|handlers?|endpoints?|routers?)/|\.(controller|routes?|router|handler)\.[a-z]+$'),
    ('job', r'(^|/)(jobs?|queues?|workers?|crons?|schedulers?|consumers?|processors?)/'
            r'|\.(job|worker|queue|cron|consumer)\.[a-z]+$'),
    ('ui', r'\.(tsx|jsx|vue|svelte|css|scss|html)$|(^|/)(components|pages|screens|views)/'),
    ('config', r'(^|/)(\.github|infra|terraform|deploy|config)/|(^|/)(dockerfile|docker-compose[^/]*|package\.json'
               r'|tsconfig[^/]*\.json|\.env[^/]*)$|\.ya?ml$'),
    ('docs', r'\.(md|mdx|txt)$'),
)
KIND_ORDER = ('migration', 'schema', 'route', 'job', 'code', 'ui', 'config', 'test', 'docs', 'generated')
SURFACES = (
    ('money', r'pay|checkout|charge|refund|pric|amount|currenc|invoice|wallet|payout|billing|fee|tax|order'),
    ('auth', r'auth|permission|rbac|role|scope|guard|polic|session|token|oauth|login'),
    ('webhook', r'webhook'),
    ('upload', r'upload|presign|s3|storage'),
    ('import', r'import|csv|xlsx'),
    ('llm', r'llm|prompt|openai|anthropic|gemini|agent|(^|/)ai/'),
)
LINKS = (r'(?<![\w/-])specs/\d{4}-\d{2}-\d{2}-[a-z0-9-]+',
         r'(?i:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#\d+', r'https://linear\.app/[^\s)\]>]+',
         r'https://github\.com/[^\s)\]>]+/issues/\d+')
BODY_LIMIT = 4000


class Failure(Exception):
    pass


def run(args, check=True, **kwargs):
    """stdout on success. With check=False a non-zero exit returns None instead of raising."""
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode != 0:
        if not check:
            return None
        raise Failure(f"{' '.join(args[:4])}…: {result.stderr.strip().splitlines()[-1] if result.stderr.strip() else 'failed'}")
    return result.stdout


def git(repo, *args):
    return run(['git', '-C', str(repo), *args]).strip()


def matches_remote(remote, repo):
    """Match the complete GitHub identity (`owner/name`) for URL and scp-style Git remotes."""
    if '://' in remote:
        try:
            url = urlsplit(remote)
            host, path = url.hostname, url.path
        except ValueError:
            return False
    else:
        target, separator, path = remote.partition(':')
        if not separator:
            return False
        host = target.rsplit('@', 1)[-1]
    path = path.strip('/')
    if path.endswith('.git'):
        path = path[:-4]
    return host is not None and host.lower() == 'github.com' and path.lower() == repo.lower()


def configured_trunk(config, read):
    """A tracker's recorded trunk, or None when it records none for this checkout."""
    if not config.exists():
        return None
    try:
        settings = json.loads(config.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise Failure(f'Cannot read the trunk from {config}; pass --trunk explicitly') from error
    trunk = read(settings) if isinstance(settings, dict) else None
    return trunk if isinstance(trunk, str) and trunk.strip() else None


def stack_trunk(settings):
    """gh-stack records a trunk per stack, so only an unambiguous one is a default."""
    stacks = settings.get('stacks')
    if not isinstance(stacks, list):
        return None
    branches = set()
    for stack in stacks:
        trunk = stack.get('trunk') if isinstance(stack, dict) else None
        branch = trunk.get('branch') if isinstance(trunk, dict) else None
        if isinstance(branch, str) and branch.strip():
            branches.add(branch)
    return branches.pop() if len(branches) == 1 else None


def default_trunk(repo_path, common_dir):
    """Either stack tracker's configured trunk can differ from GitHub's default branch."""
    for config, read in ((common_dir / 'gh-stack', stack_trunk),
                         (common_dir / '.graphite_repo_config', lambda settings: settings.get('trunk'))):
        trunk = configured_trunk(config, read)
        if trunk:
            return trunk
    reference = run(['git', '-C', str(repo_path), 'symbolic-ref', '--quiet', '--short',
                     'refs/remotes/origin/HEAD'], check=False)
    if reference and reference.strip().startswith('origin/'):
        return reference.strip()[len('origin/'):]
    raise Failure(f'No configured trunk for {repo_path}; pass --trunk explicitly')


def open_pull_requests(repo):
    """Every open PR in the repository, in one query per 100."""
    owner, name = repo.split('/')
    nodes, after, calls = [], None, 0
    while True:
        args = ['gh', 'api', 'graphql', '-f', f'owner={owner}', '-f', f'repo={name}', '--field', f'query={QUERY}']
        if after:
            args += ['-f', f'after={after}']
        page = json.loads(run(args))['data']['repository']['pullRequests']
        nodes += page['nodes']
        calls += 1
        if not page['pageInfo']['hasNextPage']:
            return nodes, calls
        after = page['pageInfo']['endCursor']


def merged_parent(repo, branch):
    """Only consulted when the chain breaks: is the base branch a merged PR?"""
    rows = json.loads(run(['gh', 'pr', 'list', '--repo', repo, '--state', 'all', '--head', branch,
                           '--json', 'number,state,title,headRefName,baseRefName', '--limit', '5']))
    return next((r for r in rows if r['state'] == 'MERGED'), None)


def pull_request(repo, number):
    """One PR in any state, so a just-merged or closed anchor can still be reviewed."""
    return json.loads(run(['gh', 'pr', 'view', str(number), '--repo', repo, '--json',
                           'number,title,body,isDraft,baseRefName,headRefName,headRefOid,baseRefOid,url,state']))


def walk(nodes, anchors, trunk, repo, notes):
    """Ancestors of every anchor down to trunk, plus children above the topmost anchor."""
    by_head = {n['headRefName']: n for n in nodes}
    by_number = {n['number']: n for n in nodes}
    for number in anchors:
        if number in by_number:
            continue
        row = pull_request(repo, number)
        notes.append(f"#{number} is {row['state'].lower()}, not open; reviewing it at its recorded head")
        by_number[number] = row
        by_head.setdefault(row['headRefName'], row)
    chain, seen = [], set()
    for number in anchors:
        branch = []
        node = by_number[number]
        while node and node['number'] not in seen:
            branch.append(node)
            seen.add(node['number'])
            if node['baseRefName'] == trunk:
                break
            parent = by_head.get(node['baseRefName'])
            if not parent:
                merged = merged_parent(repo, node['baseRefName'])
                if merged:
                    notes.append(f"#{node['number']} sits on merged PR #{merged['number']} "
                                 f"({node['baseRefName']}); everything below it is already on {trunk}")
                else:
                    notes.append(f"STACK DESYNC: #{node['number']} bases on {node['baseRefName']}, "
                                 f"which is neither {trunk} nor an open PR; using merge-base with {trunk}")
                break
            node = parent
        chain = branch[::-1] + chain
    tip = chain[-1]
    children = [n for n in nodes if n['baseRefName'] == tip['headRefName']]
    if len(children) > 1:
        notes.append('FORK above #{}: open children {}. Ask which leg to review.'.format(
            tip['number'], ', '.join(f"#{c['number']}" for c in children)))
    return chain, children


def is_ancestor(repo_path, commit, ref):
    """True when `commit` is already contained in `ref`."""
    return run(['git', '-C', str(repo_path), 'merge-base', '--is-ancestor', commit, ref],
               check=False) is not None


def resolvable(repo_path, revision):
    try:
        return git(repo_path, 'rev-parse', f'{revision}^{{commit}}')
    except Failure:
        return None


def pin(repo_path, node, parent, trunk, notes):
    """Head, plus the commit this PR's own diff starts from.

    The PR's recorded `baseRefOid` is preferred over the base branch tip: the tip
    moves on, and once a PR lands the tip contains its head, which would make the
    diff empty. The recorded OID survives even a deleted base branch.
    """
    number, head = node['number'], node['headRefOid']
    base_ref = node['baseRefName']
    base = resolvable(repo_path, node.get('baseRefOid') or '')
    if not base:
        base = resolvable(repo_path, f'origin/{base_ref}')
        if base:
            notes.append(f"#{number}: recorded base commit is not local; used the current "
                         f'{base_ref} tip, so its diff may include parent changes')
        else:
            base = git(repo_path, 'rev-parse', f'origin/{trunk}^{{commit}}')
            notes.append(f'#{number}: neither the recorded base nor {base_ref} is local; '
                         f'diffed against origin/{trunk}')
    base = git(repo_path, 'merge-base', base, head)
    if parent and parent['headRefOid'] != node.get('baseRefOid'):
        notes.append(f"#{number} NEEDS RESTACK: it is based on {str(node.get('baseRefOid'))[:10]} "
                     f"but parent #{parent['number']} is now at {parent['headRefOid'][:10]}")
    return base, head


def resolve(repo, anchors, scope, trunk=None, repo_path=None):
    notes = []
    if not REPOSITORY.fullmatch(repo):
        raise Failure(f'Name the repository as owner/name, not {repo!r}')
    repo_path = Path(repo_path or Path.cwd()).expanduser().resolve()
    common_dir = Path(git(repo_path, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
    remote = git(repo_path, 'remote', 'get-url', 'origin')
    if not matches_remote(remote, repo):
        raise Failure(f'{repo_path} origin does not match github.com/{repo}; pass --repo-path to a clone of it')
    trunk = trunk or default_trunk(repo_path, common_dir)
    nodes, calls = open_pull_requests(repo)
    chain, children = walk(nodes, anchors, trunk, repo, notes)
    if scope == 'stack':
        chain = chain + children[:1] if len(children) == 1 else chain
    reviewed = ({n['number'] for n in chain} if scope == 'stack'
                else {chain[-1]['number']} if scope == 'this' else set(anchors))
    fetch = ['+refs/heads/{0}:refs/remotes/origin/{0}'.format(trunk)]
    fetch += [f"+pull/{n['number']}/head:refs/reviews/pr-{n['number']}" for n in chain]
    run(['git', '-C', str(repo_path), 'fetch', '--force', '--quiet', 'origin', *fetch])
    prs = []
    heads = {n['headRefName']: n for n in chain}
    for node in chain:
        base, head = pin(repo_path, node, heads.get(node['baseRefName']), trunk, notes)
        prs.append({'id': f"{repo.split('/')[1]}-{node['number']}",
                    'repo': repo, 'repo_path': str(repo_path), 'number': node['number'], 'title': node['title'],
                    'base': base, 'head': head,
                    'scope': 'reviewed' if node['number'] in reviewed else 'context',
                    'url': node['url'] or f"https://github.com/{repo}/pull/{node['number']}"})
    landed = [p['number'] for p in prs
              if is_ancestor(repo_path, p['head'], f'refs/remotes/origin/{trunk}')]
    if landed:
        notes.append(f"already in {trunk}: {', '.join('#' + str(n) for n in landed)}")
    drafts = [n['number'] for n in chain if n.get('isDraft')]
    if drafts:
        notes.append(f"draft: {', '.join('#' + str(n) for n in drafts)}")
    chained = [p['id'] for p in prs]
    dependency = ([{'chain': chained, 'label': 'parent of', 'evidence': [
        {'kind': 'command', 'pr': chained[0], 'label': 'stack ancestry',
         'revision': prs[0]['head'],
         'detail': f'Resolved from the open-PR topology of {repo} in {calls} GraphQL '
                   f'query(ies); each base branch is the previous PR\'s head, and every base SHA '
                   f'below is the merge-base of that PR with its base branch.'}]}]
        if len(chained) > 1 else [])
    notes.append(f'{calls} GraphQL query(ies), {len(nodes)} open PRs scanned, {len(chain)} in scope '
                 f"({len(reviewed)} reviewed)")
    bodies = {n['number']: {'body': n.get('body') or '', 'draft': bool(n.get('isDraft'))} for n in chain}
    return {'prs': prs, 'dependencies': dependency, '_pack': {'trunk': trunk, 'prs': bodies}}, notes


def kind_of(path):
    lowered = path.lower()
    return next((kind for kind, pattern in FILE_KINDS if re.search(pattern, lowered)), 'code')


def surfaces_of(paths):
    found = []
    for name, pattern in SURFACES:
        if any(re.search(rf'(?<![a-z])(?:{pattern})', path.lower()) for path in paths):
            found.append(name)
    return found


def patch_id(repo_path, base, head):
    """Stable across rebases: an unchanged patch-id means the change itself is unchanged."""
    diff = subprocess.run(['git', '-C', str(repo_path), 'diff', base, head], capture_output=True, check=True).stdout
    if not diff:
        return None
    result = subprocess.run(['git', '-C', str(repo_path), 'patch-id', '--stable'], input=diff, capture_output=True,
                            check=True).stdout.decode().split()
    return result[0] if result else None


def previous_patch_ids(path):
    """PR key -> patch-id from an earlier review.json or prs.json."""
    if not path:
        return {}
    data = json.loads(Path(path).expanduser().read_text())
    return {(p.get('repo'), p.get('number')): p.get('patch_id') for p in data.get('prs', []) if p.get('patch_id')}


def describe(result, previous):
    """Attach patch-ids to this repository's PRs and write their section of the review pack."""
    pack = result.pop('_pack')
    lines, notes, unchanged = [], [], []
    for pr in result['prs']:
        repo_path, base, head = pr['repo_path'], pr['base'], pr['head']
        pr['patch_id'] = patch_id(repo_path, base, head)
        before = previous.get((pr['repo'], pr['number']))
        if before and before == pr['patch_id']:
            unchanged.append(pr['number'])
        numstat = run(['git', '-C', repo_path, 'diff', '--numstat', '--no-renames', base, head]).splitlines()
        files = []
        for row in numstat:
            added, deleted, path = row.split('\t', 2)
            files.append((kind_of(path), path, added, deleted))
        files.sort(key=lambda item: (KIND_ORDER.index(item[0]), item[1]))
        totals = {}
        for kind, _, added, deleted in files:
            plus, minus = totals.get(kind, (0, 0))
            totals[kind] = (plus + (int(added) if added.isdigit() else 0), minus + (int(deleted) if deleted.isdigit() else 0))
        body = pack['prs'].get(pr['number'], {}).get('body', '')
        links = list(dict.fromkeys(match.group(0) for pattern in LINKS for match in re.finditer(pattern, body)))
        state = ('unchanged since the previous review' if before and before == pr['patch_id']
                 else 'changed since the previous review' if before else 'no previous review')
        flags = ['draft'] if pack['prs'].get(pr['number'], {}).get('draft') else []
        lines += [f"## {pr['repo']} #{pr['number']} · {pr['scope']}{' · ' + ', '.join(flags) if flags else ''} · {pr['title']}",
                  '',
                  f"- Diff: `git -C {repo_path} diff {base}..{head}`",
                  f"- Size: {len(files)} files; " + ', '.join(f'{kind} +{p} −{m}' for kind, (p, m) in
                                                         sorted(totals.items(), key=lambda kv: KIND_ORDER.index(kv[0]))),
                  f"- Patch-id: {pr['patch_id'] or 'empty diff'} ({state})",
                  f"- Risk surfaces by path: {', '.join(surfaces_of([f[1] for f in files])) or 'none matched'}",
                  f"- Linked: {', '.join(links) or 'nothing linked in the body'}",
                  '', '| Kind | File | + | − |', '|---|---|---|---|']
        generated = [f for f in files if f[0] == 'generated']
        lines += [f'| {kind} | `{path}` | {added} | {deleted} |' for kind, path, added, deleted in files if kind != 'generated']
        if generated:
            lines.append(f'| generated | {len(generated)} files (lockfiles, snapshots, build output) | | |')
        text = body.strip() or '(empty)'
        if len(text) > BODY_LIMIT:
            text = text[:BODY_LIMIT].rstrip() + f'\n\n[body truncated at {BODY_LIMIT} characters; read it with gh pr view]'
        lines += ['', '### PR body (intent, not proof)', '', text, '']
    if unchanged:
        notes.append('unchanged since the previous review (reuse its findings; rerun base-dependent checks): '
                     + ', '.join(f'#{n}' for n in unchanged))
    repo = result['prs'][0]['repo'] if result['prs'] else 'repository'
    header = [f"# Review pack · {repo} (trunk {pack['trunk']})", '',
              f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}. Read pinned Git objects "
              '(`git show <sha>:<file>`, `git grep <pattern> <sha>`); never check out a branch. Kinds and risk '
              'surfaces come from file paths only: they order the reading, they are not findings.', '']
    return '\n'.join(header + lines) + '\n', notes


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('repo', help='GitHub repository as owner/name, e.g. acme/api')
    parser.add_argument('anchors', help='PR number, or a comma-separated list')
    parser.add_argument('--scope', choices=('named', 'this', 'stack'), default='named',
                        help='named: only the listed PRs reviewed (default). this: only the topmost. '
                             'stack: every PR trunk-to-tip reviewed')
    parser.add_argument('--trunk', help='Override the configured gh-stack or Graphite trunk and the origin/HEAD default')
    parser.add_argument('--repo-path', type=Path, help='Local clone or worktree of the repository (default: the current directory)')
    parser.add_argument('--output', type=Path, help='Write JSON here instead of stdout')
    parser.add_argument('--append', type=Path, help='Merge into this existing record/prs JSON file')
    parser.add_argument('--previous', type=Path, help='An earlier review.json or prs.json: PRs whose patch-id is '
                                                      'unchanged since then are named so their review can be reused')
    args = parser.parse_args()
    try:
        anchors = [int(n) for n in args.anchors.split(',') if n.strip()]
        if not anchors:
            raise ValueError
    except ValueError:
        parser.exit(2, 'anchors must be one or more PR numbers\n')
    try:
        result, notes = resolve(args.repo, anchors, args.scope, args.trunk, args.repo_path)
        pack, pack_notes = describe(result, previous_patch_ids(args.previous))
        notes += pack_notes
        target = args.append or args.output
        if target:
            pack_path = target.with_suffix('.pack.md')
            with pack_path.open('a' if args.append and pack_path.exists() else 'w') as handle:
                handle.write(pack if handle.tell() == 0 else '\n' + pack)
            notes.append(f'review pack: {pack_path}')
        if args.append:
            existing = json.loads(args.append.read_text()) if args.append.exists() else {}
            known = {p['id'] for p in existing.get('prs', [])}
            existing['prs'] = existing.get('prs', []) + [p for p in result['prs'] if p['id'] not in known]
            existing['dependencies'] = existing.get('dependencies', []) + result['dependencies']
            result = existing
            args.append.write_text(json.dumps(result, indent=1) + '\n')
            notes.append(f'merged into {args.append}')
        text = json.dumps(result, indent=1) + '\n'
        if args.output:
            args.output.write_text(text)
            print(args.output)
        elif not args.append:
            print(text, end='')
        for note in notes:
            print(note, file=sys.stderr)
    except (Failure, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Stack resolution failed: {error}\n')


if __name__ == '__main__':
    main()

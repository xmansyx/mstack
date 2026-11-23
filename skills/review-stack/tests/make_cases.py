#!/usr/bin/env python3
"""Create immutable, controlled review cases without touching product repositories."""

import argparse
import json
from pathlib import Path
import subprocess


def make_cases(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    repo = directory / 'seat-picker'
    repo.mkdir()

    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()

    def commit(files, title):
        for path, text in files.items():
            destination = repo / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text)
        git('add', '.')
        git('commit', '-qm', title)
        return git('rev-parse', 'HEAD')

    git('init', '-q')
    git('config', 'user.name', 'Fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    base = commit({'README.txt': 'Controlled seat-picker review fixtures. No live service or customer data.\n'}, 'Fixture base')
    clean = commit({'src/query.py': 'from urllib.parse import urlencode\n\ndef seat_url(seat_id):\n    return "/seats?" + urlencode({"id": seat_id})\n'}, 'Encode seat identifiers in URLs')
    middle = commit({'src/selection.js': 'function selectedSeatId(seat) {\n  return seat.id;\n}\nmodule.exports = { selectedSeatId };\n'}, 'Read the selected seat identifier')
    tip = commit({'src/selection.js': 'function selectedSeatId(seat) {\n  if (seat === null) return null;\n  return seat.id;\n}\nmodule.exports = { selectedSeatId };\n'}, 'Support cleared selections')
    ui = commit({'src/retry.html': '''<!doctype html>
<html lang="en"><meta charset="utf-8"><title>Seat refresh</title>
<button id="retry">Refresh seats</button><p id="status" role="status"></p>
<script>
const button = document.getElementById('retry');
const status = document.getElementById('status');
async function refreshSeats(load) {
  button.disabled = true;
  try {
    await load();
    status.textContent = 'Seats refreshed';
  } catch (error) {
    status.textContent = 'Refresh failed. Try again.';
    return;
  }
  button.disabled = false;
}
button.addEventListener('click', () => refreshSeats(() => Promise.reject(new Error('Offline'))));
</script></html>
'''}, 'Allow retry after a seat refresh failure')
    pairs = [(501,base,clean,'Encode seat identifiers in URLs'), (502,clean,middle,'Read the selected seat identifier'),
             (503,middle,tip,'Support cleared selections'), (504,tip,ui,'Allow retry after a seat refresh failure')]
    prs = [{'number':num,'base':parent,'head':head,'title':title,'repo':'acme/seat-picker','repo_path':str(repo)}
           for num,parent,head,title in pairs]
    (directory/'scope.json').write_text(json.dumps(prs,indent=2)+'\n')
    packet = f'''Review exactly the four synthetic seat-picker PRs listed in scope.json using the supplied review-stack skill.
Use the pinned Git revisions in {repo}; resolution is already provided. No network, ref changes, branch checkouts, or product edits are needed.
These are small controlled fixtures, not a production checkout. Code consists only of the committed fixture files; there are no hidden services or package dependencies.
The four PRs form a chain in the listed order. Review the full supplied scope and consider later PRs when judging earlier work.

Requirements:
- #501: seat_url accepts a string seat identifier and returns a /seats URL whose id query parameter decodes to the original string, including spaces and ampersands.
- #502 and #503 together: selectedSeatId accepts an object with a string id or null. It returns that id or null respectively.
- #504: the refresh button is disabled while loading. Successful and failed attempts both leave it usable again; a failed attempt displays an error.

Produce the review prescribed by the supplied skill. Keep every artifact outside the fixture repository. Report actual checks and gaps. Do not read evaluation.md or any expected-answer file.
'''
    (directory/'request.txt').write_text(packet)
    print(directory/'request.txt')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    make_cases(parser.parse_args().directory)

#!/usr/bin/env python3
"""Create a clearly labelled explainer demo: a synthetic gift-card stack and its compact record."""

import argparse
import json
from pathlib import Path

from fixture import demo_record, make_repo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    target = args.directory.resolve()
    target.mkdir(parents=True, exist_ok=False)
    shas = make_repo(target / 'repo')
    source = target / 'input.json'
    source.write_text(json.dumps(demo_record(target / 'repo', shas), indent=2, ensure_ascii=False) + '\n')
    print(source)


if __name__ == '__main__':
    main()

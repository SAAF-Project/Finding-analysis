"""Check AUDIT-CRITERIA.md and llm_checks.yaml against the SAAF template, and against each other.

In a repo made from the SAAF agent-template, run its own `python3 scripts/check_standards.py` first: it reports
[llm] criteria without a check, checks without a criterion, duplicates and placeholders. This script is the fallback
for repos without it, and adds what it does not check: the six sections, lines without a tag or number (step 0),
numbers under the wrong heading or column, duplicate criteria, gaps, valid YAML and empty fields.

    python validate_criteria.py [AUDIT-CRITERIA.md] [llm_checks.yaml]

Without arguments it reads both from the current folder (llm_checks.yaml, else evals/llm_checks.yaml).
Errors exit 1, with the line they are on. A gap in the numbering is only a warning: a removed number is not reused.
Needs Python 3.9+ and pyyaml.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SECTIONS = {  # template heading: words one of the headings must contain
    'Metadata': 'metadata',
    '1. What the agent does': 'what the agent does',
    '2. Control objectives & framework mapping (≥3)': 'control objective',
    '3. Acceptance criteria (testable, pass/fail)': 'acceptance criteria',
    '4. Good output / never do': 'good output',
    '5. Coverage gaps': 'coverage gaps',
    '6. Status / validation': 'status',
}
TAG = re.compile(r'\[(code|llm)\]', re.IGNORECASE)
BULLET = re.compile(r'^\s*-\s*(?:\[(code|llm)\]\s*(CO-\d+\.\d+)|(CO-\d+\.\d+)\s*\[(code|llm)\])\s+(.*)$', re.IGNORECASE)
TABLE_ID = re.compile(r'^([MN])-(\d+)$')
PLACEHOLDER = re.compile(r'\[(placeholder|one sentence)[^\]]*\]', re.IGNORECASE)
TEMPLATE = 'https://github.com/SAAF-Project/agent-template/blob/saaf/numbered-criteria/AUDIT-CRITERIA.md'  # main once PR #5 merges
FIELDS = ('id', 'name', 'look_for', 'pass_when')


@dataclass
class Criterion:
    id: str
    tag: str
    text: str
    line: int


@dataclass
class Report:
    criteria: list[Criterion] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def llm_checks(self) -> list[dict]:
        """Every check whose criterion is tagged [llm], with the criterion text added under `criterion`."""
        llm = {c.id: c for c in self.criteria if c.tag == 'llm'}
        return [{**ch, 'criterion': llm[ch['id']].text} for ch in self.checks if ch.get('id') in llm]


def _clean(text: str) -> str:
    return re.sub(r'\s*\*\(.*?\)\*\s*$', '', text).strip()  # drop a trailing *(test refs)*


def parse_criteria(text: str, where: str = 'AUDIT-CRITERIA.md', report: Report | None = None) -> Report:
    """The numbered criteria of sections 3 (bullets under **CO-n**) and 4 (table cells with M-n / N-n)."""
    r = report or Report()
    headings = [line.lstrip('#').strip().lower() for line in text.splitlines() if line.startswith('## ')]
    for name, words in SECTIONS.items():
        if not any(words in h for h in headings):
            r.errors.append(f'{where}: no section "## {name}"')
    section, co = '', None
    for n, line in enumerate(text.splitlines(), start=1):
        at = f'{where}:{n}'
        if line.startswith('## '):
            section, co = line.lower(), None
            continue
        if 'acceptance criteria' in section:
            if m := re.match(r'^\s*\*\*(CO-\d+)\*\*', line):
                co = m.group(1)
            elif re.match(r'^\s*-\s', line):
                tags = TAG.findall(line)
                m = BULLET.match(line)
                if len(tags) != 1 or not m:
                    r.errors.append(f'{at}: a criterion needs one tag and one number first: "- [llm] CO-1.2 Given ..."')
                    continue
                cid, tag = (m.group(2), m.group(1)) if m.group(2) else (m.group(3), m.group(4))
                if co is None or not cid.startswith(co + '.'):
                    r.errors.append(f'{at}: {cid} is not under its heading **{cid.split(".")[0]}**')
                if '…' in line:
                    r.errors.append(f'{at}: {cid} is still a template placeholder (…)')
                r.criteria.append(Criterion(id=cid.upper(), tag=tag.lower(), text=_clean(m.group(5)), line=n))
        elif 'good output' in section and line.lstrip().startswith('|'):
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            for i, cell in enumerate(cells):
                mark = re.match(r'^([✓✕])\s*(.*)$', cell)
                if not mark:
                    continue
                tags = TAG.findall(cell)
                want = 'M' if mark.group(1) == '✓' else 'N'
                prev = cells[i - 1] if i else ''
                idm = TABLE_ID.match(prev)
                if len(tags) != 1 or not idm:
                    r.errors.append(f'{at}: "{cell[:40]}" needs one tag, with its number ({want}-n) in the cell before')
                    continue
                if idm.group(1) != want:
                    r.errors.append(f'{at}: {prev} holds a {mark.group(1)} cell; use {want}-n')
                if '…' in cell:
                    r.errors.append(f'{at}: {prev} is still a template placeholder (…)')
                body = TAG.sub('', mark.group(2), count=1).strip()
                r.criteria.append(Criterion(id=prev, tag=tags[0].lower(), text=_clean(body), line=n))
    seen: dict[str, int] = {}
    for c in r.criteria:
        if c.id in seen:
            r.errors.append(f'{where}:{c.line}: {c.id} is used twice (also line {seen[c.id]})')
        seen.setdefault(c.id, c.line)
    groups: dict[str, list[int]] = {}
    for cid in seen:
        head, _, num = cid.rpartition('.') if '.' in cid else cid.partition('-')
        groups.setdefault(head, []).append(int(num))
    for head, nums in groups.items():
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        if missing:
            sep = '.' if head.startswith('CO') else '-'
            r.warnings.append(f'{where}: no {", ".join(f"{head}{sep}{m}" for m in missing)} (fine if removed)')
    return r


def parse_checks(text: str, report: Report, where: str = 'llm_checks.yaml') -> Report:
    """llm_checks.yaml against the [llm] criteria: one complete check per [llm] number, nothing else."""
    import yaml

    try:
        data = yaml.safe_load(text) or []
    except yaml.YAMLError as e:
        report.errors.append(f'{where}: not valid YAML: {e}')
        return report
    if not isinstance(data, list) or not all(isinstance(d, dict) for d in data):
        report.errors.append(f'{where}: must be a list of checks, each with {", ".join(FIELDS)}')
        return report
    tags = {c.id: c.tag for c in report.criteria}
    ids = [str(d.get('id', '')).upper() for d in data]
    for d in data:
        d['id'] = cid = str(d.get('id', '')).upper()
        empty = [f for f in FIELDS if not str(d.get(f) or '').strip()]
        if empty:
            report.errors.append(f'{where}: check {cid or "?"} has no {", ".join(empty)}')
        if any(PLACEHOLDER.search(str(d.get(f) or '')) for f in FIELDS):
            report.errors.append(f'{where}: check {cid} is still a placeholder')
        if cid not in tags:
            report.errors.append(f'{where}: check {cid} has no criterion with that number')
        elif tags[cid] != 'llm':
            report.errors.append(f'{where}: check {cid} belongs to a [code] criterion; a program decides that one')
    report.errors += [
        f'{where}: check {i} appears {ids.count(i)} times' for i in dict.fromkeys(ids) if ids.count(i) > 1
    ]
    report.checks = data
    for c in report.criteria:
        if c.tag == 'llm' and c.id not in ids:
            report.errors.append(
                f'NO CHECK {c.id}: criterion line {c.line} is tagged [llm] but has no check in {where}'
            )
    return report


def validate(criteria_path: Path, checks_path: Path | None) -> Report:
    r = parse_criteria(text=criteria_path.read_text(encoding='utf-8'), where=criteria_path.name)
    if checks_path is None or not checks_path.is_file():
        r.errors += [f'NO CHECK {c.id}: no llm_checks.yaml yet' for c in r.criteria if c.tag == 'llm']
        return r
    return parse_checks(text=checks_path.read_text(encoding='utf-8'), report=r, where=checks_path.name)


def find_checks(root: Path) -> Path | None:
    return next((p for p in (root / 'llm_checks.yaml', root / 'evals/llm_checks.yaml') if p.is_file()), None)


def main(argv: list[str]) -> int:
    criteria = Path(argv[0]) if argv else Path('AUDIT-CRITERIA.md')
    if not criteria.is_file():
        print(f'error: no {criteria}')
        return 1
    checks = Path(argv[1]) if len(argv) > 1 else find_checks(root=criteria.parent)
    r = validate(criteria_path=criteria, checks_path=checks)
    llm = [c.id for c in r.criteria if c.tag == 'llm']
    written = [c for c in r.llm_checks() if not any(PLACEHOLDER.search(str(c.get(f) or '')) for f in FIELDS)]
    print(f'{len(r.criteria)} criteria ({len(llm)} [llm]); {len(written)} of {len(llm)} have a check')
    if any('one tag and one number' in e or 'no section' in e for e in r.errors):
        print(f'format: {TEMPLATE}')
    for w in r.warnings:
        print(f'warning: {w}')
    for e in r.errors:
        print(f'error: {e}')
    return 1 if r.errors else 0


if __name__ == '__main__':
    sys.exit(main(argv=sys.argv[1:]))

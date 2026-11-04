# Finding-analysis
The AuditRepAnalysis agent automates previous audit report reviews by analyzing historical findings and scoring their relevance to current audit objectives. It filters key issues for follow-up and drafts new findings with risk scores, saving time and removing subjectivity for auditors preparing for engagements.

## Input

- Historical audit documents: PDF, PPTX, XLSX, DOCX or images, uploaded in the browser or fetched from a SharePoint folder.
- Optional: the engagement letter of the current audit (PDF or DOCX) and free-text keywords to focus the analysis.
- A lookback period of 1–10 years.
- An Anthropic API key.

## Output

A Dutch-language overview, shown in the browser and downloadable as HTML, Word and PDF:

- relevant historical findings, each with source file, year, why it is relevant now, and a priority (Hoog / Middel / Laag);
- additional points of attention for the auditor;
- a short summary.

The overview is an AI-generated planning aid. It needs review by the auditor before use.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optional: set ANTHROPIC_API_KEY, or enter the key in the UI
python app.py
```

Then open http://localhost:5000. Run it on your own machine only: there is no login, and uploaded documents stay in `uploads/` until you delete them. Document content is sent to the Anthropic API.

## Audit criteria

See [AUDIT-CRITERIA.md](AUDIT-CRITERIA.md) for the control objectives, acceptance criteria and known limits of this agent.

## Prerequisites

- Python: TODO(owner): state the supported Python version(s).
- An Anthropic API key. Set it in the `ANTHROPIC_API_KEY` environment variable (or a local `.env` file, copied from `.env.example`, which is git-ignored), or enter it in the UI. `FLASK_SECRET_KEY` is read from the environment too. Never commit a real key.
- Optional: SharePoint credentials, entered in the UI, if you fetch documents from SharePoint.

## Model and data residency

- Model: `claude-opus-4-6` via the Anthropic Messages API (`agent/audit_agent.py`). One request per analysis.
- Where data goes: the extracted text of every uploaded document, the engagement letter and the keywords are sent to the Anthropic API, a hosted service. Uploaded files also stay on the local disk in `uploads/` until you delete them.
- TODO(owner): state the region where the provider processes and retains the data, and whether a local or EU-hosted option is supported.

## Limitations and human review

The overview is an AI-generated planning aid. It is not evidence and not a finding in its own right; the auditor must review it before use. Known limits, detailed in [AUDIT-CRITERIA.md](AUDIT-CRITERIA.md) sections 3, 5 and 6:

- Only the first part of each file is read (4,000 characters per file, 15 pages per PDF, 60 rows per sheet, 4 images per run), and the report does not say what was skipped or truncated.
- Scanned PDFs are not read (no OCR).
- Findings point to a file name only, not to a page or quote.
- Local single-user prototype: no login, Flask development server with `debug=True`. Do not expose it on a network.

## Guardrails

The code follows the SAAF command allowlist (`regulatory/guardrails/allowed-commands.md` in the main SAAF-Project repo). The Python code runs no shell commands (no `rm`, `sudo`, `curl`, `wget`, `ssh`, `scp`, `chmod`, `chown` or `cron`) and does not `pip install` at runtime.

## License and contact

- License: TODO(owner): licence to be decided by Stichting SAAF.
- Maintainer: Amber van der Weijden (see the metadata in [AUDIT-CRITERIA.md](AUDIT-CRITERIA.md)). TODO(owner): add a preferred contact channel.
- Plan: TODO(owner): link the plan in `SAAF-Project/plans/` if one exists. None was found during the 2026-11 standards audit.

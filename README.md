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

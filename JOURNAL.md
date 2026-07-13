# Module 3 Journal

## Week 7 — Issue selection

**Issue link:** https://github.com/jamjamgobambam/pathreview/issues/12

**Issue title:** Support multi-page resume PDFs

**Tier:** [ ] Tier 1  [x] Tier 2  [ ] Tier 3

**Problem summary:**
PathReview builds a candidate profile from an uploaded resume, and this issue reports that the PDF path in the ingestion pipeline only captures the first page. For anyone with a longer resume (two pages is normal after a few years of experience), everything past page one gets dropped before it reaches the rest of the pipeline, so reviews end up generated from an incomplete picture of the person. The affected code is `ResumeParser._parse_pdf` in `ingestion/parsers/resume_parser.py`. A successful fix extracts and joins the text from every page, records the real page count in the parse metadata, and proves the behavior with a multi-page PDF fixture and unit tests.

**Branch name:** feat/12-multi-page-resume-pdfs

**Setup confirmation:** [x] App runs locally at localhost:5173

**Cohort ledger:** [ ] Issue added to cohort ledger

### Selection notes ("Is this right for me?")

- Scope fits the estimate. The change lives in one parser file plus a test fixture, with no schema, API, or frontend work, which matches the 3 to 5 hour tier 2 estimate.
- I understand the code involved. `resume_parser.py` is about 150 lines of plain Python on top of pypdf, and I can already follow the parse path from raw bytes to `ParseResult`.
- It is testable. A two-page sample PDF in `tests/fixtures/` plus a unit test asserting that text from both pages shows up in the parsed output will prove the fix.
- Risk is low. The `ParseResult` contract stays the same, so downstream pipeline stages should not need changes.
- One thing I noticed on a first read: the current `_parse_pdf` loop already iterates over `pdf_reader.pages`, and the upload route in `api/routes/profiles.py` does too. So my first task is reproducing the single-page behavior with a real two-page resume to find where content actually gets lost. If the loop turns out to be fine, the work shifts to locking multi-page support in with fixtures and tests so it can't regress.

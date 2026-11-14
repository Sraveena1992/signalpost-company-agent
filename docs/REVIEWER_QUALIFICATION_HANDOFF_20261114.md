# SIGNALPOST — reviewer qualification technical handoff, 14 November 2026

## Shipping status (actually verified)
- Production `main` merged PR #48 with squash SHA `659aa1a374a9ecb103170b9de0207cef3e743ff0`.
- Live Render: https://signalpost-company-agent.onrender.com/
- Read-only live content audit: https://github.com/Sraveena1992/signalpost-company-agent/actions/runs/43603847608 **PASS**: source-linked dated noticeboard article and historical-vacancy disclaimer are visible.
- 100-company fresh smoke: https://github.com/Sraveena1992/signalpost-company-agent/actions/runs/43601907928 **PASS**, exactly 100 profiles/envelopes, validation.
- Latest 500-company all-ten-module run: https://github.com/Sraveena1992/signalpost-company-agent/actions/runs/43601907908 **PASS**, 500 fresh profiles/envelopes, 7,673 synthesis claims with URL/time, one company-owned dated news item, no verified active site jobs.
- Genuine dated source: Norwegian org `987531630` 1. ÅS SPEIDERGRUPPE; publication May 14 2026 https://aas.speiding.no/oppslagstavle/utlysning-sommerjobb-som-aktivitetsledere/ . Historical recruitment item, NOT active job. Exact live research source proof: https://github.com/Sraveena1992/signalpost-company-agent/actions/runs/43601901869
- 194 tests + 7 subtests, browser E2E and security audit passed on reviewer PR; main post-merge CI passed.

## Real remaining blockers
1. **Official qualification** requires submitting the exact main SHA and official Builderr evaluation. We cannot self-award >=65/100; unknown until evaluator runs. User says >=95% of checked claims right, with >=65 points.
2. **Independent accuracy**: `scripts/verify_all_claims_live.py` freshly re-fetches sources but is NOT an independent adjudicated gold-label benchmark. Earlier 7,671 of 7,672 corroborated; updated 7,673-claim recheck now runs in isolated branch. If a checked factual assertion lacks a stable gold label, mark `unknown`/human-review, NOT correct.
3. **Active company-site jobs** remain zero in exact 500 set. NAV authenticated feed opt-in connector is in separate draft PR #47; 45-day experimental feed scan looked at 29,028 events and 9,194 active headers, but 2 probable company-name leads failed exact employer orgnr. Never substitute unrelated vacancy from another employer. Reviewer quote asks **one dated item OR an open posting**; dated item is already real and implemented.
4. **News breadth**: only one genuine company-owned dated item in latest 500. Increase recall through permitted targeted detail-page discovery while keeping legal-company attribution; avoid counting RSS-only or index pages as original articles.

## Quick next steps for another coding agent
- Read the reviewer feedback *verbatim*; ascertain whether single dated item satisfies the 'or' condition and whether other expected fields are compulsory.
- Verify main and Render currently contain PR #48 evidence and no regressions.
- Fetch workflow 43601907908 artifacts and independent recheck (see `audit/live-reviewer-proof-20261114`).
- Generate category-stratified independent gold labels from source records independent of predictions, with real adjudication. Calculate TP/FP/FN, Wilson intervals and claim-level precision, with missing as unknown rather than success.
- If more jobs are needed, use official NAV permitted feed / company source with exact `employer.orgnr` and current status, never count parent-company jobs as subsidiary jobs.
- Do not modify `main`, deploy, add fictitious company records, change input membership, or manufacture scores without explicit approval.
- If Builderr supports CLI/API submission, verify real docs before submitting. Preserve exact commit hash and official output; do not invent evaluator scores.

## Independent audit fix in this branch
`scripts/verify_all_claims_live.py` formerly incorrectly labelled `/oppslagstavle/<article>` as contradicted purely because URL path omitted. New isolated patch routes dated original publisher items to `unverifiable` pending true independent HTML/date check, instead of false contradicted.

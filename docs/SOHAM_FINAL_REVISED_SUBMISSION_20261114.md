# SIGNALPOST — FINAL REVISED SUBMISSION AND EVIDENCE HANDOFF

Prepared 14 November 2026, before Soham's requested 15 November 09:00 IST reply.

## WHAT TO SUBMIT

- Repo: https://github.com/Sraveena1992/signalpost-company-agent
- Proposed final branch: `final/qualification-evidence-20261114`
- Review PR: https://github.com/Sraveena1992/signalpost-company-agent/pull/52
- **Use the exact latest head SHA shown on PR #52**, not production SHA. CI embeds its exact SHA in FINAL_EVIDENCE_MANIFEST.json.
- Production baseline, unchanged without owner merge approval: `659aa1a374a9ecb103170b9de0207cef3e743ff0`
- Live UX: https://signalpost-company-agent.onrender.com/
- Genuine source-linked company-owned dated article: https://aas.speiding.no/oppslagstavle/utlysning-sommerjobb-som-aktivitetsledere/
- Important: job-related historical summer 2026 recruitment is **NOT currently open**.

## EVIDENCE VERIFIED, NOT CLAIMED

- Exact 100-company fresh smoke: https://github.com/Sraveena1992/signalpost-company-agent/actions/runs/43601907928 (PASS).
- Exact 500-company all-ten-module run: https://github.com/Sraveena1992/signalpost-company-agent/actions/runs/43601907908 (PASS): 500/500 real outputs, 7,673 synthesis claims with source URLs/timestamps; 1 dated company-site article; zero exact verified active jobs.
- 500 source URL comparison: current comprehensive CI produces a per-claim JSON report. **It is automated corroboration, not blinded human adjudication or official >=95% precision.**
- Blind sample generated: 384 source-linked claims from actual 7,673 claims. 384 human reviews still UNREVIEWED; never report a self-certified gold accuracy.
- Job funnel result from archived 500: 12 identity-approved websites, 2 career-link candidates, 0 ATS links captured, 0 structured jobposting candidates, 0 verified active postings. These are bounded archived observations, not proof that vacancies do not exist.
- Full regressions on combined branch: 212 tests + 7 subtests passed as of the last checked SHA; recheck latest head CI before sending.
- Security scanning: PASS on prior combined-branch commits; recheck latest head.
- Live site reviewer evidence: https://github.com/Sraveena1992/signalpost-company-agent/actions/runs/43603847608 (PASS).

## ADJUDICATION QUEUE / KNOWN SOURCE TIME DRIFT

1. `995311321` 1HJELP.NO AS. Company-site description differs between original timestamped crawler value and later HTML metadata. The original source contains its exact org number (company ownership corroborated). Archived description cannot be declared historically false/true from current text alone. Gold label UNKNOWN.
2. `987531630` 1. ÅS SPEIDERGRUPPE. Publisher original article exists and is company-owned. The archived crawler captured `2026-05-14T09:01:21+00:00`, whereas currently visible Norwegian article date is `24 juli 2026`. This discrepancy requires independent timestamp review, NOT automatic agreement. Article is about expired summer recruiting, not an active opening. Gold label for exact published date UNKNOWN.
3. `932850753` 2 NK SOLUTION SP. Z O.O. SP. K. Archive at `2026-11-14T14:03:32Z` asserted bankruptcy false, liquidation false and Polish business address. Later official BRREG JSON omitted those three keys. A missing field **does not contradict** a historical assertion; the fixed verifier marks these as UNVERIFIABLE pending evidence from original source snapshot. Source comparison and hashes: see Forensic official register discrepancy workflow.

## WHY THE OLD BUILDR SCORE WAS 49.26

According to Soham's prior evaluation of a *different old commit*, old scores were Recall 18.66/50; Evidence 26.60/30; Synthesis 0/12; UX 4/8. 6 of 53 inspected claims belonged to wrong companies (88.68% correct). These are NOT the official scores for this revised branch.

The revised branch uses exact-site source gates, refuses site-builder social profiles without independent account ownership, preserves missing source states, and produces a reviewer-facing `synthesis.decision_brief` with ONLY source-linked findings, dated metadata and explicitly unknown categories. No claims of new 65/100, 95% gold score, 12/12 synthesis or 8/8 UX unless the organiser publishes an official re-evaluation.

## REPRODUCIBLE COMMANDS

On a clean clone, `uv sync --frozen --all-groups` then `uv run pytest -q`.

Use existing CLI options for 100/500 research: `uv run python scripts/run_competition_batch.py --organisations <EXACT_ORG_INPUT> --output <OUTPUT_JSONL> --profiles-output <PROFILES_JSONL> --report <REPORT_JSON> --run-id <UNIQUE_RUN_ID> --expected-count 500` (and the appropriate real optional bulk snapshot, all ten default modules, network and permitted sources). **Do not substitute random 500-company inputs.** Download immutable `profiles-500.jsonl` from the linked GitHub Actions run.

Analyze existing saved actual profiles:

```bash
uv run python scripts/diagnose_exact_500_jobs.py --profiles profiles-500.jsonl --output jobs-diagnostic-500.jsonl --report jobs-funnel-summary.json
uv run python scripts/build_blind_gold_review.py --mode sample --profiles profiles-500.jsonl --queue gold-review-384.json --manifest gold-review-manifest.json
uv run python scripts/verify_all_claims_live.py --profiles profiles-500.jsonl --output fresh-source-validation.json --workers 8
```

The final integrated workflow `Final qualification evidence gate` stores these exact reproducible reports under an artifact with source-commit SHA.

## SUBMISSION REQUIREMENTS AND NO FALSE POSITIVES

- Protect exact 100-company membership/terminal state.
- Preserve real news original source and visible publisher date, disclose date mismatch.
- Treat all unknown data as unknown.
- Do not attribute parent/staffing company vacancies to a different legal entity.
- No source-host or company-identity fallback to fuzzy string matching.
- No unapproved Apollo paid API calls.
- **No merge/deploy, no source modifications to production unless owner approves.**
- Submit repository, reviewed branch/commit, latest test and source evidence links to Soham before his earlier reply deadline.

**Outstanding external gates:** independent human gold-label adjudication of the sample and official Builderr scoring/rescore. No engineering agent can self-issue either result.

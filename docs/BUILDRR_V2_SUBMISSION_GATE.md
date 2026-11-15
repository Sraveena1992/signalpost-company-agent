# Builderr Signalpost evaluation contract v2 — evidence and submission gate

Applies to the supplied 26 August 2026 contract. This checklist is a developer
evidence register, NOT Builderr's official score or admission notice.

## Current frozen official submission
- Original submission branch: `main`.
- Submitted commit: `07ad8c3ae1e0b7aa85a5f6e41043a20a0a9df23c`.
- Current additional improvement branch: `fix/news-visible-date-provenance-20261115`.
- **Do not assume this new branch is an admitted revision.** Soham explicitly
  said that the admitted-version ledger is unreconciled and version 5/5 is
  unconfirmed either way. The next step is eligibility confirmation.

## Contract checks and evidence
| Requirement | Existing implementation / check | Remaining qualification gate |
|---|---|---|
| Exactly one terminal envelope per input | `terminal_envelope`, `validate_envelopes`, 100 and 500-company CI | Fresh official Builderr batch of 1,000 or expanded 1,100, under the evaluator time budget |
| Six published states | `TERMINAL_STATES` and internal-to-public mapping in `batch.py` | Verify each Builderr run |
| Registry identity anchor | Brønnøysund official record, organisation-number validation | Official frozen Builderr registry snapshot input |
| Per-material-claim source and timestamp | `answer_profile`, evidence modules and source audit | Independent factual precision by Builderr |
| Reporting period for financial claims | Annual account data carries period/year; explicit claim guards | Check every new official field |
| Zero/null handling | Missing values separate from actual numeric zero | Official false-publication scan |
| Refresh/idempotence | `diff_profile` and tests; false-change on failed source now suppressed and previous source metadata preserved | Fresh official two-run refresh observation |
| Source rights/secrets/outbound | README policy, strict website host gates, GitHub security audit | Provider/official network rules |
| Company news/jobs | Date-verified owned article and exact-employer structured job gate | Live ATS discovery and verified active postings not demonstrated for official batch |
| AI source-corroboration | Frozen 384 review (382 source matched, 2 unknown) | NOT Builderr's human/official 95% accuracy |
| Performance/cost | Report contains requests/bytes/p50/p95 and third-party paid cost | Re-measure within 1,000+ company Builderr time/resource budget |
| UX | Public directory, research UI, on-demand company profile, evidence | 100-profile public sample on /signalpost and official 8-point UX score not proven |
| 50/30/12/8 | Internal tests and source-linked synthesis | Official scorer alone can determine score and ≥65 qualification |

## Exact evaluator-owned input (do not replace)
```bash
uv sync --frozen
uv run python scripts/run_competition_batch.py \
  --organisations /path/to/builderr-official-1000-orgs.jsonl \
  --bulk /path/to/builderr-frozen-registry-snapshot.csv \
  --output out/official-terminal.jsonl \
  --profiles-output out/official-profiles.jsonl \
  --report out/official-run-report.json \
  --run-id signalpost-official-v2 \
  --expected-count 1000
```
Use actual Builderr supplied paths and expected count (for example 1100 if the
shared batch expands). `--bulk` is optional when none is supplied; don't invent
a snapshot. These are command shape examples, not claims that the private
evaluator dataset has been run.

## Latest specific improvements
1. News original publisher byline and differing metadata both preserved;
   disputed archive May vs visible July dating is flagged.
2. Source-recheck does not count the stale metadata as a verified publication date.
3. Refresh does not treat a temporary unavailable source as financial data
   deletion or a material company change.
4. Material refresh changes preserve previous source URL, retrieval timestamp,
   status, period and source digest as evidence.

## Non-negotiable claims boundary
- No official 50/30/12/8 or 65+/100 claim until Builderr confirms it.
- 382/384 is an *observed automated source-corroboration* result, not an
  independently certified factual precision.
- 0 verified active jobs remains 0 until original company and current vacancy
  are proved; don't insert other legal entities, stale vacancies or ATS leads.
- No additional official version submission without confirming that a version
  slot exists.

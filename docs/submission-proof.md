# Buildathon Submission Proof

Use this document when recording the five-minute Razorpay Buildathon video or completing the written submission.

## Five-minute demo outline

**0:00–0:35 — Problem.** Finance teams compare gateway settlements, bank statements, and internal ledgers by hand. Differences caused by fees, settlement delays, duplicate IDs, and missing exports make a simple match percentage misleading.

**0:35–1:10 — The loop Reconcio closes.** Show the three input sources and explain that Reconcio validates them, reconciles every record group, persists the evidence, and routes only defensible exceptions to a reviewer. This is the verification loop that makes downstream cash reporting trustworthy.

**1:10–2:00 — Matching decisions.** Open **Matched Records**, filter to Tier 1 and Tier 2, and point out exact-ID matching, amount/date tolerances, and RapidFuzz reference similarity. Emphasize that Tier 2 displays its rule trace and confidence.

**2:00–2:50 — Honest exceptions.** Show the exception chart and table. Explain that a missing bank record, duplicate ID, or out-of-tolerance amount becomes an exception instead of being forced into a match. Point to **Unreconciled cash exposure** as the value that still requires review.

**2:50–3:35 — AI judgment and safety.** State that the deterministic matcher makes every match decision first. AI is read-only: it provides schema-validated explanations when configured, or transparent rule-based explanations when no API key is available. It cannot modify records, matches, or money movement.

**3:35–4:20 — Auditability and scale.** Show **Run History / Audit Trail**, then cite the README’s persisted 193-record and 7,722-record runs. The numbers are end-to-end and reproducible from the documented commands.

**4:20–5:00 — Failure recovery and close.** Say: “At 2 AM, our standalone throughput number did not match the audit log. We found that it excluded loading and persistence. We fixed the timing boundary and report only audit-backed end-to-end throughput. Reconcio’s principle is simple: if the evidence is not defensible, create an exception rather than pretend it matched.”

## Reviewer checklist

- Seeded batch has more than 50 source records and intentionally contains exact, fuzzy, duplicate, missing, rounding, and unresolved cases.
- Dashboard exposes match rate, tier breakdown, throughput, unreconciled cash exposure, explanations, and append-only audit evidence.
- The repository documents the reproducible stress test and contains automated tests.
- The demo avoids claiming that the optional AI layer makes financial decisions.

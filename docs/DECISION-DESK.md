# Sway Decision Desk

The Decision Desk performs actual model inference on case content. Its decisions are not computed from assumed timings or random probabilities. The original planning simulator remains a separate screen.

## Execution flow

1. Define a workflow objective, a policy (one rule per line), allowed teams, and review requirements. You can author these yourself or ask Groq for an editable draft.
2. Paste a real case and optionally attach text documents. TXT, Markdown, JSON, and CSV are supported. PDFs/images are not parsed in this version. Limits: four documents, 16,000 combined characters.
3. Save the input and policy snapshot in SQLite. The server sends the actual case and document text to Groq.
4. The LLM chooses an action, team, and priority, cites exact source passages and policy IDs, explains its conclusion, and identifies missing information or uncertainty.
5. Python validates the response schema, team allowlist, policy IDs, exact quotes, required request fields, and resolution gaps. Source matching does not prove semantic correctness.
6. Failed checks block execution. Configured approval requirements, model-reported uncertainty, and escalation enter the human review queue.
7. Authorized decisions execute in one SQLite transaction. The action result and audit event are committed together. Repeating a run or approval cannot execute the action twice.

## What actions actually do

| Action | Actual local effect |
|---|---|
| route | Assign a team and priority and set the case to `routed`. |
| request_info | Set `awaiting_information`, assign a team, and store the request draft. |
| resolve | Set the case to `resolved`. By default this requires human approval, configurable per workflow. |
| escalate | Enter review; an approved escalation records the team and `escalated` status. |

No external messages, payments, refunds, or third-party changes are performed. Responses remain drafts. These are real local state changes, not simulated actions. The model cannot run Python, shell commands, URLs, or arbitrary tools.

## Manual walkthrough

Open http://127.0.0.1:5173. The Decision Desk is the default screen.

1. Choose **Service outage** and **Analyze case**. Inspect its actual selected action, priority, and destination. With the default policy, expect routing to Technical Support at high priority. The local state should change to routed when checks pass.
2. Open **Inspect the source** and compare every quote with the case/documents. Inspect the Python check results and audit events.
3. Click **Verify integrity**, then **Export record**. The export includes the source text, original policy, decision, measured provider latency/tokens, checks, local state, and audit chain.
4. Start a **New case**, choose **Missing information**, and run. Expect a specific information request. Expand the response draft; it is stored, not sent.
5. Run **Ready to close**. With the default policy it should wait for human approval. Enter a review note and choose **Approve & execute**, or **Reject action**. Verify that actual case status changes only on approval.
6. Run **Conflicting evidence**. Inspect whether the model identifies the conflicting records and escalates for review.
7. Run **Instruction attack**. The malicious instructions are part of the case evidence and should not override policy. Inspect the action and team rather than trusting the prose. This single example is a smoke test, not proof of prompt-injection immunity.
8. Open **Setup** and describe a new operational use case. Draft, review, edit, and save its policy. Submit a case relevant to that new policy. This proves decisions are conditioned on supplied content and policy rather than prewritten sample outcomes.
9. Turn off automatic execution and save. A new case should wait for approval even if all validation checks pass.
10. Reopen a case from the local library. Its original policy remains fixed even if the workspace policy has since changed.

Cases that need more information can be copied into a new case and supplemented with the reply. This version does not have inbound email or automatic follow-up ingestion.

## Evidence and trust

The model is fallible. Mechanical validation establishes allowed action shape and citation provenance; it does not independently establish whether every interpretation is correct. Human review is configurable, with mandatory review for model-reported uncertainty and escalation. High-impact eligibility/payout/medical/employment outcomes are directed to qualified review by the model instructions; the executor itself supports only local routing, requests, escalation, and closure.

Audit records are hash-linked and the source snapshot is hashed. The integrity check detects ordinary changes to those records. It is not a signed, externally anchored, tamper-proof ledger, and it does not certify correctness.

The app is a single-operator localhost workspace. Review entries identify `local_operator`, not an authenticated person's identity. Production use with multiple users needs authentication, authorization, measured evaluation on representative cases, hardened review rules, and integration-specific action controls.

## Failure behavior

- Invalid model output or unavailable provider: persist a failed case, execute nothing, allow a deliberate retry.
- Unknown team, fabricated quote, unknown policy ID, incomplete request, or unresolved resolution gaps: block execution. Human approval cannot bypass failed validation.
- Same case submitted twice: return conflict; only the first run can proceed.
- Interrupted server: in-progress cases become failed on restart and can be retried; no fabricated completion.
- Changing workflow: affects new cases only; existing case policy snapshots remain fixed.

## Tests

Run `.venv/Scripts/python.exe -m pytest -q` for deterministic engine and decision-executor tests. With the default support workflow and server running, `.venv/Scripts/python.exe backend/scripts/live_decision_check.py` runs a small set of actual Groq smoke cases. It consumes real model requests and saves local cases. It is not a decision-accuracy benchmark.

## Implementation

- `backend/app/decisions.py`: input/output contracts, model prompt, policy references, evidence checks, action allowlist.
- `backend/app/decision_store.py`: saved cases, transaction boundaries, review, audit, recovery.
- `backend/app/main.py`: API and existing provider request quota.
- `frontend/src/components/DecisionDesk.tsx`: policy editor, case input, evidence, validation, execution state, review, history.

SQLite storage and the server-side Groq credential remain in use. No Supabase migration or external deployment is part of this change.

# Progress

## Requirements and decisions
- Original brief preserved in `docs/original-brief.md`.
- User override: private chats default to both participants' messages, requesting
  revocation for everyone; `--private-mode own` restores outgoing-only targeting.
- Groups/channels/bots remain sender-attributed. Saved Messages includes saved forwards.
- All deletion calls use `revoke=True`; no local-only fallback or live development deletions.
- Migrated groups retain distinct historical peer namespaces to avoid losing old history.
- New messages found after confirmation require another confirmation.

## Completed implementation
- Python 3.11+ package, module and console entry points, environment configuration,
  missing-credential prompts, optional credential saving, Telethon login lifecycle.
- Classification and scopes; explicit main/archive discovery and peer deduplication.
- Sequential sender-filtered scanning, conservative fallback, ID-only inventory.
- Atomic JSON checkpoints, account-bound resume, per-batch persistence and interruption handling.
- Rich tables, export/dry run, exact typed confirmation, private-mode visibility.
- Per-dialog 1–100 ID revocation batches, flood waits, bounded transient retries,
  bad-ID splitting, permission isolation and authentication-error termination.
- Three-pass verification limit, newly discovered-ID confirmation barrier, explicit
  partial reports, distinct accepted-request and externally-absent counts.
- README, environment example, secret exclusions and disposable-account test procedure.
- GitHub Actions matrix for Windows/Linux and Python 3.11/3.12/3.13.

## Local evidence (2026-09-18)
- Editable installation succeeds with Telethon 1.45.0 on Python 3.12.6 / Windows.
- 41 mocked tests pass. Covers classifications, scope, private both/own policy,
  Saved Messages, batch boundaries, atomic write interruption, account mismatch,
  deletion interruption, flood waits, bounded transient retry, fallback safety,
  permission errors, authentication errors, invalid-ID isolation, verification caps,
  newly discovered messages, zero-deletion CLI dry run and exact confirmation.
- Ruff lint and formatting pass; module compiles; CLI help works; pip check passes.
- Wheel build succeeds. GitHub Actions run 35326519082 passed all six Windows/Linux
  and Python 3.11/3.12/3.13 combinations for cf1ecbd.
- Final source audit fixed discovery of unexpected entities lacking stable peer IDs;
  a regression test confirms they are reported and skipped instead of aborting.
- Milestones pushed: scaffold `796726f`; implementation `cfd792c`.

## Acceptance audit / remaining
- Automated checks establish the local workflow, mock request semantics, and recovery
  behavior. They do not establish live Telegram behavior or another user's view.
- Required manual acceptance remains: actual code/2FA login, known-message inventory
  against Telegram, group/channel permissions, archived history, and disappearance
  in both private participants' official clients. Follow `docs/manual-validation.md`.
- No API credentials or authenticated disposable test session were supplied. Do not
  use a real account's history as a development fixture or claim manual checks passed.
- Requirement-by-requirement audit is recorded in `docs/acceptance.md`.
- Await remote checks for the final discovery fix and operator manual-test results.

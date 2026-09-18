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
- Final implementation run 35326684111 for a596b96 also passed all six combinations,
  including all 41 tests and lint/format checks.
- Final source audit fixed discovery of unexpected entities lacking stable peer IDs;
  a regression test confirms they are reported and skipped instead of aborting.
- Milestones pushed: scaffold `796726f`; implementation `cfd792c`.

## Acceptance audit / remaining
- Automated checks establish the local workflow, mock request semantics, and recovery
  behavior. They do not establish live Telegram behavior or another user's view.
- Live login and all-scope archived-inclusive inventory have now been exercised.
  Remaining manual acceptance is deletion of designated disposable messages,
  permission behavior and disappearance in both participants' official clients.
  Follow `docs/manual-validation.md`; ordinary account history is not a test fixture.
- Requirement-by-requirement audit is recorded in `docs/acceptance.md`.
- User later supplied credentials and asked for tests to run here. Authentication
  was completed locally; live dry-run results are recorded below. No live deletion
  acceptance is claimed.

## Live-test follow-up
- User supplied credentials locally and requested that tests be run here.
- Automated suite: 41 passed before attempting live authentication.
- Read-only live run exposed `PhoneMigrateError`: setting Telethon request retries
  to zero switched data centers without reissuing the authentication request.
- Enabled two bounded internal retries and added a regression test exercising
  Telethon's real request loop with a simulated data-center migration.
- Updated automated suite: 42 tests pass; Ruff checks pass.
- Retried live login successfully reached Telegram's code prompt. Opened a local
  authentication-only window so the user can enter code/2FA without sharing secrets.
- No message deletions have been performed. Live inventory awaits local sign-in.

## Live inventory and progress-feedback follow-up
- User completed local sign-in. Live all-scope inventory (including archives)
  finished every discovered dialog with zero discovery/scan errors and no fallback
  scans. Telegram flood waits were observed and respected; no deletions occurred.
- User requested that message contents not be viewed. Inspected only aggregate
  counts, targeting/scan metadata and error status; no message text/media inspected.
- Final inventory rendering hit Windows redirected-output UnicodeEncodeError on a
  non-Latin chat title. The inventory checkpoint is complete and intact.
- User explicitly requested a separate agent for progress UI. Delegated scoping,
  scan/deletion progress, elapsed/rate/ETA feedback and tests, plus the output-encoding fix.
- Latest authentication-fix CI run 35327028667 passed on all six supported combinations.
- Live destructive validation and observation from the other participant's client
  remain unperformed; the account's ordinary history is not a destructive test fixture.
- Completed Rich progress display for discovery/scoping, message scanning, deletion
  and verification: elapsed time, measured rates, known-total ETA, unknown-total
  indicators, visible flood waits, 80-column layout and bounded redirected output.
- Output encoding fix verified against the actual completed inventory in memory
  using a Windows cp1252 output stream. No message contents were inspected and no
  additional Telegram API calls were needed for that check.
- 52 automated tests pass, including progress events without body access, precise
  rate/ETA calculations, empty-dialog transitions, private local-filter labels,
  narrow terminal layout and Unicode output. Ruff lint/format checks pass.
- Remote run 35328176447 passed all six Windows/Linux and Python 3.11/3.12/3.13
  jobs for d2b93b6, including all 52 tests and lint/format checks.
- Revalidated the clean worktree and successful remote run. Requested a designated
  disposable test chat/message set, or an explicit user decision to finish without
  destructive live validation. No further Telegram requests made during this audit.

## Authorized cleanup with preserved chats
- User explicitly authorized account-wide cleanup, excluding two specified chats.
  Their exact peer IDs are kept in local execution state rather than public documentation.
- Implemented repeatable `--exclude-chat` links/IDs with persistent, additive resume
  exclusions; protected dialogs are pruned from targeting before discovery/scanning.
- Migrated legacy histories inherit protection. Deletion requests independently
  reject protected peer IDs, including mismatched input peers.
- 58 tests pass, including protected-chat scan/delete/verification exclusion,
  resume with stale protected inventory rows, link parsing and migrated protection.
- Live deletion will resume the completed inventory with both exclusions in force.
- Live deletion completed with 4,855 accepted IDs. Both protected chats were
  absent from the active target set throughout; excluded IDs persisted in state.
- API-type-only audit of 171 remaining IDs found 143 history-cleared markers and
  28 membership service events; no message text/media inspected.
- Fixed verification to track history-cleared markers separately from failures
  and externally absent IDs. Other service entries remain explicitly reported.
- 60 tests pass with lint/format checks. A read-only verification of the previously
  incomplete dialogs is running with both exclusions enforced.

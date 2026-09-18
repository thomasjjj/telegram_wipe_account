# Acceptance audit

Audited against all sections of `original-brief.md` and the user's private-chat override.
This is a software implementation audit, not a record of live Telegram success.

| Brief sections | Implementation / evidence | Status |
| --- | --- | --- |
| 1–2: objective, accessible scope, limitations | README scope/limits; strict group/channel/bot sender checks; private `both` override; Saved Messages full scan | Implemented; live coverage unverified |
| 3–4: Python, dependencies, modules, entry points | pyproject.toml; all specified package modules; module/console help; successful editable install and wheel build | Passed locally |
| 5: credentials/login/security | config.py; telegram.py; CLI start/disconnect; .gitignore; config prompt and environment tests | Mocked/local checks pass; real code/2FA login pending |
| 6–7: startup, classification, archives, scopes | cli.py, dialogs.py; classification, scope exclusion, archive dedup and unknown-entity tests | Automated checks pass |
| 8: sender filtering/fallback/sequential scans | scanner.py; sender validation, fallback, continuation offset and transient retry tests | Automated checks pass |
| 9: inventory before typed deletion confirmation | workflow tests for dry run, invalid confirmation and confirmed deletion | Automated checks pass |
| 10: atomic state/resume/account binding | state.py; atomic replacement failure, account mismatch, interruption and completed-batch resume tests | Automated checks pass |
| 11: peer batches/revocation/checkpoint/verification | deleter.py; boundary sizes, revoke=True, persisted accepted IDs, three-pass cap, new-ID confirmation tests | Automated checks pass; server/other-client behavior pending |
| 12: flood/auth/permission/transient/bad-ID errors | telegram.py/scanner.py/deleter.py; mocked error and interruption tests | Automated checks pass |
| 13–15: optimization/models/module ownership | Sequential APIs, cached input peers, ID-only checkpoints, separate config/discovery/scan/delete/state/UI modules | Source audited |
| 16–18: workflow/flags/dry run | CLI help and end-to-end fake-client tests; export is the saved JSON checkpoint | Automated checks pass |
| 19: transparent final report | Found/pending/failed counts, accepted requests, externally absent IDs, scanned/skipped/verified dialogs, concise errors, no trace-free claim | Source and workflow tests audited |
| 20: special cases | README explains Saved forwards, bot replies, private override, anonymous posts, migrated-history namespaces | Automated targeting checks pass; migrated live history pending |
| 21: safety invariants | No deletion path in dry run; typed gate; no revoke=False or history-delete shortcut; safe checkpoint recovery | Automated checks pass; private incoming-message exclusion intentionally superseded |
| 22: required unit tests | tests/test_core.py, test_workflow.py, test_recovery.py | 41 tests pass locally |
| 23: manual test plan | manual-validation.md | **Pending disposable account and operator results** |
| 24: operational README | README.md includes setup, credentials, examples, scopes, resume, rates, privacy and limits | Implemented |
| 25–26: style/order/checks | Typed small modules, async sleeps, dataclasses/pathlib, logging metadata, Ruff checks; mocked dry run demonstrated without live deletion | Local checks pass |
| 27: acceptance criteria | Tests establish application behavior; real auth, actual attribution/permissions and both clients' resulting histories require section 23 | **Not fully verified** |
| 28–29: Telethon 1.x and conservative operation | Telethon 1.45.0 installed; official client/error references reviewed; no concurrent scans/deletes or heuristic authorship | Implemented |
| User: commit regularly, progress.md | Scaffold, implementation and hardening milestones pushed to origin/master; progress.md records outcomes and remaining checks | Ongoing |

Private-chat change: received messages are intentionally included only for human
private peers in `both` mode. This supersedes the original brief's private-chat
own-only safety/acceptance clauses. Bot replies and other people's group/channel
messages remain excluded. The tool clears inventory contents using revoke batches;
it does not promise removal of the empty chat-list entry or server metadata.

Remote CI run 35326684111 passed all six Windows/Linux × Python 3.11/3.12/3.13 jobs
for final implementation commit a596b96, including all 41 tests and lint/format checks.
Follow-up: user supplied credentials locally and completed interactive sign-in.
Live inventory covered all discovered dialogs without scan/discovery errors or
fallbacks and respected observed flood waits. A final-table Windows encoding error
was fixed and rendering verified against that saved inventory without viewing
message contents. No live deletion occurred; both-client deletion validation
was subsequently authorized across the account with two protected chats excluded.
The live run recorded 4,855 accepted deletion IDs; read-only verification confirmed
794 dialogs clean and identified 28 retained membership service entries. History-
cleared markers are tracked separately. Both protected peers remained outside the
active job. No message contents were inspected. The final functional CI run
35329839048 passed all six environments with 60 tests. Another participant's
official-client view has not been independently observed; do not claim it was.

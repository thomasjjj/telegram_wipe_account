# Telegram Account Cleaner

A Python 3.11+ CLI that inventories accessible Telegram messages, then deletes them
with Telethon 1.x after typed confirmation. **Deletion is permanent.** Start with a
dry run and inspect the saved inventory.

Private chats default to clearing **both participants' messages**, requesting deletion
for both users. Groups, supergroups, channels and bots target only messages attributed
to the signed-in account. Every deletion uses `revoke=True`; the tool never silently
falls back to deleting only your local copy.

## Install

```powershell
git clone https://github.com/thomasjjj/telegram_wipe_account.git
cd telegram_wipe_account
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

On macOS/Linux activate with `source .venv/bin/activate` and copy the example with
`cp .env.example .env`. If your environment has no pip, run `python -m ensurepip`.

Obtain your own API ID and hash from [my.telegram.org](https://my.telegram.org), under
API development tools. Configure `.env` in the current working directory:

```dotenv
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=
TELEGRAM_SESSION=telegram_cleaner
```

Missing API credentials are prompted for. Saving them is optional and defaults to No.
Environment variables override `.env`. The optional phone number can be entered at
login. Telethon prompts for the login code and, when enabled, your 2FA password.
Neither is saved to `.env`. Subsequent runs use the local session file. Run from the
same directory (or configure an absolute session path) to reuse it.

## Inventory and cleanup

```powershell
telegram-cleaner --dry-run --scope all --include-archived
telegram-cleaner --scope all --include-archived
telegram-cleaner --scope groups-channels
python -m telegram_cleaner --help
```

Without flags, an interactive menu defaults to inventory only. Archived dialogs
are included by default when prompted. Inventory shows peer IDs, titles, categories,
counts, scan failures, private-chat policy and Saved Messages coverage. It saves IDs,
not message bodies or media, in `state/cleanup_*.json`.

| Scope | Targets |
| --- | --- |
| `groups-channels` | Your attributed messages in basic groups, supergroups (including forum topics), broadcast channels |
| `all` | Above, plus your messages to bots, both sides of private chats, and all Saved Messages |

`--private-mode own` restricts private chats to your messages. The default is
`--private-mode both`, which includes messages received from the other person.
Bot replies remain untouched. Saved Messages includes forwarded/saved messages
regardless of original author. Group/channel posts sent anonymously or as a channel
are never inferred to belong to you from admin privileges or the outgoing flag.

After inventory, choose `delete`, `export`, or `abort` (the default). Deletion also
requires the exact phrase `DELETE <pending-count>`. There is no `--yes` shortcut.
The JSON checkpoint is the inventory export; export and dry run send no deletion
requests. Partial inventories show errors; only fully scanned dialogs can proceed.

Messages are deleted in batches of at most 100, tied to a single peer. For private
chats this clears the inventoried conversation contents rather than merely your
outgoing messages. It does not call a whole-history deletion method, leave groups,
or explicitly remove chat-list entries. Whether an empty chat remains listed is
controlled by Telegram. Messages arriving after the inventory may require another
confirmed pass.

## Resume and verification

```powershell
telegram-cleaner --resume state/cleanup_TIMESTAMP_ID.json
telegram-cleaner --resume state/cleanup_TIMESTAMP_ID.json --dry-run
```

Incomplete jobs for the authenticated account are offered on startup. An explicit
resume path must match that account. Scope, archive and private-mode settings are
retained; conflicting overrides are rejected. Use a new job to change those settings.
Do not edit checkpoint IDs or share checkpoints between accounts.

Checkpoints are atomically replaced after every accepted deletion batch and during
scanning. Ctrl+C preserves available progress. A crash between a successful request
and its checkpoint may replay that batch; deletion is idempotent. Finished batches
are otherwise skipped. Failed IDs remain retryable. Restarted partial scans may
repeat read requests and deduplicate IDs.

Verification scans for remaining matches, with at most three deletion/verification
passes. New IDs discovered after confirmation are recorded but require a fresh
confirmation before deletion. A resumed run rechecks previously verified dialogs.
`--no-verify` skips these checks; it cannot produce a verified-complete checkpoint.
The report distinguishes accepted deletion requests from verified absence and
incomplete/inaccessible dialogs. Verification sees the signed-in account's view;
it cannot independently prove what every other participant sees.

## Rate limits and options

Scanning and deletion are sequential. Telegram flood waits pause for the requested
duration plus 1–3 seconds, then retry. Transient requests have bounded retries;
invalid batches split to isolate bad IDs. Permission failures skip that dialog,
authentication failures stop the run, and unexpected failures preserve the checkpoint.
No parallel workers, account rotation or flood-wait bypasses are used.

Additional options: `--no-archived`, `--batch-size 1..100`, `--verbose`, and
`--state-dir PATH`. Run `telegram-cleaner --help` for all flags. Flags configure the
workflow, but destructive runs still require interactive confirmation.

Exit codes: 0 for a successful inventory, completed request pass, or deliberate abort;
2 for partial inventory/cleanup; 1 for fatal errors; 130 for interruption. A successful
request pass with `--no-verify` remains explicitly unverified in the checkpoint.

## Privacy and limits

The tool cannot promise a trace-free account. It cannot reliably discover inaccessible
or previously removed dialogs, attribute anonymous-admin/channel-authored posts,
remove other people's forwards, screenshots, exports, notifications or external
archives, or control Telegram's retained metadata. Scheduled messages and drafts
are outside posted history. Special/service messages and permissions may prevent
deletion. An accepted revocation request is not proof of erasure from all parties.

Archive and main folders are enumerated explicitly and deduplicated by stable peer
ID. Migrated legacy groups are retained as separate histories because they can hold
unique older messages; distinct peer namespaces are never merged by title.

API secrets, login codes, 2FA passwords, auth keys and message bodies are not logged.
Logs contain generated operational metadata and error class names only; `--verbose`
never enables Telethon protocol debug logging. Inventory files contain sensitive
chat titles, IDs and relationships. Session files grant account access: protect them
like passwords. `.env`, sessions, logs and state files are Git-ignored. Use OS account
permissions or disk encryption, especially on shared machines. Run one cleaner
process per Telegram session/job at a time.

## Development and validation

```powershell
python -m pip install -e '.[dev]'
python -m pytest -q
python -m ruff check src tests
python -m ruff format --check src tests
```

Tests use fake Telegram clients and never perform live deletions. They cover scope,
private two-sided targeting, dry-run safety, exact confirmation, state replacement,
account mismatch, interruptions, retry/flood behavior and failure reporting.
See [manual validation](docs/manual-validation.md) for disposable-account checks.
Live login, Telegram permission behavior and the other participant's view must be
validated with that procedure; automated tests do not establish those outcomes.

The original supplied brief is preserved in [docs/original-brief.md](docs/original-brief.md).
Its own-messages-only private-chat requirements are superseded by the requested
both-participants default described above. Development status is in [progress.md](progress.md).

API references: [Telethon client methods](https://docs.telethon.dev/en/stable/modules/client.html),
[RPC error handling](https://docs.telethon.dev/en/stable/concepts/errors.html).

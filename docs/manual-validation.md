# Disposable-account validation

Status: not executed against live Telegram during development. Use a disposable
account and test conversations whose participants agree to deletion.

1. Obtain API credentials, install the package, and start without `.env`. Verify
   prompts, invalid-ID handling, default refusal to save, login code and 2FA.
   Then configure `.env` and check credentials are no longer prompted for.
2. Create Saved Messages (including a forwarded message), a private conversation
   with messages from both users, a bot conversation with replies, a basic group,
   supergroup/forum topic, and a channel where the test account can post. Include
   another person's group messages and channel-authored posts. Archive one chat.
3. Run `telegram-cleaner --dry-run --scope all --include-archived`. Check every
   known message ID/count in the JSON and both official clients. Nothing changes.
   Private incoming messages and Saved forwards must be included; group messages
   by others, bot replies and channel-authored messages must be excluded.
4. Run a groups/channels dry run; private, bot and self chats must not be scanned.
   Repeat with `--no-archived` and with `--private-mode own` in fresh jobs.
5. Resume the intended inventory without `--dry-run`. Check `y` and a wrong count
   cannot authorize deletion. Resume again and type the exact displayed phrase.
6. Inspect both official clients: inventoried private messages should disappear
   for both users where permitted. Group messages by others and bot replies must
   remain. Membership must remain unchanged. Inspect archived history too.
   Empty private chat-list entries are not explicitly removed by this tool.
7. Interrupt between batches and resume. Inspect checkpoint validity and confirm
   completed batches are not reissued. Reject a checkpoint from another account.
8. Introduce a newly sent message after confirmation. Verification should record
   it as requiring another confirmation; a second run should remove it only after
   that confirmation. Check permission failures remain visible and resumable.
9. Inspect logs and Git status for secrets, message text, sessions and inventory.
   Do not publish the test inventory or credentials. Record actual Telegram API
   restrictions and test date in progress.md.

Flood waits and interruption/error edge cases are primarily exercised with mocks;
do not deliberately overload Telegram to provoke throttling.

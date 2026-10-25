# OverWatch roadmap

## Done

- [x] Oct 24 2026: upstream redelivery fix deployed (run_bot skips finished bots, broker visibility_timeout 6h). Came in with Adam's version bump.

## In progress

- [ ] Zombie run_bot tasks (branch `fix/zombie-run-bot-tasks`): a run whose bot ended elsewhere shuts itself down, leftover GLib callbacks remove themselves, hard 5h task limit, and a "bot not launched by its join time" instance health alert.

## Next steps

- Turn on instance health alerts in production: set `SAVE_INSTANCE_HEALTH_SNAPSHOTS=true` and `SLACK_WEBHOOK_URL_FOR_INSTANCE_HEALTH_ALERTS` on "OverWatch Scheduler". Until then no OverWatch alert reaches Slack.
- Fix recording uploads: on Oct 22 the S3 upload for bot 29 failed with `SignatureDoesNotMatch`, so its video was lost. Check the S3 credentials on "OverWatch Worker".
- Check whether `clean_up_bots_with_heartbeat_timeout_or_that_never_launched` runs in production. A bot sat in "joining" for two days without being cleaned up.

## Known issues

- Bots left in the Meet lobby time out after 10 minutes if nobody admits them (Oct 25: CUGINI, patterned Threads).

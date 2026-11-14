# OverWatch roadmap

## Done

- [x] Oct 24 2026: upstream redelivery fix deployed (run_bot skips finished bots, broker visibility_timeout 6h). Came in with Adam's version bump.
- [x] Nov 4 2026: Meet join failures fix merged and deployed (captions variant, `/meet/<code>` links, Xvfb leak).
- [x] Nov 12 2026: Worker restarted by hand at 11:17 UTC. From Nov 8 to Nov 12 every bot failed in seconds (`SessionNotCreatedException`, `[Errno 11]`): the container ran out of process room after 8 days up.

## In progress

- [x] Nov 12 2026: process census logging merged and deployed. Nov 14 it named the leak: dead Chrome processes (309 zombies after bot 208) held by celery, which runs as PID 1 because the Railway start command skips tini.
- [ ] Zombie reaping + blocked-bot ending (branch `fix/zombie-reaping-and-blocked-bot`): each run_bot adopts and reaps the Chrome processes it orphans, and a bot Google blocks repeatedly ends as a fatal error instead of staying "joining" (the pod restart path only works under Kubernetes). Not merged; merging deploys.

- [ ] Zombie run_bot tasks (branch `fix/zombie-run-bot-tasks`): a run whose bot ended elsewhere shuts itself down, leftover GLib callbacks remove themselves, hard 5h task limit, and a "bot not launched by its join time" instance health alert.

## Next steps

- Set `ENABLE_WAITING_ROOM_STATE_FOR_WEB_BOTS=true` on "OverWatch Worker" so a bot knocking in the Meet lobby reports `waiting_room` to the Admin app instead of `joining`. Then the Admin app can tell the rep to let it in.
- Google Meet refuses our anonymous bots ("You can't join this video call") since about Nov 12 2026: bots 206, 207, 208 on three different meetings. Upstream's answer is a signed-in bot on a dedicated paid Google Workspace account (docs/signed_in_bots.md). Decision pending.
- Sync upstream: the fork is 118 commits behind attendee-labs/attendee (Nov 4 2026).

- Turn on instance health alerts in production: set `SAVE_INSTANCE_HEALTH_SNAPSHOTS=true` and `SLACK_WEBHOOK_URL_FOR_INSTANCE_HEALTH_ALERTS` on "OverWatch Scheduler". Until then no OverWatch alert reaches Slack.
- Fix recording uploads: on Oct 22 the S3 upload for bot 29 failed with `SignatureDoesNotMatch`, so its video was lost. Check the S3 credentials on "OverWatch Worker".
- Check whether `clean_up_bots_with_heartbeat_timeout_or_that_never_launched` runs in production. A bot sat in "joining" for two days without being cleaned up.

## Known issues

- Until the zombie reaping branch is deployed, the worker still climbs toward its 1000 pid limit (571 on Nov 14) and needs a restart roughly weekly.
- Bots left in the Meet lobby time out after 10 minutes if nobody admits them (Oct 25: CUGINI, patterned Threads).

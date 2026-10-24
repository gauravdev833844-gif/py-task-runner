> Deployment note: This is a development/testing prototype. Read CAPACITY_AND_LIMITS.md and OPEN_SOURCE_RESEARCH.md before deployment. The audit does not recommend GitHub-hosted Actions as an ongoing multi-stream recording/archival service. Use an owned runtime for sustained capture; existing account/provider terms and quotas still apply.

# Start once; continue in overlapping overnight windows

The production candidate uses one YouTube channel per repository. Start a session manually whenever monitoring should begin. Later shifts start automatically relative to that manual start; there is no fixed midnight cron schedule to remember.

## What has actually been verified

On GitHub-hosted runners, a cookie-enabled web_safari test saved a 20-second, 1280x720 Sky News live clip with audio. The actual recorder.py engine also saved a roughly 54-second live clip with web_safari. Both downloaded artifacts passed ffprobe and a three-second FFmpeg decode locally. The repository's existing YT_COOKIES binding was used by those GitHub jobs; no cookie value was printed or committed. Full client-matrix and compressed overlap test results are documented separately in VALIDATION.md.

Nine local tests cover scheduling, input limits, continuation fields, deadline expiry and dispatch construction. Simulated regressions cover bot-check classification and carrying the successful detector client into downloading. Generated local media checks cover recovery and finalization. These tests do not establish that every YouTuber or future run will work.

## Files for each repository

Copy recorder.py, shift_plan.py and chain_shift.py to the repository root, and .github/workflows/record.yml to its workflow directory. Copy the matching channels.json from channel-configs. The optional probe_live.py, test_shifts.py and test-live.yml provide live and local regression checks.

Existing channel mappings:

- py-task-newrepo: @HarshxTashu
- py-task-repo4: @bekalki
- py-task-reposit: @baskarfiroz15
- py-task-runner: @BagadBillagang-p6s
- yt-recorder (proposed mapping): @itstarunk4179

Use exactly one channel entry per repository. The yt-recorder configuration intentionally has an empty ID; the recorder resolves identity from the supplied handle rather than inventing an ID.

Each repository needs a usable YT_COOKIES GitHub Actions secret for the verified authentication mode. Never commit cookies or include them in artifacts. The supplied cookies and other credentials are excluded from this bundle. The integration used here cannot create or read repository secrets through the API (HTTP 403); existing bindings are passed privately by Actions. Configure any missing bindings in GitHub Settings -> Secrets and variables -> Actions. Telegram credentials remain optional and only affect notifications. No Telegram messages or Gofile uploads were performed by the test runs.

## Manual start

Actions -> YouTube Live Recorder -> Run workflow. Choose total_hours (default 12, maximum 24). Leave session_start and session_id empty, and shift_index=0; those are internal continuation fields. Use the same branch containing all helper files. Ordinary overnight sessions should be run on main after review.

The workflow starts another five-hour window every three hours while needed. The final window ends at the shared session deadline. For a manual session planned at 20:30 India time, the ideal 12-hour timeline is:

| Window | Approximate recording period |
| --- | --- |
| 1 | 20:30 to 01:30 |
| 2 | 23:30 to 04:30 |
| 3 | 02:30 to 07:30 |
| 4 | 05:30 to 08:30 |

Adjacent full windows overlap by approximately two hours. A stream beginning around midnight is therefore inside multiple monitoring windows. Setup and GitHub queue time can shift actual starts. The continuation job runs separately from recording and can start the next window while the previous one is still saving or uploading. Every continuation keeps the same session ID and deadline. No session continues indefinitely; choose a longer total_hours if needed.

GitHub-hosted scheduling, runner availability, YouTube authentication/rate limits, network failures and account concurrency limits prevent a literal zero-loss guarantee. A current unavailable/bot-blocked stream cannot be made recordable merely by overlapping workers. This design reduces shift handoff gaps; it does not guarantee every frame or every broadcast.

The separate continuation jobs wait on GitHub runners, so they consume runner time. Each five-repository session also has multiple concurrent recorders. The inspected runner repository is public; check your account limits and artifact storage before running overnight. These tests launched only short diagnostic sessions, not a 12-hour production recording.

## Recordings and failures

Recordings, including partial/short-exit .ts fragments, are backed up to a GitHub artifact before external upload, with one-day retention. The Gofile upload step and optional Telegram links are retained. External upload retries have a bounded timeout. Artifact backup itself still depends on the job having time and storage to finish; recordings are not durable until an upload succeeds.

The recorder preserves the default yt-dlp client as a fallback, tries web_safari first, carries forward the successful detection client, keeps bot-check errors distinct from short exits, respects failure cooldowns, and reports a nonzero exit if monitoring saves no final media. An offline channel may legitimately produce no video; that is distinct from a successful recording.

To stop a session, cancel its active/queued recorder and next-shift jobs. Continuations already started are separate runs: find the shared session ID in their run names and cancel those too.

## Reproducible short tests

Run Actions -> Test live recording clients on a currently live public channel such as @SkyNews or @DWNews. It tries four clients with/without cookies serially. A pass requires live status, at least ten seconds of captured video, ffprobe readability and an FFmpeg decode. A metadata-only success is insufficient. Saved results record the exact yt-dlp version and authentication mode. A passing test on Sky News is not proof of access to a different target.

Local scheduling checks: python -m unittest -v test_shifts. No network or real credentials are required for those local tests.

New integrity regression: a complete decode exposed an audio-tail error in the older native-stop sample. The updated SIGINT-first shutdown passed a new 45-second full audio/video decode. See OPEN_SOURCE_RESEARCH.md for exact scope and run links. The probe validator now decodes the complete capture.

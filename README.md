# YouTube recorder — reliability update v2

One repository records one channel. Your intended mapping is **3 accounts × 5 repositories**, five streamers per account. This package does not create accounts, rotate IPs, lift quotas, or guarantee that a hosting provider permits the workload.

This is an improved code package, **not evidence that five repositories have completed an overnight session**. No changes to `main`, no paid services, no Telegram messages, and no overnight production runs were made to prepare this version.

## What changed

- SIGINT-first shutdown gives yt-dlp time to close its current fragment. A disk reserve stops capture gracefully and reports it as incomplete instead of silently filling the disk.
- Source chunks are retained if there is insufficient room to concatenate a second full video. Small/recovered recordings are included in upload discovery and probed for video content instead of being discarded just because they are smaller than 1 MB or named `short_exit`.
- Upload has one shared 30-minute deadline across all files, attempts, checksums and backup operations. Gofile uses its standard upload endpoint, two bounded attempts, and reuses the same guest account/folder during a shift. Optional `GOFILE_TOKEN` lets you supply your own account token.
- Gofile acknowledgement must contain matching byte size and MD5 plus a valid sharing link. This is provider-acknowledged verification; automated download/readback has not been tested.
- **Optional GitHub Release backup** splits adaptively and checks the actual byte size of every part: strictly below 2,000,000,000 bytes, safely under GitHub's 2 GiB ceiling. Fixed 90-minute durations are not treated as a size guarantee. Splitting copies compressed streams; it does not reduce their total size.
- Partial upload receipts are checkpointed. Source files are retained locally after successful or failed uploads. **A GitHub-hosted runner deletes local media when the job is removed**: unuploaded media is not a durable backup.
- Recorder errors cannot become a successful workflow just because upload succeeded. Missing video and failed publication fail the final status. Telegram notifications are optional, report failures, and split long messages into bounded chunks.
- Fixed per-window deadlines stop delayed/duplicate workflows from extending a window indefinitely. Session/index concurrency lets adjacent windows overlap while serializing duplicates.

## Files to put in each repository

Upload these root files and preserve their names:

1. `recorder.py`
2. `shift_plan.py`
3. `chain_shift.py`
4. `publish_recordings.py`
5. `notify_telegram.py`
6. `channels.json`
7. `.github/workflows/record.yml` (the `.github` folder must be at the repository root)

The ZIP also includes tests, this guide, pinned dependencies, a bounded probe and validation evidence. `channel-configs/` contains the five previously supplied channel configurations. Copy the appropriate file to root `channels.json`. For any other channel use:

```json
[{"handle":"@YOUR_CHANNEL","id":""}]
```

If changing a handle, **clear the old `id`** or supply that channel's matching UC ID. Do not leave another YouTuber's ID in place.

## Secrets

Repository → Settings → Secrets and variables → Actions:

- Required: `YT_COOKIES`, the complete Netscape-format cookie-file contents. Keep an existing working binding. The uploaded cookie file and an older working GitHub secret were previously found to differ; success with the old binding does not validate the uploaded file.
- Optional notifications: `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`. Generate a fresh token if the one you pasted elsewhere is active; this package contains no credentials.
- Optional upload account: `GOFILE_TOKEN`. Optionally put `GOFILE_FOLDER_ID` in repository **Variables**. Neither is needed for an anonymous upload; the first successful anonymous response supplies a guest token/folder reused in that shift.

Do not commit cookie files, `.env` files, private provider responses or bot tokens. `.gitignore` protects common filenames but cannot prevent arbitrary renamed secrets.

## Test and schedule

First use a **single repository**, Actions → YouTube Live Recorder → Run workflow:

- `total_hours`: **0.1** for a six-minute bounded detection/capture/upload test. Pick a channel actually live for this test. The named target streamers may be offline.
- `release_backup`: leave false unless you explicitly want failed Gofile uploads copied to GitHub Releases. **Release assets follow repository visibility; public-repo assets are public.**
- Leave `session_start`/`session_id` empty and `shift_index` at zero.

Review actual media, the run Summary, and `upload-report.json`. A running instance or accepted child dispatch is not capture success. A session with no live video reports no confirmed recording instead of a misleading success.

Monitoring starts relative to **your manual run**, with no fixed evening or midnight schedule. Set `total_hours` to **8 or 9**; default and maximum are **9 hours**. The short `0.1`-hour test is still supported. Exactly two windows cover either normal duration:

| Window | Start after manual start | End with 8 hours selected | End with 9 hours selected |
| --- | --- | --- | --- |
| Shift 1 | 0 h | 5 h | 5 h |
| Shift 2 (automatic) | 4 h | 8 h | 9 h |

Both have **one hour of planned overlap**. Shift 2 is dispatched automatically while Shift 1 is still recording. No third shift is scheduled. The controller has a 260-minute ceiling to allow its four-hour wait plus dispatch overhead.

Examples for a 9-hour session (IST):

| Manual start | Automatic Shift 2 start | Monitoring ends next morning |
| --- | --- | --- |
| 19:00 | 23:00 | 04:00 |
| 20:30 | 00:30 | 05:30 |
| 22:00 | 02:00 | 07:00 |
| 00:00 | 04:00 | 09:00 |

For an 8-hour session, monitoring ends one hour earlier. Runner startup/queue delays can shift actual timing; these are planned relative times.

This is **planned coverage**, not guaranteed source continuity. Runner queues, suspension, expiring cookies, YouTube restrictions, network faults and upload failures can cause gaps. Upload occurs after the current recording window; this version is not an upload-while-recording service and is not sized for Northflank's 256 MB / 1 GB free instance.

Each five-channel account normally has 5 recording jobs; during overlap it can have 10, plus controller/preparation jobs. Limits apply to the entire account, not separately to every repository. Duplicate recordings increase traffic/storage.

## Hosting and cost limits

GitHub-hosted Actions is for developing/testing applications and has account/job/storage limits. Do not interpret these scripts as permission to operate a daily multi-account video storage service on GitHub-hosted runners. Review [Actions terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions), [account terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#b-account-terms), and [limits](https://docs.github.com/en/actions/reference/limits). For sustained recording use a runtime you control and a provider that permits the workload; this package does not supply that runtime or free unlimited capacity.

Five recordings of 5 GB need about 25 GB across their runners; fifteen need about 75 GB, before overlap. There is no promise of 30 GB free disk after deleting bundled tools. Actual free disk is printed. Compression is not performed. Gofile sharing has its own account/IP, retention and traffic policies. Release storage is distinct from Actions artifact billing, but [each Release asset must be under 2 GiB](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

Only small JSON diagnostics are saved as Actions artifacts, so this workflow does not quietly duplicate multi-GB video into the artifact allowance. If all upload paths fail, the job fails and local-only recordings can be lost when its runner goes away. No zero-loss guarantee is made.

## Local checks

Requires Python 3.11+, Node 22+, FFmpeg/ffprobe, curl; optional Release backup requires `gh` and repository contents-write permission.

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m unittest -v test_reliability
```

See `VALIDATION.md` for executed checks and untested scope.

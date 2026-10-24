# Verified results — 24 October 2026

Live test source: public @SkyNews. yt-dlp 2026.10.21, Python 3.11, Node 22 on GitHub-hosted Ubuntu.

| Client | Existing GitHub cookie secret | Without cookies |
| --- | --- | --- |
| web_safari | PASS: 20.01-second playable video | YouTube bot verification |
| default | PASS: 20.00-second playable video | YouTube bot verification |
| ios | No matching media format | YouTube bot verification |
| android | No matching media format | YouTube bot verification |

The actual recorder.py, using its native download path rather than just the diagnostic FFmpeg downloader, saved a 54.10-second live clip with web_safari. Its downloaded artifact passed ffprobe and FFmpeg decoding locally.

A compressed integration test used the same production workflow/helper logic with a 30-second next-window interval and 120-second window cap, plus a 151-second shared deadline. The next workflow was dispatched automatically. Both runs succeeded and saved independently playable 109.04-second and 69.03-second recordings. Their logged active windows overlapped by 87.03 seconds. This verifies automatic handoff and overlapping capture on short timing; it is not a completed 12-hour endurance run.

The existing GitHub YT_COOKIES binding does NOT match the uploaded cookie file, verified by an identity comparison that did not display credential values. Successful GitHub captures therefore validate the existing repository binding, not the uploaded file. Local requests with the uploaded cookies were rejected by the cloud proxy before reaching YouTube. The integration has no repository-secret API permission, so no secret was replaced. Keep the working binding intact until another binding is separately verified.

Nine local scheduling/dispatch tests passed, along with simulated bot-check/client-propagation regressions, generated-media recovery/finalization checks, and Python/YAML/shell syntax checks. No Gofile upload, Telegram delivery, private target channel capture, or overnight endurance run is claimed verified.

Run links and sanitized machine-readable results are in validation-results.json. No credentials are included in this bundle.

## Subsequent integrity regression

The earlier native 54-second sample passed only the documented three-second decode check. A later complete-file decode found an audio-tail error. The candidate now tries graceful SIGINT before termination, and a new 45-second live recording passed complete audio/video decoding: https://github.com/gauravdev833844-gif/py-task-runner/actions/runs/40080361118 . Full details are in OPEN_SOURCE_RESEARCH.md. The older native sample should not be described as passing complete-file integrity.

# Current open-source recorder options and bounded tests

Checked 24 October 2026 using public project metadata, current releases, source/README inspection and official provider documentation. A project being free/open source does not supply free unlimited compute or storage. Author nationality was not inferred from account names, and no claim of a private national developer “trick” is made.

| Project | Current evidence | Assessment |
| --- | --- | --- |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Latest release 2026.10.21; active | Keep as the verified engine. Existing-cookie web_safari/default captures passed earlier. |
| [Streamlink](https://github.com/streamlink/streamlink) | Latest release 8.6.2, 7 October 2026; active | A fresh bounded GitHub cookie-enabled Sky News test failed authentication/bot verification. It is not a verified fix for this case. |
| [StreamCap](https://github.com/ihmily/StreamCap) | Chinese-language multi-platform FFmpeg/StreamGet UI; README lists YouTube and says it needs cookies; latest release v1.0.3, source pushed September 2026 | Suitable self-hosted shortlist. Full installation, channel-monitoring behavior and live capture were not validated here. |
| [DouyinLiveRecorder](https://github.com/ihmily/DouyinLiveRecorder) | Chinese-language multi-platform project; lists YouTube; latest release v4.0.7 from October 2025 | A supported-platform claim is not a current live-test result. Reviewed, not installed or credential-tested. |
| [book000/youtube-live-recorder](https://github.com/book000/youtube-live-recorder) | MIT Docker recorder with channel/playlist configuration; release v1.23.96 on 23 October 2026 | Actively updated self-hosting wrapper; not an authentication or free-hosting bypass. Reviewed, not live-tested. |
| [stream-rec](https://github.com/stream-rec/stream-rec) | Repository archived; inspected support table marks YouTube unsupported | Excluded for this YouTube requirement. |
| [ytarchive](https://github.com/Kethsar/ytarchive) | Latest stable release v0.5.0 from 2024; README explicitly requires a PO token | Not selected without its documented prerequisite; no unsupported trial pretending cookies alone are enough. |
| [bgutil PO-token provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) | Third-party provider, release 2.0.2 from October 2026 | Optional for diagnosed client/token requirements. Not an official guarantee of cookie-free access. Not installed for this test because existing-cookie yt-dlp worked. |
| [wangbo5825/YoutubeLiveRecorder](https://github.com/wangbo5825/YoutubeLiveRecorder) | Self-hosted extension/server design; cookie synchronization and MediaMTX; no license detected in inspected metadata | Architecture review only. Do not give a new server/browser extension account cookies without a separate security/license review. No proxy was deployed here. |

## New actual tests

### Streamlink comparison

[Run 40080137052](https://github.com/gauravdev833844-gif/py-task-runner/actions/runs/40080137052): pinned Streamlink 8.6.2, existing repository cookie binding, @SkyNews, a 75-second process bound and 20-second intended output. It exited 1 with authentication/bot verification. Raw cookies and signed media URLs were not published.

### Complete media integrity and shutdown correction

The earlier native-downloader smoke test inspected media and decoded only three seconds. A subsequent full-file decode found an incomplete audio packet near the tail of the older 54-second sample; its video-only decode passed. Do not interpret the earlier three-second check as a full-file integrity test.

The candidate now requests SIGINT first so yt-dlp can close its fragment, with bounded terminate/kill fallbacks for a hung downloader. [Run 40080361118](https://github.com/gauravdev833844-gif/py-task-runner/actions/runs/40080361118) saved a new 45.00-second Sky News live recording. The complete audio and video decoded successfully both in GitHub and after downloading the artifact locally. The public video ID had changed since the earlier Sky News test, demonstrating fresh channel/live resolution. This is a short regression result, not proof that every future stop or source will be perfect.

The diagnostic probe now decodes the entire captured clip instead of only its first three seconds. The earlier 20-second FFmpeg-downloader clip also passed full-file decoding locally.

### Stream-copy segmentation

The clean 20-second captured FFmpeg clip was split into four closed parts without re-encoding. All parts passed complete audio/video decoding; the total video-frame count was exactly 600 before and 600 after segmentation. Codec and resolution were preserved. Total size changed from 3,868,664 bytes to 3,870,732 bytes: splitting did not compress the recording. This was a local segmentation test of captured media, not a new live-network continuity test.

### Compression experiment

A separate 20-second 1280x720 sample encoded at H.264 180 kbps plus AAC 32 kbps occupied 573,994 bytes and passed complete decoding. Linear projection at that sample's average file rate is 516.6 MB over five hours. SSIM against the source was approximately 0.951 for this sample. Re-encoding is lossy; different motion/detail changes quality and encoder load. Fifteen realtime transcodes and a five-hour compressed capture were not run.

### Provider and local checks

See CAPACITY_AND_LIMITS.md: five small generated Gofile uploads passed API size/hash checks at concurrency two; Premium content-listing prevented automated readback. Pixeldrain upload remains unrun without an API key. Nine scheduling/dispatch tests and the simulated bot-check/client-propagation regressions still pass. These are distinct from five-repository or fifteen-stream production validation, which was not performed.

## Free hosting: current official limits

The most direct zero-new-hosting-subscription option is an existing computer/NAS with adequate disk and uplink. A continuous recorder there does not need GitHub shift chaining. Power, network, sleep settings and hardware availability still matter.

[Oracle's current Always Free documentation](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) lists 1,500 A1 OCPU-hours and 9,000 GB-hours per month: for an Always Free tenancy, two OCPUs and 12 GB RAM, plus 200 GB combined boot/block storage. Old guides promising four OCPUs/24 GB should not be assumed current. Home-region capacity can be unavailable and idle instances may be reclaimed. No account, VM or payment resource was created here; availability and real recorder throughput were not validated.

## Decision

Keep the currently tested yt-dlp authentication mode, improve graceful shutdown, and move sustained recording to an owned runtime with segment-based storage and a verified upload queue. A UI wrapper can improve management, but cannot make YouTube bot checks, provider plan requirements, disk capacity or account terms disappear. Do not rotate accounts/IPs to evade restrictions, repeatedly request a Premium-only API, or treat ephemeral free sharing as guaranteed backup.

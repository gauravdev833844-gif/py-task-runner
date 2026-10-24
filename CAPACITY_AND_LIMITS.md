# Recording capacity, storage and hosting audit

Checked 24 October 2026. This report records observed tests and official current documentation, not a promise of indefinite free hosting or zero-loss capture.

## Deployment recommendation

Use GitHub-hosted Actions for bounded development/testing of the recorder. Do not treat a successful short test or the account concurrency number as approval for a continuous multi-stream recording service. GitHub's [Actions terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions) restrict disproportionate server burden and state that Actions may only be used to develop and test applications. Its [account terms](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service#b-account-terms) limit a person/legal entity to one free account, with the stated machine-account exception. IP changes and browser sessions do not change those terms.

An existing PC/NAS is the most practical route with no new hosting subscription. Keep recording continuously there, use a supervised process, write closed segments, and use a bounded upload queue. An owned server removes GitHub's six-hour job boundary and the need to run duplicate overlapping CI workers. Hardware, electricity, bandwidth, service authentication and storage still have limits. No server deployment has been performed by this audit.

## What was checked in the five repositories

| Repository | Existing channel configuration | Read-only observation |
| --- | --- | --- |
| py-task-runner | @BagadBillagang-p6s | Public; existing recording workflow active |
| py-task-repo4 | @bekalki | Public; existing recording workflow active |
| py-task-newrepo | @HarshxTashu | Public; existing recording workflow active |
| py-task-reposit | @baskarfiroz15 | Public; existing recording workflow active |
| yt-recorder | No channels.json on main | Public; existing workflow manually disabled |

The bundle supplies @itstarunk4179 as the proposed yt-recorder mapping. It is not a verified target-channel recording. The disabled workflow was not enabled. No five-repository production stress test or other-account deployment was started. Earlier real recording tests and the subsequent bounded development tests were in py-task-runner. Other repositories' cookie bindings remain unverified.

At inspection the five visible repositories held 44,675,237 bytes of non-expired Actions artifacts (about 44.7 MB decimal). This is an artifact inventory, not access to the account billing dashboard or proof of available paid storage.

## Video size: resolution alone does not determine storage

Using average combined video+audio bitrate and decimal units:

`GB = Mbps × hours × 0.45`

| Average total bitrate | One five-hour video | Five simultaneous channels | Fifteen simultaneous channels |
| --- | ---: | ---: | ---: |
| 1 Mbps | 2.25 GB | 11.25 GB | 33.75 GB |
| 2 Mbps | 4.50 GB | 22.50 GB | 67.50 GB |
| 4 Mbps | 9.00 GB | 45.00 GB | 135.00 GB |

These are unique source hours, without duplicate overlapping recordings. If all channels are continuously live across the prototype's 12-hour session, its four windows record up to 18 channel-hours each: at 2 Mbps, fifteen channels produce about 243 GB instead of the 162 GB for one continuous capture per channel. Actual totals depend on when channels are live and their actual bitrates.

500 MB across five hours allows only about 222 kbps TOTAL, including audio and container overhead. This requires aggressive lossy compression, not merely choosing 720p. In a local 20-second 720p news sample, H.264 180 kbps plus AAC 32 kbps produced 573,994 bytes; a linear five-hour projection is about 516.6 MB. SSIM against that source sample was about 0.951. This single low-motion sample does not predict quality or encoding speed on other broadcasts. Fifteen simultaneous software transcodes were not tested.

Stream-copy segmentation preserves quality and uses much less CPU, but does not shrink total bytes. Ten- to fifteen-minute pieces at 2 Mbps are about 150–225 MB each; they reduce retry size and working-file size, not an account's storage quota.

## GitHub: three different storage concepts

- Runner disk is temporary. Current [standard public runner specifications](https://docs.github.com/en/actions/reference/runners/github-hosted-runners) list 14 GB SSD storage. Check actual available disk with df; dependencies, fragments and finalization copies also consume space. A 5 GB recording plus another 5 GB during concatenation can put pressure on available disk.
- The [GitHub Free artifact allowance](https://docs.github.com/en/actions/reference/limits) is 500 MB. It is an included storage allowance, not a universal 500 MB file-size cap or five hours of video. Account billing/entitlements must be checked before relying on multi-GB artifacts. [Billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions) distinguishes free public standard runner execution from storage usage; free runner execution is not a reason to assume unlimited archival storage.
- Git commits are different from artifacts: [ordinary Git files over 100 MiB are blocked](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github). Do not commit recordings or cookies.

Current documented Free-plan standard runner concurrency is 20 jobs per account, and each hosted job has a six-hour execution limit. Five repositories do not each receive a separate 20-job pool. Other workflows, controller/preparation jobs, slow uploads, queued starts and plan-specific limits affect real concurrency. A nominal 10–15 active jobs is not a ban-safety or no-gap guarantee.

## Two or three windows?

With five-hour windows beginning every three hours:

| Windows | Covered interval from manual start | Example starting 20:30 India time |
| --- | --- | --- |
| Two | About eight hours | Until 04:30 |
| Three | About eleven hours | Until 07:30 |
| Four with a 12-hour shared deadline | About twelve hours | Until 08:30 |

Two windows can miss the end of a five-hour stream beginning at midnight. The user chooses the observation horizon; unknown later starts and longer broadcasts cannot be guaranteed covered by a finite horizon. On an owned always-on runtime, a continuous recorder is preferable to creating overlapping CI shifts.

## Gofile: small uploads passed; bulk capacity not established

Official [API documentation](https://gofile.io/api) and [FAQ](https://gofile.io/faq) describe guest tokens, per-endpoint rate limits and temporary free storage. Do not create a new guest account for every upload: create/use one authorized account and reuse its token and destination folder.

Observed tests from this cloud machine:

- One generated 2,296,420-byte video uploaded with HTTP 200 / status ok; reported size and MD5 matched.
- Five additional generated files, 11,235,068 bytes total, uploaded with two concurrent transfers using the same guest account/folder. All five returned HTTP 200 / status ok and matching reported sizes/MD5 hashes.
- These are small-upload API checks, not five-repository live tests, fifteen concurrent transfers, multi-GB uploads or a load-capacity guarantee.
- Authenticated content listing returned HTTP 401 / error-notPremium, matching the current documented Premium gate. Full automated download/readback was therefore not verified. No workaround of that paid gate was attempted.

The current official free plan advertises 100 GB traffic per 30 days; the FAQ notes that free traffic can be IP-counted and some download functionality can be restricted after the allowance is exceeded. Free files are ephemeral: the FAQ states ten days of inactivity. API rate-limit failures return 429; back off instead of repeatedly retrying across identities or IPs. There is no documented guarantee that fifteen large simultaneous uploads will succeed.

The [rclone Gofile backend](https://rclone.org/gofile/) explicitly requires a Premium account. A free website upload is not evidence that its rclone backend is free.

## Pixeldrain

The official [Pixeldrain API](https://pixeldrain.com/api) states that resource-creating methods need an API key and anonymous uploads are not supported. No usable key was present here; the unauthenticated user endpoint returned 401. Upload was unrun, not proven broken or ready. File-size/storage limits depend on the account plan.

The [rclone Pixeldrain backend](https://rclone.org/pixeldrain/) uses the premium filesystem, requiring Pro or Prepaid, and is different from its free file-sharing product.

## Recommended data path

Record one continuous stream per channel on an owned runtime. Close ten- to fifteen-minute segments without re-encoding, keep a persistent upload manifest, and feed a bounded queue. Retry transient failures with backoff. Preserve the local segment until the configured destination confirms its size/hash; use download/readback where the plan/API permits. Keep an explicit local retention budget and disk-low alarm. During provider outages, retain unsent segments rather than deleting them or claiming backup success.

At 2 Mbps each, fifteen continuous streams create about 30 Mbps of incoming traffic. An upload queue needs roughly that average outgoing rate plus headroom to keep up, otherwise local backlog grows. With no uploads, fifteen five-hour streams need about 67.5 GB before duplicate copies and overhead. A fixed 500 MB budget cannot hold that workload. Free software does not remove physical storage or provider quotas.

Do not auto-delete user recordings merely to make a test pass. This audit did not remove existing artifacts, alter main-branch schedules, enable the disabled workflow, or start overnight production sessions.

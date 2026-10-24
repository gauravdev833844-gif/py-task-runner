# No-card cloud candidate: one-channel deployment pilot

The requirement is remote recording while the user's own device is offline from 17:00 to 10:00 India time. A remote process can continue without that device's connection, but compute, storage, outgoing traffic and YouTube authentication must be verified on the selected host first.

This package is a ONE-OFF, roughly 20-second YouTube capture diagnostic. It is not an overnight recorder, does not run five/fifteen channels, does not upload to Gofile or send Telegram messages, and deletes its temporary capture after validation. Its health server remains available so the result can be inspected. Do not mistake this pilot for a completed overnight deployment.

## Why this candidate

Northflank's current [pricing page](https://northflank.com/pricing) advertises a free Sandbox with "No card needed", two services, two jobs, one database and "Always on, no sleeping". Its [pricing documentation](https://northflank.com/docs/v1/application/billing/pricing-on-northflank#deploy-for-free) describes this as a hobby/testing tier, not a production service guarantee. Current quota documentation lists limits that vary by account/project; the free tier is not proof of enough disk or egress for fifteen recordings.

Use Northflank Cloud's free Sandbox for the pilot only. BYOC requires a separate cloud account and may incur that cloud's costs. Do not select paid resources or add a card to proceed with this candidate. If account verification or a paid gate prevents free use, stop and report that result rather than bypassing it.

## Autonomous deployment prerequisite

A Northflank account/session/token is not present in this Codex environment. No Northflank service has been created and live capture on Northflank is unverified.

1. Create your own [Northflank account](https://app.northflank.com/signup) and select the free Sandbox.
2. Create an expiring, appropriately scoped [API token](https://app.northflank.com/s/account/api/tokens) for the test resources. Permissions come from its RBAC role; use only the project/resource access needed for the pilot, not billing changes. See [the official API access guide](https://northflank.com/docs/v1/application/secure/grant-api-access).
3. Put the token in this Codex environment's secure environment settings under NORTHFLANK_API_TOKEN. A metadata-only requirement is already saved and scoped to api.northflank.com. Never paste the value into chat, source, a screenshot or a command argument. Review/save the environment draft and publish the environment as required by the onboarding settings; that is separate from deploying a Northflank service.
4. Return only a confirmation that the secure binding is set. The next operation is a read-only API check of access, account limits and existing projects before any free pilot resource is created.

No API value is contained in this package. A successful save of the requirement does not itself supply the credential or deploy anything.

## Manual deployment alternative

If deploying directly through Northflank's UI, use a combined build/deployment service from the public repository:

- Repository: gauravdev833844-gif/py-task-runner
- Branch: codex/overlapping-overnight-recorder
- Dockerfile location, relative to repository root: /northflank-pilot/Dockerfile
- Build context: /northflank-pilot
- Build engine: BuildKit
- One instance, using an eligible free resource plan; confirm entitlement and resource usage in the account before launching.
- HTTP port: 8080; health path: /healthz
- Runtime secret: YT_COOKIES, containing a Netscape cookie file. Never use a Docker build argument or commit the cookie file.
- Optional runtime variable: CHANNEL_HANDLE=@SkyNews (or another public channel currently live).

The earlier successful GitHub cookie binding differs from the uploaded cookie file; no secret is automatically copied between providers. Authentication must therefore be tested on the new host. If that cookie file is unavailable/invalid/expired, stop and diagnose it rather than assuming authentication works.

The process runs one bounded probe on startup. The private Northflank logs contain PILOT_RESULT with sanitized JSON. /healthz exposes process state and the pass/fail flag only, not cookies, signed media URLs or downloadable recordings. A final capture_passed=true requires actual live status, at least ten seconds of video, ffprobe readability and a complete FFmpeg audio/video decode. A 200 health response alone does not establish recording success.

If the secret is missing, state is missing_cookie_binding and no recording starts. Add the private runtime secret and redeploy. After a successful pilot, resource/egress limits and a rolling segment/upload queue must be validated before any overnight configuration is represented as ready. Stop/delete this pilot when it is no longer needed so it does not occupy a free service slot.

## Local verification and limits

The image was built with Python 3.11, Node 22, FFmpeg and yt-dlp 2026.10.21. Local runtime tests use no external network and no cookies, a non-root UID 10001, a 512 MiB memory cap and a 0.2 CPU cap. They verify HTTP startup, honest missing-secret state, dependency activation and complete decoding of a known captured video. They do not establish Northflank capacity, provider egress, cookie validity or live recording there. See local-validation.json.

TLS and Debian package verification remain enabled. The optional BuildKit build_ca secret supports the current build proxy's trust bundle, is not copied into the image and is not required on a normal Northflank build using public trusted roots.

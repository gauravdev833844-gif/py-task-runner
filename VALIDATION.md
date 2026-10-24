# Validation — reliability v2

- **22 local tests passed**, including delayed/expired windows, 18-hour coverage, SIGINT-first shutdown, low-disk preservation, bounded concat failure, upload integrity/failure handling, guest reuse, and workflow failure propagation.
- **22 tests passed on a real GitHub runner**: [https://github.com/gauravdev833844-gif/py-task-runner/actions/runs/40096746402](https://github.com/gauravdev833844-gif/py-task-runner/actions/runs/40096746402). The initial diagnostic run failed because its test looked at the diagnostic workflow instead of the production-workflow fixture; the fixture path was corrected and the complete test rerun passed.
- **Fresh live engine capture passed** with the existing GitHub `YT_COOKIES` binding: SkyNews, **30.0 seconds**, **1280×720 H.264**, **10,701,524 bytes**. Complete audio/video decode passed on the GitHub runner and again after downloading the artifact locally. Executable recorder/helper/test sources in this ZIP match the passing validation branch.
- **Adaptive splitting exercised with real FFmpeg** at a reduced 260,000-byte cap: every part fitted, every part fully decoded, and the sum of video frames matched the original. The source was unchanged. This is a logic/integrity test, not an actual 2 GB split/upload test.
- **Two real Gofile uploads passed**, total **468,120 bytes**, using the new uploader and the same guest account/folder. Both provider size and MD5 acknowledgements matched; original files were retained. Download/readback was not tested.
- Workflow schema/expression lint passed with **actionlint 1.7.12**, plus Python parsing, Bash syntax, and package credential-pattern checks.

## Limits of this evidence

No five-channel simultaneous live test, no fifteen-channel run, no 18-hour overnight run, no multi-GB upload test, no actual GitHub Release upload, and no Telegram message delivery were performed. The uploaded cookies and the existing GitHub binding differ; this live test validates only the latter.

Shift coverage is a planned schedule, not a promise that queues, source failures or suspensions cannot create gaps. Local-only media can disappear when a hosted runner is deleted. Free hosting/provider capacity and suitability remain separate from code correctness. See README.md and CAPACITY_AND_LIMITS.md.

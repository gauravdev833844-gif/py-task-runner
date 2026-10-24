# Validation — manual-start 8/9-hour update

- **23 local tests passed**. **23 tests passed on the GitHub runner**: https://github.com/gauravdev833844-gif/py-task-runner/actions/runs/40098046141.
- The new scheduling tests cover arbitrary manual starts at 19:00, 20:30, 22:00 and 00:00; both 8-hour and 9-hour choices; exactly two windows; Shift 2 at +4 hours; one hour overlap; no Shift 3; expired duplicates; and rejection of durations above 9 hours. The short 0.1-hour test remains available.
- The controller job now has 260 minutes, sufficient for its four-hour wait plus dispatch overhead. Workflow lint passed with actionlint 1.7.12.
- Earlier live proof remains applicable to the **unchanged recorder engine**: 30 seconds, 1280×720 H.264 SkyNews capture, 10,701,524 bytes; complete audio/video decode passed on the GitHub runner and after download. Proof: https://github.com/gauravdev833844-gif/py-task-runner/actions/runs/40096746402 . This used the existing GitHub cookie binding, not the uploaded cookie file.
- The unchanged uploader previously completed two small real Gofile uploads (468,120 bytes total), with matching provider size/MD5 acknowledgements. Generated-media splitting preserved all video frames and every output fully decoded at a reduced byte cap.

These tests validate schedule logic and bounded operations. No actual eight/nine-hour run, four-hour live handover, five-channel overnight workload, multi-GB upload/readback, real Release upload or Telegram delivery has been verified. Runner queues can affect actual start and handover timing. Provider/free-plan suitability remains separate from code correctness.

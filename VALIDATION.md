# Current setup validation

- 30 tests passed locally and on GitHub: https://github.com/gauravdev833844-gif/py-task-runner/actions/runs/40102452716 .
- Rclone copy/remote-size/MD5 contract passed using the real CLI with an owned local filesystem backend. **This is not a Google Drive authentication or upload test.** No Google Drive OAuth configuration is available yet.
- Simulated Gofile failure followed by an **actual draft GitHub Release upload, download and SHA-256 readback** passed using 233,496 bytes of generated media. Full audio/video decode and source preservation passed; the temporary draft was deleted. The first draft test found a release-by-tag metadata lookup limitation; using the CLI asset metadata lookup fixed it and the rerun passed.
- Earlier real SkyNews validation used 0.1-hour monitoring, produced 344.985422 seconds of 1280×720 video (140,166,784 bytes), fully decoded, and uploaded to Gofile in 3.8 seconds with matching provider size/MD5. Evidence: https://github.com/gauravdev833844-gif/py-task-runner/actions/runs/40099263317 . The recorder engine remains unchanged; the uploader now adds the optional Drive-first path and budget reserves.
- Current schedule tests cover four three-hour windows starting every two hours, one hour overlap and a common 8/9-hour deadline. Upload can continue after a recording window, independently of the next recorder.

Actual Google Drive access, the claimed 5 TB allowance, multi-GB uploads, full overnight handovers, five concurrent live channels and Telegram delivery are not verified. The uploaded cookie file differs from the old working GitHub binding; historical capture success validates that existing binding only.

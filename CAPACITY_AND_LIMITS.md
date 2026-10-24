# Capacity and limits — v2

One account has five repositories and five channels; three accounts together have fifteen. Account-wide quotas include overlapping recording, controller and preparation jobs. More repositories do not increase an account quota. Changing accounts or IPs is not a quota or suspension workaround.

At 2 Mbit/s total bitrate, five hours is about 4.5 GB per channel. Five channels produce 22.5 GB; fifteen produce 67.5 GB, before overlap. Splitting does not compress that data.

For a continuously live source, the two windows in the 9-hour plan record 10 hours in total (two 5-hour windows, with one hour of overlap). At 2 Mbit/s, five continuous channels can therefore generate about 45 GB, or fifteen about 135 GB. An 8-hour plan records 9 hours per continuously live channel. These are arithmetic projections, not measured workload tests.

Five channels can have ten recording jobs during overlap, plus controller/preparation jobs. GitHub job concurrency limits are account-wide; hosted jobs have a six-hour execution ceiling. The workflow reserves time for cleanup and one shared 30-minute upload deadline, but queues, network errors and lost child dispatches can still create gaps.

The workflow prints real disk availability. It does not promise 30 GB freed by deleting bundled tools. A low-disk reserve stops recording and reports failure; it cannot create missing disk or recover future footage. Source chunks are retained when concatenation would require too much free space.

Gofile has its own traffic, retention, account/IP and abuse controls. Small successful uploads are not evidence of five simultaneous multi-GB uploads. GitHub Release assets must each be smaller than 2 GiB; the helper uses a conservative 2,000,000,000-byte cap. Release assets follow repository visibility. Neither route promises permanent free video storage.

Use GitHub-hosted Actions for bounded development/testing in accordance with its terms; sustained recording needs an allowed runtime. This package does not supply free hosting, remove restrictions or establish that all fifteen channels will work.

# Capacity and limits

Three-hour recording windows start every two hours, leaving a shared two-hour upload budget within each six-hour GitHub job. The default nine-hour plan records up to twelve hours per continuously live channel (including duplicate footage); an eight-hour plan records eleven hours. At 2 Mbit/s, nine-hour monitoring can therefore produce about 10.8 GB per continuously live channel, 54 GB for five channels, or 162 GB for fifteen. These are projections, not tested capacity.

Google Drive storage allowance is not an upload-speed promise. Drive API limits depend on the account and workload. The same Drive account aggregates uploads from all repositories; verify quota and a real upload after OAuth connection. The Google Workspace limits page documents 750 GB/user/day and a 5 TB maximum file size; do not assume this verifies a consumer Gemini/Jio plan. Source: https://developers.google.com/workspace/drive/api/guides/limits .

GitHub-hosted job limits and account-wide concurrency remain in force. More repositories/accounts are not a quota or suspension workaround. Continuous media archiving must be allowed by the runtime/provider terms; setup does not guarantee account safety or unlimited free capacity.

Source files are kept on the runner. If all destinations fail and the hosted runner is removed, local-only media is not a durable backup. Drive copy, Gofile and optional Release fallback share one deadline; backups may still fail. Release assets must be under 2 GiB; adaptive splitting verifies each part against a conservative 2,000,000,000-byte cap. Public repository Release assets are public.

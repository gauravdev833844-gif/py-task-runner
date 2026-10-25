# One-time private credential repair

Complete this on your own Windows PC. Do not paste credentials into chat or source files. These steps do not change a source access denial into a guarantee of future access.

## Google Drive

After Google Cloud Audience reports **In production**, reconnect the existing remote in the rclone folder:

```bat
.\rclone.exe config reconnect drive:
.\rclone.exe about drive:
```

Choose browser authentication, authorize the Johnwatson account that reports 5 TiB, and decline Shared Drive for a normal personal Drive. Reauthorization after publication is necessary to replace a refresh token issued during Testing. Production does not need to be repeated daily.

The complete configuration is at `%APPDATA%\rclone\rclone.conf`. A client ID/secret pair alone does not include the Drive refresh token.

## Update five repositories in one command

Use GitHub CLI installed from https://cli.github.com/ on the same owner PC. `gh auth status` shows configured accounts; use `gh auth login --web --git-protocol https` or `gh auth switch --user OWNER` to select the intended owner. `gh api user --jq .login` must print that owner before making changes. Do not send the device code or access token in chat.

The commands below are for **Windows CMD**, where `%R` is correct. A `.bat` file needs `%%R` instead.

While logged in as **gauravdev833844-gif**:

```bat
for %R in (py-task-runner py-task-reposit py-task-newrepo py-task-repo4 yt-recorder) do gh secret set RCLONE_CONFIG --repo gauravdev833844-gif/%R < "%APPDATA%\rclone\rclone.conf"
```

While logged in as **h29257583-svg**:

```bat
for %R in (py-task-floxrepo py-task-reposaksh py-task-pbrepo py-task-repouzii script-py-reporish) do gh secret set RCLONE_CONFIG --repo h29257583-svg/%R < "%APPDATA%\rclone\rclone.conf"
```

While logged in as **johnwatson739418-lab**:

```bat
for %R in (python-script-task py-task-repo-pran py-task-repoansh py-task-repoarhan py-task-reponihaan python-task-repogoredo) do gh secret set RCLONE_CONFIG --repo johnwatson739418-lab/%R < "%APPDATA%\rclone\rclone.conf"
```

Each CLI result must show success. These owner-PC commands use GitHub's normal encrypted secret API. They are not executed in this cloud session; the connector's Secrets API access is denied with 403.

The optional Python helper `update_private_secrets.py` provides owner checks, a dry run and private local input for Drive, cookies and optional Telegram bindings. It does not recover or reveal an existing GitHub secret.

## YouTube authorization

Cookie syntax passing is not proof of authentication. Real CI capture must obtain media, fully decode it and verify a Drive copy. On explicit bot-check/403/429, stop automatic retries and repair legitimate source authorization. Do not rotate accounts, proxies or IPs to bypass a denial.

For legitimate cookie export, follow the current official yt-dlp guide: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies . It describes a dedicated private browser session, visiting YouTube's robots.txt in that session, exporting only the YouTube cookies in Netscape format, and closing the private session afterward. Use a trusted export tool. Avoid opening and refreshing the exported account's session afterward because YouTube can rotate the session cookies. Never upload the cookie file to a public repository.

On the owner PC, the helper can update `YT_COOKIES` from the private local file:

```bat
python update_private_secrets.py --owner h29257583-svg --drive-config "%APPDATA%\rclone\rclone.conf" --cookies-path "C:\path\to\your-private-youtube-cookies.txt" --dry-run
```

Replace the sample cookie path with the real private file path. Run without `--dry-run` only after the owner and intended repositories are correct. Neither path example is an actual credential. Fresh cookies still cannot guarantee that a datacenter IP will be accepted by YouTube.

## Optional Telegram

`check_telegram.py` only checks getMe/getChat; it never sends a message. Telegram secrets are optional for capture/upload. If a bot token was shared in chat, replace it through BotFather and store the new token privately. The helper's `--set-telegram` flag prompts without echo and writes both bindings to the selected owner's repositories.

## Johnwatson app access

Collaboration invitations and a Codex GitHub App installation are separate. To authorize this connector for code/workflow writes, the owner can install/configure https://github.com/apps/chatgpt-codex-connector/installations/new for the six intended repositories. Current API access is read-only there despite collaborator push metadata. No code install or test result is claimed for those six until actual write/dispatch succeeds.

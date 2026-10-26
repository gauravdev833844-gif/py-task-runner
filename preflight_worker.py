"""Bounded Drive round trip and sequential YouTube metadata only.

Credentials come only from the existing workflow secrets. Raw extractor/provider
responses stay in memory; artifacts are built from explicit public-field allowlists.
"""
import argparse
import configparser
from dataclasses import dataclass
import datetime
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid


EXPECTED_YT_DLP = "2026.10.21"
SURVEY_CHANNELS = ("@SkyNews", "@NASA", "@NASAEarth", "@SpaceVideos")
OPERATION_SECONDS = 45
PUBLIC_TEXT = re.compile(r"[A-Za-z0-9_.:+-]{1,100}\Z")
CHANNEL_ID = re.compile(r"UC[A-Za-z0-9_-]{22}\Z")
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}\Z")
LIVE_STATUSES = {"is_live", "is_upcoming", "was_live", "post_live", "not_live"}
SECRET_VARIABLES = (
    "YT_COOKIES", "RCLONE_CONFIG_TEXT", "RCLONE_CONFIG", "GH_TOKEN",
    "GITHUB_TOKEN", "GOFILE_TOKEN", "GOFILE_FOLDER_ID", "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


@dataclass
class Outcome:
    code: int
    stdout: bytes = b""
    stderr: bytes = b""
    timed_out: bool = False


def child_environment():
    environment = os.environ.copy()
    for name in SECRET_VARIABLES:
        environment.pop(name, None)
    return environment


def bounded_run(command, *, timeout=OPERATION_SECONDS):
    """Run in the foreground and kill the entire process group at the deadline."""
    process = subprocess.Popen(
        command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=child_environment(), start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return Outcome(process.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = process.communicate(timeout=5)
        return Outcome(process.returncode, stdout, stderr, True)


def write_private(path, content):
    with path.open("w", encoding="utf-8") as stream:
        stream.write(content)
    path.chmod(0o600)


def cookie_syntax_valid(value):
    if not isinstance(value, str) or not value.strip():
        return False
    for line in value.splitlines():
        if line.startswith("#HttpOnly_"):
            line = line[len("#HttpOnly_"):]
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        domain = fields[0].lstrip(".").casefold()
        if (len(fields) == 7 and fields[-1] and
                (domain == "youtube.com" or domain.endswith(".youtube.com"))):
            return True
    return False


def drive_syntax_valid(value):
    try:
        config = configparser.ConfigParser(interpolation=None)
        config.read_string(value)
        token = json.loads(config.get("drive", "token", fallback="{}"))
        return bool(
            config.get("drive", "type", fallback="") == "drive"
            and config.get("drive", "client_id", fallback="").strip()
            and config.get("drive", "client_secret", fallback="").strip()
            and isinstance(token, dict) and token.get("refresh_token")
        )
    except (configparser.Error, ValueError, TypeError, AttributeError):
        return False


def denial_reason(raw):
    """Return fixed codes, never a fragment of a provider's error text."""
    text = raw.decode("utf-8", errors="replace").casefold()
    if any(value in text for value in (
        "not a bot", "automated queries", "unusual traffic", "bot verification",
    )):
        return "youtube_bot_verification"
    if re.search(r"\b429\b", text) or "too many requests" in text:
        return "youtube_rate_limited"
    if re.search(r"\b403\b", text) or "forbidden" in text or "access denied" in text:
        return "youtube_access_denied"
    if any(value in text for value in (
        "private video", "members-only", "members only", "join this channel",
        "sign in", "login required", "log in", "confirm your age", "age-restricted",
        "video unavailable", "video is unavailable", "video has been removed",
        "not available in your country", "not available in your region",
        "account has been suspended", "channel does not exist",
    )):
        return "youtube_explicit_denial"
    return None


def numeric(value, maximum):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value) and 0 <= value <= maximum:
            return value
    return None


def public_string(value):
    return value if isinstance(value, str) and PUBLIC_TEXT.fullmatch(value) else None


def public_formats(info):
    rows = []
    formats = info.get("formats")
    if not isinstance(formats, list):
        return rows
    for item in formats:
        if not isinstance(item, dict):
            continue
        # A storyboard or incomplete flat entry is not a media-format result.
        media_url = item.get("url")
        if not isinstance(media_url, str) or not media_url.startswith(("https://", "http://")):
            continue
        if not any(public_string(item.get(key)) not in {None, "none"} for key in ("vcodec", "acodec")):
            continue
        row = {
            "height": numeric(item.get("height"), 20000),
            "width": numeric(item.get("width"), 30000),
            "fps": numeric(item.get("fps"), 1000),
            "protocol": public_string(item.get("protocol")),
            "format_id": public_string(item.get("format_id")),
            "tbr": numeric(item.get("tbr"), 1000000),
            "acodec": public_string(item.get("acodec")),
            "vcodec": public_string(item.get("vcodec")),
        }
        if row["format_id"] and row["protocol"]:
            rows.append(row)
    return rows


def sanitize_metadata(info, channel):
    row = {
        "channel": channel, "source_validity": "inconclusive",
        "channel_id": None, "video_id": None, "is_live": None,
        "live_status": None, "formats": [], "stop_survey": False,
    }
    if not isinstance(info, dict) or info.get("_type", "video") != "video":
        row["reason"] = "incomplete_extractor_result"
        return row
    channel_id, video_id = info.get("channel_id"), info.get("id")
    row["channel_id"] = channel_id if isinstance(channel_id, str) and CHANNEL_ID.fullmatch(channel_id) else None
    row["video_id"] = video_id if isinstance(video_id, str) and VIDEO_ID.fullmatch(video_id) else None
    live_status = info.get("live_status")
    row["live_status"] = live_status if isinstance(live_status, str) and live_status in LIVE_STATUSES else None
    row["is_live"] = info.get("is_live") if isinstance(info.get("is_live"), bool) else None
    row["formats"] = public_formats(info)
    if not row["channel_id"] or not row["video_id"]:
        row["reason"] = "invalid_or_missing_public_ids"
    elif row["is_live"] is True and live_status == "is_live" and row["formats"]:
        row["source_validity"] = "valid_live_metadata"
    elif row["live_status"] in {"is_upcoming", "was_live", "post_live", "not_live"}:
        row["source_validity"] = "confirmed_not_live"
    else:
        row["reason"] = "live_media_formats_unconfirmed"
    return row


def channel_url(channel):
    if re.fullmatch(r"@[A-Za-z0-9_.-]{1,100}", channel):
        return "https://www.youtube.com/" + channel + "/live"
    if CHANNEL_ID.fullmatch(channel):
        return "https://www.youtube.com/channel/" + channel + "/live"
    return None


def probe_channel(channel, cookie_text, private_root):
    row = {
        "channel": channel, "source_validity": "inconclusive",
        "channel_id": None, "video_id": None, "is_live": None,
        "live_status": None, "formats": [], "stop_survey": False,
    }
    target = channel_url(channel)
    if not target:
        row["reason"] = "invalid_channel_input"
        return row
    # Each invocation owns its cookie copy. yt-dlp may update it on exit.
    with tempfile.TemporaryDirectory(prefix="youtube-", dir=private_root) as directory:
        cookie_path = Path(directory) / "cookies.txt"
        write_private(cookie_path, cookie_text)
        command = [
            sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-cache-dir",
            "--js-runtimes", "node", "--socket-timeout", "10",
            "--retries", "0", "--extractor-retries", "0", "--fragment-retries", "0",
            "--no-playlist", "--skip-download", "--dump-single-json",
            "--cookies", str(cookie_path), target,
        ]
        try:
            outcome = bounded_run(command)
        except OSError:
            row["reason"] = "extractor_process_unavailable"
            return row
        blocked = denial_reason(outcome.stderr)
        if blocked:
            row.update(source_validity="blocked", reason=blocked, stop_survey=True)
        elif outcome.timed_out:
            row["reason"] = "metadata_timeout"
        elif outcome.code:
            # A generic failure is never counted as an offline channel.
            if "the channel is not currently live" in outcome.stderr.decode("utf-8", errors="replace").casefold():
                row.update(source_validity="confirmed_not_live", is_live=False, reason="channel_explicitly_not_live")
            else:
                row["reason"] = "metadata_extraction_failed"
        else:
            try:
                row = sanitize_metadata(json.loads(outcome.stdout), channel)
            except (ValueError, TypeError):
                row["reason"] = "invalid_metadata_json"
        return row


class DriveFailure(Exception):
    pass


def drive_roundtrip(config_text, private_root):
    result = {
        "status": "FAIL", "scope": "one_generated_tiny_file",
        "remote_size_md5_confirmed": False, "readback_sha256_matches": False,
        "cleanup_required": False, "cleanup_success": False,
        "sharing": "sharing_permissions_not_modified_or_verified",
    }
    if not shutil.which("rclone"):
        result["failure"] = "rclone_missing_prerequisite"
        return result
    if not drive_syntax_valid(config_text):
        result["failure"] = "drive_secret_missing_or_invalid_own_oauth_config"
        return result
    with tempfile.TemporaryDirectory(prefix="drive-", dir=private_root) as directory:
        root = Path(directory)
        config = root / "rclone.conf"
        write_private(config, config_text)
        source = root / "generated-check.txt"
        source.write_bytes(b"Bounded generated Google Drive round trip.\n" * 64)
        source.chmod(0o600)
        data = source.read_bytes()
        batch_id = os.environ.get("PREFLIGHT_BATCH_ID", "bounded-" + os.environ.get("GITHUB_RUN_ID", "local"))
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", batch_id):
            result["failure"] = "invalid_preflight_batch_id"
            return result
        remote = "drive:RecorderCITests/" + batch_id + "/preflight-check-" + uuid.uuid4().hex + ".txt"
        base = [
            "rclone", "--config", str(config), "--retries", "1",
            "--low-level-retries", "1", "--contimeout", "10s",
            "--timeout", "20s", "--log-level", "ERROR", "--stats", "0",
        ]

        def operation(arguments, code):
            outcome = bounded_run(base + arguments)
            error_text = outcome.stderr.decode("utf-8", errors="replace").casefold()
            if re.search(r"\b429\b", error_text) or "too many requests" in error_text:
                raise DriveFailure("drive_rate_limited")
            if re.search(r"\b403\b", error_text) or "forbidden" in error_text or "access denied" in error_text:
                raise DriveFailure("drive_access_denied")
            if outcome.timed_out:
                raise DriveFailure(code + "_timeout")
            if outcome.code:
                raise DriveFailure(code + "_failed")
            return outcome.stdout

        try:
            quota = json.loads(operation(["about", "drive:", "--json"], "drive_quota_authorization"))
            if not isinstance(quota, dict):
                raise DriveFailure("drive_invalid_quota_response")
            result["quota_bytes"] = {
                key: quota[key] for key in ("total", "used", "free")
                if isinstance(quota.get(key), int) and not isinstance(quota.get(key), bool)
            }
            # Know the owned destination before uploading, including partial failure.
            result["cleanup_required"] = True
            operation(["copyto", str(source), remote, "--checksum", "--transfers", "1", "--checkers", "1"], "drive_copy")
            info = json.loads(operation(["lsjson", remote, "--stat", "--hash"], "drive_metadata"))
            hashes = info.get("Hashes", {}) if isinstance(info, dict) else {}
            md5 = next((value for key, value in hashes.items() if key.casefold() == "md5"), None) if isinstance(hashes, dict) else None
            if not isinstance(info, dict) or info.get("Size") != len(data) or md5 != hashlib.md5(data).hexdigest():
                raise DriveFailure("drive_remote_size_or_md5_mismatch")
            result["remote_size_md5_confirmed"] = True
            returned = operation(["cat", remote], "drive_readback")
            if hashlib.sha256(returned).digest() != hashlib.sha256(data).digest():
                raise DriveFailure("drive_readback_sha256_mismatch")
            result.update(status="PASS", readback_sha256_matches=True, bytes=len(data))
        except DriveFailure as error:
            result["failure"] = str(error)
        except (OSError, ValueError, TypeError, AttributeError):
            result["failure"] = "drive_operation_or_response_invalid"
        finally:
            if result["cleanup_required"]:
                try:
                    cleanup = bounded_run(base + ["deletefile", remote])
                    result["cleanup_success"] = cleanup.code == 0 and not cleanup.timed_out
                except OSError:
                    result["cleanup_success"] = False
                if not result["cleanup_success"]:
                    result.update(status="FAIL", failure="drive_test_file_cleanup_failed")
            else:
                result["cleanup_success"] = True
    return result


def prerequisites():
    try:
        version = importlib.metadata.version("yt-dlp")
    except importlib.metadata.PackageNotFoundError:
        version = None
    node_version = None
    if shutil.which("node"):
        try:
            node = bounded_run(["node", "--version"], timeout=5)
            value = node.stdout.decode("ascii", errors="ignore").strip()
            if node.code == 0 and re.fullmatch(r"v22\.\d+\.\d+", value):
                node_version = value
        except OSError:
            pass
    return {
        "yt_dlp_version": version if version and re.fullmatch(r"[0-9.]+", version) else None,
        "yt_dlp_pinned_version_ready": version == EXPECTED_YT_DLP,
        "node_22_version": node_version, "node_22_ready": bool(node_version),
        "rclone_present": bool(shutil.which("rclone")),
    }


def run_preflight(*, survey, channel, cookie_text, drive_text):
    report = {
        "schema": "bounded-preflight-v1", "status": "FAIL",
        "tested_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "tiny_drive_roundtrip_and_youtube_metadata_only",
        "media_downloaded": False, "overnight_workload_tested": False,
        "client": "default", "metadata_timeout_seconds": OPERATION_SECONDS,
        "prerequisites": prerequisites(), "sources": [], "survey_stopped": False,
    }
    channels = SURVEY_CHANNELS if survey else ((channel or "@SkyNews"),)
    report["requested_channels"] = list(channels) if all(channel_url(value) for value in channels) else []
    report["cookie_binding_present"] = bool(cookie_text)
    report["cookie_format_valid"] = cookie_syntax_valid(cookie_text)
    with tempfile.TemporaryDirectory(prefix="bounded-preflight-private-") as private:
        Path(private).chmod(0o700)
        report["drive"] = drive_roundtrip(drive_text, private)
        if not report["requested_channels"]:
            report["metadata_status"] = "invalid_channel_input"
        elif not report["cookie_format_valid"]:
            report["metadata_status"] = "cookie_secret_missing_or_invalid"
        elif not (report["prerequisites"]["yt_dlp_pinned_version_ready"] and report["prerequisites"]["node_22_ready"]):
            report["metadata_status"] = "metadata_prerequisite_failed"
        else:
            for candidate in channels:
                row = probe_channel(candidate, cookie_text, private)
                report["sources"].append(row)
                if row["stop_survey"]:
                    report["survey_stopped"] = True
                    break
            report["metadata_status"] = "blocked" if report["survey_stopped"] else "completed"
    valid = any(row["source_validity"] == "valid_live_metadata" for row in report["sources"])
    if report["drive"]["status"] == "PASS" and valid and not report["survey_stopped"]:
        report["status"] = "PASS"
    return report


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--survey", action="store_true", default=os.environ.get("PREFLIGHT_SURVEY", "false").casefold() == "true")
    parser.add_argument("--channel", default=os.environ.get("PREFLIGHT_CHANNEL", ""))
    args = parser.parse_args()
    cookie_text = os.environ.pop("YT_COOKIES", "")
    drive_text = os.environ.pop("RCLONE_CONFIG_TEXT", "")
    try:
        report = run_preflight(survey=args.survey, channel=args.channel, cookie_text=cookie_text, drive_text=drive_text)
    except Exception:
        # Never print traceback/provider text: cookie parsers can include cookie lines.
        report = {
            "schema": "bounded-preflight-v1", "status": "FAIL",
            "failure": "unexpected_preflight_failure", "media_downloaded": False,
            "drive": {"status": "FAIL", "failure": "preflight_interrupted"},
        }
    finally:
        cookie_text = ""
        drive_text = ""
    write_private(Path("preflight.json"), json.dumps(report, indent=2, allow_nan=False) + "\n")
    write_private(Path("drive-test-result.json"), json.dumps(report["drive"], indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, allow_nan=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

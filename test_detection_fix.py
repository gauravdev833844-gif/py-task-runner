"""Network-free tests for real recorder code paths, not mocked expected verdicts."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

ROOT = Path(__file__).parent
BOOT = tempfile.TemporaryDirectory(prefix="recorder-test-", dir="/tmp")
with patch.dict(os.environ, {"OUT_DIR": BOOT.name, "USE_COOKIES": "false"}):
    spec = importlib.util.spec_from_file_location("urgent_recorder", ROOT / "recorder.py")
    r = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r)


class RecorderFixTests(unittest.TestCase):
    def setUp(self):
        r.AUTH_BLOCKED.clear()
        r.STOP_REQUESTED = False
        r.FATAL_ERRORS_COUNT = 0
        r.LAST_FATAL_ERROR = None
        r.LIVE_DETECTED_EVER = False
        r.PROBE_OBSERVATIONS.update(live=0, offline=0, unknown=0)
        r.USE_COOKIES = False
        r.JS_ARGS = ["--js-runtimes", "node"]
        self.tmp = tempfile.TemporaryDirectory(prefix="cookie-test-", dir="/tmp")
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "original.txt"
        self.source.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tTEST_ONLY\tnot-a-login\n")
        r.COOKIE_FILE = str(self.source)
        self.original = self.source.read_bytes()

    def run_json(self, data, stderr="", code=0, url=None):
        result = subprocess.CompletedProcess([], code, json.dumps(data), stderr)
        with patch.object(r, "bounded_metadata_run", return_value=result) as call:
            value = r.run_ytdlp_json(url or r.LIVE_URL, None)
        return value, call

    def test_partial_metadata_is_unknown_not_offline(self):
        result, _ = self.run_json({"id": "aaaaaaaaaaa", "is_live": False})
        self.assertIsNone(result)
        self.assertEqual(r.observation_result([]), ("unknown", "observation_incomplete", 2))

    def test_explicit_channel_offline_is_distinct(self):
        result, _ = self.run_json(None, "ERROR: The channel is not currently live", 1)
        self.assertEqual(result["_observation"], "offline")
        self.assertEqual(r.observation_result([]), ("offline", None, 0))

    def test_arbitrary_ended_video_does_not_prove_channel_offline(self):
        self.run_json(None, "ERROR: This live event has ended", 1, "https://www.youtube.com/watch?v=aaaaaaaaaaa")
        self.assertEqual(r.observation_result([])[0], "unknown")

    def test_timeout_is_unknown(self):
        with patch.object(r, "bounded_metadata_run", side_effect=subprocess.TimeoutExpired([], 1)):
            self.assertIsNone(r.run_ytdlp_json(r.LIVE_URL, None))
        self.assertEqual(r.PROBE_OBSERVATIONS["unknown"], 1)
        self.assertEqual(r.observation_result([])[2], 2)

    def test_zero_exit_partial_json_does_not_hide_bot_denial(self):
        self.run_json({"id": "aaaaaaaaaaa"}, "ERROR: Sign in to confirm you're not a bot")
        self.assertTrue(r.AUTH_BLOCKED.is_set())
        self.assertTrue(r.STOP_REQUESTED)
        self.assertEqual(r.observation_result([]), ("failed", "botcheck", 2))

    def test_invalid_cookies_stop_even_exit_zero(self):
        self.run_json({"id": "aaaaaaaaaaa"}, "WARNING: The provided YouTube account cookies are no longer valid")
        self.assertEqual(r.LAST_FATAL_ERROR, "invalid_cookies")
        self.assertTrue(r.AUTH_BLOCKED.is_set())

    def test_denied_probe_never_rotates_client_or_fetches_html(self):
        result = subprocess.CompletedProcess([], 1, "null", "Sign in to confirm you're not a bot")
        with patch.object(r, "bounded_metadata_run", return_value=result) as call, patch.object(r, "fetch_text") as html:
            self.assertIsNone(r.probe_fast())
            self.assertEqual(call.call_count, 1)
            html.assert_not_called()
            self.assertIsNone(r.run_ytdlp_json(r.LIVE_URL, "web"))
            self.assertEqual(call.call_count, 1)

    def test_live_requires_playable_formats(self):
        data = {"id": "aaaaaaaaaaa", "is_live": True, "live_status": "is_live", "formats": []}
        result, _ = self.run_json(data)
        self.assertIsNone(result)
        self.assertFalse(r.LIVE_DETECTED_EVER)
        self.assertEqual(r.observation_result([])[0], "unknown")

    def test_valid_live_is_accepted(self):
        data = {"id": "aaaaaaaaaaa", "is_live": True, "live_status": "is_live", "formats": [{"url": "https://example.invalid/media", "vcodec": "h264", "acodec": "aac"}]}
        result, _ = self.run_json(data)
        self.assertEqual(result["id"], data["id"])
        self.assertTrue(r.LIVE_DETECTED_EVER)
        self.assertEqual(r.PROBE_OBSERVATIONS["live"], 1)

    def test_storyboard_only_live_is_unknown(self):
        data = {"id": "aaaaaaaaaaa", "is_live": True, "formats": [{"url": "https://example.invalid/storyboard", "protocol": "mhtml", "vcodec": "images", "acodec": "none"}]}
        value, _ = self.run_json(data)
        self.assertIsNone(value)
        self.assertEqual(r.observation_result([])[0], "unknown")

    def test_separate_audio_and_video_formats_are_accepted(self):
        data = {"id": "aaaaaaaaaaa", "is_live": True, "formats": [
            {"url": "https://example.invalid/v", "vcodec": "h264", "acodec": "none"},
            {"url": "https://example.invalid/a", "vcodec": "none", "acodec": "aac"}]}
        value, _ = self.run_json(data)
        self.assertEqual(value["id"], "aaaaaaaaaaa")

    def test_stale_private_discovery_does_not_stop_monitoring(self):
        self.run_json(None, "ERROR: Private video", 1, "https://www.youtube.com/watch?v=aaaaaaaaaaa")
        self.assertFalse(r.AUTH_BLOCKED.is_set())
        self.assertFalse(r.STOP_REQUESTED)
        self.assertEqual(r.FATAL_ERRORS_COUNT, 0)

    def test_malformed_json_is_unknown(self):
        with patch.object(r, "bounded_metadata_run", return_value=subprocess.CompletedProcess([], 0, "{bad", "")):
            r.run_ytdlp_json(r.LIVE_URL, None)
        self.assertEqual(r.observation_result([])[0], "unknown")

    def test_explicit_offline_does_not_erase_unknown_window(self):
        r.record_probe_observation("offline")
        r.record_probe_observation("unknown")
        self.assertEqual(r.observation_result([])[0], "unknown")

    def test_partial_media_and_access_loss_is_failed(self):
        r.record_fatal_error("botcheck")
        self.assertEqual(r.observation_result(["valid.ts"]), ("partial_failed", "botcheck", 2))

    def test_renderer_badge_does_not_bleed_to_adjacent_video(self):
        page = json.dumps({"contents": [
            {"videoRenderer": {"videoId": "aaaaaaaaaaa", "title": {"simpleText": "recorded"}}},
            {"videoRenderer": {"videoId": "bbbbbbbbbbb", "badges": [{"metadataBadgeRenderer": {"style": "BADGE_STYLE_TYPE_LIVE_NOW", "label": "LIVE"}}]}},
            {"videoRenderer": {"videoId": "ccccccccccc", "title": {"simpleText": "recorded"}}},
        ]})
        self.assertEqual(r.extract_live_badge_ids(page), ["bbbbbbbbbbb"])

    def test_video_title_live_is_not_a_live_badge(self):
        page = json.dumps({"videoRenderer": {"videoId": "aaaaaaaaaaa", "title": {"runs": [{"text": "LIVE"}]}}})
        self.assertEqual(r.extract_live_badge_ids(page), [])

    def test_renderer_nested_braces_and_escaped_strings(self):
        page = '<script>var ytInitialData=' + json.dumps({"gridVideoRenderer": {"videoId": "aaaaaaaaaaa", "title": {"simpleText": 'brace } { and "'}, "thumbnailOverlays": [{"thumbnailOverlayTimeStatusRenderer": {"style": "LIVE"}}]}}) + ';</script>'
        self.assertEqual(r.extract_live_badge_ids(page), ["aaaaaaaaaaa"])
        self.assertEqual(r.extract_live_badge_ids('"videoRenderer":{"videoId":"bbbbbbbbbbb","badges":['), [])

    def test_concurrent_cookie_jars_private_unique_and_cleaned(self):
        r.USE_COOKIES = True
        seen = []
        lock = threading.Lock()
        def child(cmd, **kwargs):
            cookie = Path(cmd[cmd.index("--cookies") + 1])
            with lock:
                seen.append((str(cookie), cookie.read_bytes(), stat.S_IMODE(cookie.stat().st_mode)))
            return subprocess.CompletedProcess(cmd, 1, "null", "The channel is not currently live")
        with patch.object(r, "bounded_metadata_run", side_effect=child):
            with ThreadPoolExecutor(max_workers=6) as pool:
                list(pool.map(lambda _: r.run_ytdlp_json(r.LIVE_URL, None), range(12)))
        self.assertEqual(len({row[0] for row in seen}), 12)
        self.assertTrue(all(row[1] == self.original and row[2] == 0o600 for row in seen))
        self.assertTrue(all(not Path(row[0]).exists() for row in seen))
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_download_cookie_lifetime_and_exception_cleanup(self):
        r.USE_COOKIES = True
        seen = []
        def child(active, end, client, queue, cookie):
            p = Path(cookie)
            seen.append(p)
            self.assertTrue(p.exists())
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
            self.assertNotEqual(str(p), str(self.source))
            raise RuntimeError("synthetic child failure")
        with patch.object(r, "_run_download_attempt", side_effect=child):
            with self.assertRaises(RuntimeError):
                r.run_download_attempt({}, 0, None, None)
        self.assertFalse(seen[0].exists())
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_download_command_requires_private_cookie_and_runtime(self):
        r.USE_COOKIES = True
        with self.assertRaisesRegex(RuntimeError, "private_cookie_path_required"):
            r.make_download_cmd({"live_url": "https://example.invalid"}, "x.ts", None)
        with r.private_cookie_copy() as path:
            cmd = r.make_download_cmd({"live_url": "https://example.invalid"}, "x.ts", None, path)
            self.assertEqual(cmd[cmd.index("--cookies") + 1], path)
            self.assertIn("--js-runtimes", cmd)
            self.assertEqual(cmd[cmd.index("--socket-timeout") + 1], "15")
            self.assertNotIn(str(self.source), cmd)

    def test_optional_streamlink_command_uses_owned_private_cookie(self):
        r.USE_COOKIES = True
        with patch.dict(os.environ, {"CAPTURE_TRANSPORT": "streamlink_hls"}), patch.object(r.os.path, "isfile", return_value=True):
            with r.private_cookie_copy() as cookie:
                cmd = r.make_download_cmd({"live_url": "https://www.youtube.com/watch?v=aaaaaaaaaaa"}, "chunk.ts", None, cookie)
                self.assertTrue(cmd[1].endswith("hls_capture.py"))
                self.assertEqual(cmd[cmd.index("--client") + 1], "default")
                self.assertEqual(cmd[cmd.index("--cookies") + 1], cookie)
                self.assertEqual(cmd[cmd.index("--format") + 1], r.FORMAT_SELECTOR)
                self.assertNotIn(str(self.source), cmd)

    def test_optional_transport_requires_its_packaged_helper(self):
        with patch.dict(os.environ, {"CAPTURE_TRANSPORT": "streamlink_hls"}), patch.object(r.os.path, "isfile", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "hls_capture_helper_missing"):
                r.make_download_cmd({"live_url": "https://example.invalid"}, "chunk.ts", None)

    def test_blocked_account_never_launches_native_or_helper_capture(self):
        r.record_fatal_error("botcheck")
        with patch.object(r, "_run_download_attempt") as launch:
            for transport in ["native", "streamlink_hls"]:
                with patch.dict(os.environ, {"CAPTURE_TRANSPORT": transport}):
                    self.assertEqual(r.run_download_attempt({}, 0, None, None), (False, "botcheck", None))
        launch.assert_not_called()

    def test_probe_command_has_runtime_and_no_ignore_no_formats(self):
        _, call = self.run_json({"id": "aaaaaaaaaaa"})
        cmd = call.call_args.args[0]
        self.assertIn("--js-runtimes", cmd)
        self.assertNotIn("--ignore-no-formats-error", cmd)
        self.assertNotIn("--no-warnings", cmd)

    def test_runtime_prefers_installed_deno_then_node(self):
        with patch.object(r, "command_exists", side_effect=lambda name: name in {"deno", "node"}):
            self.assertEqual(r.js_runtime_args(), ["--js-runtimes", "deno"])
        with patch.object(r, "command_exists", side_effect=lambda name: name == "node"):
            self.assertEqual(r.js_runtime_args(), ["--js-runtimes", "node"])

    def test_cookie_cleanup_if_source_read_fails(self):
        r.USE_COOKIES = True
        r.COOKIE_FILE = str(Path(self.tmp.name) / "absent")
        created = Path(self.tmp.name) / "copy.txt"
        def mk(**kwargs):
            fd = os.open(created, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            return fd, str(created)
        with patch.object(r.tempfile, "mkstemp", side_effect=mk), patch.object(r.os, "close", wraps=os.close) as close:
            with self.assertRaises(FileNotFoundError):
                with r.private_cookie_copy():
                    pass
            close.assert_not_called()
        self.assertFalse(created.exists())

    def test_preprovisioned_mode_does_not_run_pip_or_apt(self):
        with patch.dict(os.environ, {"SKIP_DEPENDENCY_INSTALL": "true"}), patch.object(r, "command_exists", return_value=True), patch.object(r.importlib.util, "find_spec", return_value=object()), patch.object(r.subprocess, "run") as call:
            r.install_dependencies()
        call.assert_not_called()

    def test_preprovisioned_mode_fails_missing_tools(self):
        with patch.dict(os.environ, {"SKIP_DEPENDENCY_INSTALL": "true"}), patch.object(r, "command_exists", return_value=False), patch.object(r.importlib.util, "find_spec", return_value=None), patch.object(r.subprocess, "run") as call:
            with self.assertRaisesRegex(SystemExit, "dependencies missing"):
                r.install_dependencies()
        call.assert_not_called()

    def test_short_exit_retries_allow_a_30_second_blink(self):
        self.assertGreaterEqual(r.SHORT_EXIT_BACKOFF_SECONDS, 30)
        self.assertGreaterEqual(r.STALL_SECONDS, 90)
        self.assertEqual(r.DOWNLOAD_CLIENTS, [None])
        self.assertEqual(r.VALIDATION_CLIENTS, [None])

    def test_capture_owns_group_and_cleans_it_after_leader_exit(self):
        process = unittest.mock.Mock()
        process.pid = 45678
        process.poll.return_value = 0
        process.stdout = io.StringIO("")
        active = r.new_session({"id": "aaaaaaaaaaa", "source": "unit_test"})
        with patch.object(r.subprocess, "Popen", return_value=process) as popen, patch.object(r, "stop_proc") as stop:
            r.run_download_attempt(active, r.time.time() + 5, None, r.Queue())
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertTrue(process._recorder_owned_group)
        stop.assert_called_once_with(process)

    def test_process_registry_tracks_own_group_and_cleans_after_stop(self):
        registry = Path(self.tmp.name) / "registry"
        registry.mkdir(mode=0o700)
        process = subprocess.Popen([r.sys.executable, "-c", "import time;time.sleep(60)"], start_new_session=True,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        process._recorder_owned_group = True
        try:
            with patch.dict(os.environ, {"RECORDER_PROCESS_REGISTRY": str(registry)}):
                r.register_owned_process(process, "capture")
            entries = list(registry.glob("*.json"))
            self.assertEqual(len(entries), 1)
            data = json.loads(entries[0].read_text())
            self.assertEqual(data["pid"], process.pid)
            self.assertEqual(data["kind"], "capture")
            self.assertIs(type(data["proc_start_ticks"]), int)
            self.assertEqual(stat.S_IMODE(entries[0].stat().st_mode), 0o600)
            self.assertEqual(entries[0].name, f'{process.pid}-{data["proc_start_ticks"]}.json')
        finally:
            r.stop_proc(process)
        self.assertIsNotNone(process.poll())
        self.assertFalse(list(registry.glob("*.json")))

    def test_registry_entry_is_retained_if_group_kill_is_denied(self):
        registry = Path(self.tmp.name) / "still-owned.json"
        registry.write_text("{}")
        process = unittest.mock.Mock()
        process.pid = 45678
        process._recorder_owned_group = True
        process._recorder_registry_path = str(registry)
        process.poll.return_value = 0
        with patch.object(r.os, "killpg", side_effect=PermissionError()):
            r.stop_proc(process)
        self.assertTrue(registry.exists())

    def test_actual_metadata_process_group_is_reaped_on_timeout(self):
        import time
        pid_file = Path(self.tmp.name) / "descendant.pid"
        script = (
            "import subprocess,sys,time; "
            "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); "
            "open(sys.argv[1],'w').write(str(child.pid)); time.sleep(60)"
        )
        with self.assertRaises(subprocess.TimeoutExpired):
            r.bounded_metadata_run([r.sys.executable, "-c", script, str(pid_file)], timeout=0.4)
        self.assertTrue(pid_file.exists())
        pid = int(pid_file.read_text())
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            stat_path = Path(f"/proc/{pid}/stat")
            if not stat_path.exists() or stat_path.read_text().split()[2] == "Z":
                break
            time.sleep(0.02)
        else:
            self.fail("owned metadata descendant remained running after timeout cleanup")

    def test_stop_proc_kills_owned_descendants_even_after_leader_exit(self):
        process = unittest.mock.Mock()
        process.pid = 45678
        process._recorder_owned_group = True
        process.poll.return_value = 0
        with patch.object(r.os, "killpg") as kill:
            r.stop_proc(process)
        kill.assert_called_once_with(45678, r.signal.SIGKILL)
        process.wait.assert_called_once_with(timeout=2)

    def test_stop_proc_does_not_signal_unowned_process_group(self):
        process = unittest.mock.Mock()
        process.pid = 45678
        process._recorder_owned_group = False
        process.poll.return_value = None
        with patch.object(r.os, "killpg") as kill:
            r.stop_proc(process)
        kill.assert_not_called()
        process.send_signal.assert_called_once_with(r.signal.SIGINT)

    def concat_fixture(self):
        directory = Path(self.tmp.name) / "chunks"
        directory.mkdir()
        first, second = directory / "video_chunk0001.ts", directory / "video_chunk0002.ts"
        first.write_bytes(b"A" * 3760)
        second.write_bytes(b"B" * 3760)
        return {"chunks": [str(first), str(second)], "chunk_dir": str(directory),
                "chunk_index": 3, "final_ts": str(Path(self.tmp.name) / "combined.ts")}, first, second

    def test_successful_concat_preserves_all_unverified_source_chunks(self):
        active, first, second = self.concat_fixture()
        def concat(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(first.read_bytes() + second.read_bytes())
            return subprocess.CompletedProcess(cmd, 0, "", "")
        free = first.stat().st_size + second.stat().st_size + r.MIN_FREE_BYTES + 1
        with patch.object(r.shutil, "which", return_value="/test/ffmpeg"), patch.object(r.shutil, "disk_usage", return_value=type("Disk", (), {"free": free})()), patch.object(r.subprocess, "run", side_effect=concat):
            result = r.build_final_file(active)
        self.assertEqual(result, active["final_ts"])
        self.assertEqual(first.read_bytes(), b"A" * 3760)
        self.assertEqual(second.read_bytes(), b"B" * 3760)

    def test_low_disk_skips_concat_and_preserves_sources(self):
        active, first, second = self.concat_fixture()
        with patch.object(r.shutil, "which", return_value="/test/ffmpeg"), patch.object(r.shutil, "disk_usage", return_value=type("Disk", (), {"free": 1})()), patch.object(r.subprocess, "run") as concat:
            self.assertIsNone(r.build_final_file(active))
        concat.assert_not_called()
        self.assertEqual(first.read_bytes(), b"A" * 3760)
        self.assertEqual(second.read_bytes(), b"B" * 3760)
        self.assertFalse(Path(active["final_ts"]).exists())

    def test_output_does_not_print_signed_media_url(self):
        stream = io.StringIO("[download] https://example.invalid/signed?token=DUMMY\nERROR: Sign in to confirm you're not a bot\n")
        state = dict.fromkeys(["botcheck", "no_formats", "rate_limited", "not_live", "normal_exit", "unavailable"], False)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            r.output_reader(stream, state)
        self.assertNotIn("DUMMY", captured.getvalue())
        self.assertTrue(state["botcheck"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

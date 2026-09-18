import contextlib
from datetime import datetime, timezone
import io
import unittest
from unittest.mock import patch

import auto_release as release


class AutoReleaseTests(unittest.TestCase):
    def setUp(self):
        self.published = [{"draft": False, "prerelease": False,
                           "tag_name": "apple-password-gen-0.4.0", "published_at": "2026-08-26T01:18:23Z"}]
        self.pr = {
            "number": 2, "state": "open", "draft": False, "user": {"login": "codyps"},
            "head": {"ref": "release-plz-next", "sha": "checked-sha",
                     "repo": {"full_name": "codyps/password-gen"}},
            "base": {"ref": "master", "sha": "base-sha"}, "mergeable_state": "clean",
        }
        self.runs = [{"id": 10, "status": "completed", "conclusion": "success"}]
        self.jobs = [{"name": name, "status": "completed", "conclusion": "success"}
                     for name in release.REQUIRED_JOBS]

    def test_interval_boundary(self):
        for now, blocked in [("2026-09-02T01:18:22Z", True),
                             ("2026-09-02T01:18:23Z", False)]:
            with self.subTest(now=now):
                self.assertEqual(bool(release.cooldown_reason(
                    self.published, [], release.timestamp(now))), blocked)

    def test_new_manual_release_resets_interval(self):
        self.published.append({**self.published[0], "published_at": "2026-09-01T00:00:00Z"})
        self.assertIsNotNone(release.cooldown_reason(
            self.published, [], release.timestamp("2026-09-02T01:18:23Z")))

    def test_missing_release_fails_closed(self):
        self.assertIsNotNone(release.cooldown_reason([], [], datetime.now(timezone.utc)))

    def test_pending_publication_blocks_even_after_one_week(self):
        closed = [{"merged_at": "2026-08-27T00:00:00Z"}]
        self.assertIn("awaiting publication", release.cooldown_reason(
            self.published, closed, release.timestamp("2026-10-01T00:00:00Z")))

    def test_draft_prerelease_and_other_package_do_not_reset_interval(self):
        for extra in [{"draft": True}, {"prerelease": True}, {"tag_name": "other-1.0.0"}]:
            with self.subTest(extra=extra):
                entries = self.published + [{**self.published[0],
                                            "published_at": "2026-09-01T00:00:00Z", **extra}]
                self.assertIsNone(release.cooldown_reason(
                    entries, [], release.timestamp("2026-09-02T01:18:23Z")))

    def test_release_pr_must_be_same_repository_and_default_branch(self):
        self.assertTrue(release.release_pr(self.pr, "codyps/password-gen", "master"))
        self.pr["head"]["repo"]["full_name"] = "someone/password-gen"
        self.assertFalse(release.release_pr(self.pr, "codyps/password-gen", "master"))
        self.pr["head"]["repo"] = None
        self.assertFalse(release.release_pr(self.pr, "codyps/password-gen", "master"))

    def test_missing_skipped_or_failed_checks_block(self):
        self.assertTrue(release.ci_passed(self.runs, self.jobs))
        self.assertFalse(release.ci_passed(self.runs, self.jobs[:-1]))
        for conclusion in ["failure", "skipped", None]:
            with self.subTest(conclusion=conclusion):
                self.jobs[0]["conclusion"] = conclusion
                self.assertFalse(release.ci_passed(self.runs, self.jobs))

    def test_newer_pending_run_blocks_older_success(self):
        self.runs.append({"id": 11, "status": "in_progress", "conclusion": None})
        self.assertFalse(release.ci_passed(self.runs, self.jobs))

    def run_main(self, merge=True, changed=False, unsafe_file=False, held=False):
        root = "repos/codyps/password-gen"
        reads = {
            root: {"default_branch": "master"}, "user": {"login": "codyps"},
            f"{root}/pulls/2": self.pr,
        }
        collections = {
            f"{root}/pulls?state=open&base=master": [self.pr],
            f"{root}/pulls/2/files": [{"filename": "src/lib.rs" if unsafe_file else "apple-password-gen/Cargo.toml",
                                      "status": "modified"}],
            f"{root}/actions/workflows/ci.yml/runs?event=pull_request&head_sha=checked-sha": self.runs,
            f"{root}/actions/runs/10/jobs": self.jobs,
        }
        mutations = []
        pr_reads = 0

        def fake_api(endpoint, payload=None):
            nonlocal pr_reads
            if payload is not None:
                mutations.append((endpoint, payload))
                return {"merged": True, "sha": "merge-sha"}
            if endpoint.endswith("/pulls/2"):
                pr_reads += 1
                if changed and pr_reads == 2:
                    return {**self.pr, "head": {**self.pr["head"], "sha": "new-sha"}}
            return reads[endpoint]

        with (patch.object(release, "api", side_effect=fake_api),
              patch.object(release, "registry_versions", return_value=[]),
              patch.object(release, "pages", side_effect=lambda endpoint, key=None:
                           collections.get(endpoint, [])),
              patch.object(release, "cooldown_reason", side_effect=[None, "Hold-off" if held else None]),
              patch.dict("os.environ", {"GITHUB_REPOSITORY": "codyps/password-gen"}),
              patch("sys.argv", ["auto_release.py"] + (["--merge"] if merge else [])),
              contextlib.redirect_stdout(io.StringIO())):
            release.main()
        return mutations

    def test_merge_pins_examined_sha_and_preserves_release_pr_history(self):
        self.assertEqual(self.run_main(), [
            ("repos/codyps/password-gen/pulls/2/merge", {"sha": "checked-sha", "merge_method": "merge"})])

    def test_preview_never_merges(self):
        self.assertEqual(self.run_main(merge=False), [])

    def test_changed_head_unsafe_files_or_new_release_block_merge(self):
        for option in ["changed", "unsafe_file", "held"]:
            with self.subTest(option=option):
                self.assertEqual(self.run_main(**{option: True}), [])

    def test_draft_wrong_author_and_blocked_mergeability(self):
        for changes in [{"draft": True}, {"user": {"login": "someone"}},
                        {"mergeable_state": "blocked"}, {"mergeable_state": "unknown"}]:
            with self.subTest(changes=changes), patch.dict(self.pr, changes):
                self.assertEqual(self.run_main(), [])

    def test_pagination_reads_all_pages(self):
        with patch.object(release, "api", side_effect=[[{}] * 100, [{"id": 101}]]) as api:
            self.assertEqual(len(release.pages("repos/example/releases")), 101)
            self.assertIn("page=2", api.call_args.args[0])

    def test_pagination_limit_fails_instead_of_using_partial_history(self):
        with patch.object(release, "api", return_value=[{}] * 100):
            with self.assertRaisesRegex(RuntimeError, "Pagination limit"):
                release.pages("repos/example/releases")

    def test_registry_bootstraps_interval_without_github_release(self):
        versions = [{"num": "0.1.1", "created_at": "2026-09-01T12:00:00Z"}]
        for now, blocked in [("2026-09-08T11:59:59Z", True),
                             ("2026-09-08T12:00:00Z", False)]:
            with self.subTest(now=now):
                self.assertEqual(bool(release.cooldown_reason(
                    [], [], release.timestamp(now), versions)), blocked)

    def test_registry_manual_release_resets_interval(self):
        versions = [{"num": "0.1.2", "created_at": "2026-09-09T12:00:00Z"}]
        self.assertIsNotNone(release.cooldown_reason(
            self.published, [], release.timestamp("2026-09-10T00:00:00Z"), versions))

    def test_registry_prereleases_do_not_bootstrap_interval(self):
        versions = [{"num": "0.2.0-rc.1", "created_at": "2026-08-01T12:00:00Z"}]
        self.assertIsNotNone(release.cooldown_reason(
            [], [], release.timestamp("2026-09-10T00:00:00Z"), versions))


if __name__ == "__main__":
    unittest.main()

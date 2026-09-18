"""Periodically merge a checked release-plz PR; default to a read-only preview."""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import subprocess
from urllib.request import Request, urlopen

INTERVAL = timedelta(days=7)
REQUIRED_JOBS = {"Quality"}
RELEASE_FILES = {"Cargo.lock", "apple-password-gen/Cargo.toml",
                 "apple-password-gen/CHANGELOG.md"}


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def api(endpoint, payload=None):
    command = ["gh", "api", endpoint]
    if payload is not None:
        command += ["--method", "PUT", "--input", "-"]
    result = subprocess.run(
        command, input=json.dumps(payload) if payload is not None else None,
        text=True, capture_output=True, check=True, timeout=30,
    )
    return json.loads(result.stdout)


def pages(endpoint, key=None):
    # Bound API work as well as each individual request. Never use partial data.
    rows = []
    separator = "&" if "?" in endpoint else "?"
    for page in range(1, 21):
        data = api(f"{endpoint}{separator}per_page=100&page={page}")
        batch = data[key] if key else data
        rows.extend(batch)
        if len(batch) < 100:
            return rows
    raise RuntimeError("Pagination limit reached; manual inspection required")


def release_pr(pr, repository, branch):
    return (
        pr["head"]["ref"].startswith("release-plz-")
        and (pr["head"].get("repo") or {}).get("full_name") == repository
        and pr["base"]["ref"] == branch
    )


def registry_versions():
    request = Request(
        "https://crates.io/api/v1/crates/apple-password-gen/versions",
        headers={"User-Agent": "password-gen-release-automation (https://github.com/codyps/password-gen)"},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)["versions"]


def cooldown_reason(releases, closed_prs, now, versions=()):
    published = [timestamp(r["published_at"]) for r in releases
                 if not r["draft"] and not r["prerelease"]
                 and r["tag_name"].startswith("apple-password-gen-") and r["published_at"]]
    # Registry history bootstraps repositories without GitHub releases and also
    # accounts for manual publications. Yanked versions still count as releases.
    published.extend(timestamp(v["created_at"]) for v in versions if "-" not in v["num"])
    if not published:
        return "No published apple-password-gen release found; establish the first release manually"
    latest = max(published)
    # A merged PR reserves the next release until publication is observed.
    if any(p["merged_at"] and timestamp(p["merged_at"]) > latest for p in closed_prs):
        return "A merged release PR is still awaiting publication"
    due = latest + INTERVAL
    if now < due:
        return f"Release hold-off ends at {due.isoformat()}"
    return None


def ci_passed(runs, jobs):
    if not runs:
        return False
    latest = max(runs, key=lambda r: r["id"])
    return (latest["status"] == "completed" and latest["conclusion"] == "success"
            and REQUIRED_JOBS <= {j["name"] for j in jobs
                                 if j["status"] == "completed" and j["conclusion"] == "success"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--merge", action="store_true", help="Perform the eligible merge")
    args = parser.parse_args()
    repository = os.environ.get("GITHUB_REPOSITORY", "codyps/password-gen")
    if repository != "codyps/password-gen":
        raise RuntimeError("Automatic releases are only configured for codyps/password-gen")
    root = f"repos/{repository}"
    branch = api(root)["default_branch"]

    def holdoff():
        releases = pages(f"{root}/releases")
        closed = [p for p in pages(f"{root}/pulls?state=closed&base={branch}")
                  if release_pr(p, repository, branch)]
        return cooldown_reason(releases, closed, datetime.now(timezone.utc), registry_versions())

    reason = holdoff()
    if reason:
        print(reason)
        return
    candidates = [p for p in pages(f"{root}/pulls?state=open&base={branch}")
                  if release_pr(p, repository, branch)]
    if len(candidates) != 1:
        print(f"Expected one release PR; found {len(candidates)}. Nothing merged.")
        return
    pr = api(f"{root}/pulls/{candidates[0]['number']}")
    # The same PAT account creates and merges release-plz PRs. A branch prefix
    # alone is not sufficient evidence that a PR belongs to release automation.
    if pr["draft"] or pr["user"]["login"] != api("user")["login"]:
        print("Release PR is a draft or was not created by the release token account")
        return
    files = pages(f"{root}/pulls/{pr['number']}/files")
    if not files or any(f["filename"] not in RELEASE_FILES
                        or f["status"] not in {"modified", "added"} for f in files):
        print("Release PR changes files outside the expected release metadata")
        return
    sha = pr["head"]["sha"]
    runs = pages(f"{root}/actions/workflows/ci.yml/runs?event=pull_request&head_sha={sha}",
                 "workflow_runs")
    jobs = (pages(f"{root}/actions/runs/{max(runs, key=lambda r: r['id'])['id']}/jobs", "jobs")
            if runs else [])
    if not ci_passed(runs, jobs):
        print("Latest CI run must pass Quality")
        return
    current = api(f"{root}/pulls/{pr['number']}")
    if (current["state"] != "open" or current["draft"]
            or current["head"]["sha"] != sha or current["base"]["sha"] != pr["base"]["sha"]
            or not release_pr(current, repository, branch)
            or current["mergeable_state"] != "clean"):
        print("PR changed or GitHub has not confirmed it is cleanly mergeable")
        return
    reason = holdoff()
    if reason:
        print(reason)
        return
    print(f"Eligible release PR #{pr['number']} at {sha}")
    if args.merge:
        result = api(f"{root}/pulls/{pr['number']}/merge", {"sha": sha, "merge_method": "merge"})
        if not result.get("merged"):
            raise RuntimeError(f"GitHub declined the merge: {result.get('message')}")
        print(f"Merged release PR; the push-triggered release-plz job will publish {result['sha']}")
    else:
        print("Preview only; pass --merge to merge")


if __name__ == "__main__":
    main()

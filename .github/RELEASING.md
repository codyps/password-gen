# Releases

Pushes to `master` create or update a release-plz PR. CI checks formatting,
Clippy, tests, documentation, packaging, and the automatic release policy.
Merging a release PR publishes `apple-password-gen` and creates its GitHub release.
Ordinary commits do not publish (`release_always = false`).

The automatic release workflow checks hourly at minute 23. Once seven full days
have elapsed since the latest stable publication, it merges an eligible release
PR. GitHub schedule delays and CI can make publication later than seven days.
There must be new releasable changes; it does not manufacture weekly versions.

The clock uses the later of crates.io's publication timestamp and the matching
GitHub release timestamp. This supports the existing crates.io releases even
though the repository has no historical GitHub releases. A merged release PR
awaiting publication blocks further automatic merges. Missing history or API
errors prevent automatic merging. The current 0.1.1 publication is already more
than a week old, so the first passing release PR can merge on the next poll.

## GitHub setup

1. Create a **fine-grained personal access token** owned by an account with write
   access, restricted to **codyps/password-gen**. Give it repository permissions:
   **Contents: Read and write**, **Pull requests: Read and write**, and
   **Actions: Read-only** (used to verify CI runs and jobs). Metadata read access
   is automatic. Store it as the Actions repository secret **RELEASE_PLZ_TOKEN**.
   Renew it before expiry. Use the same token account to create and merge release
   PRs: the automatic merge script verifies their authorship.
2. Enable GitHub Actions and allow the pinned checkout and release-plz actions.
   Keep merge commits enabled in repository settings. Protect `master` with the
   **Quality** required check. Existing required reviews or rules also apply;
   the script will wait if GitHub reports the PR blocked. If unattended releases
   are desired, those rules must permit the token account's release PRs to merge.
3. Land these files on the default branch, `master`. Scheduled workflows only
   run once present there. GitHub's auto-merge setting is not needed: the script
   merges through the API after its checks succeed.

The PAT is used for PR creation/updates and merging, so both PR CI and the
push-triggered publishing workflow run automatically. The built-in `GITHUB_TOKEN`
does not trigger those downstream events; enabling “Allow GitHub Actions to
create and approve pull requests” alone does not fix that. This implementation
does not fall back to it for either operation. The publishing job itself uses
the built-in token for GitHub operations.

A GitHub App installation token can also trigger CI, but these workflows are
wired for the PAT above; an App requires token-generation steps and changing the
script's PAT-account author check.

## crates.io trusted publisher

In the settings for the existing **apple-password-gen** crate, add a GitHub
trusted publisher with:

- Owner: **codyps**
- Repository: **password-gen**
- Workflow filename: **release-plz.yml**
- Environment: **leave empty** (the publish job has no environment)

The publishing job has `id-token: write`. Release-plz exchanges the OIDC token
itself; no `CARGO_REGISTRY_TOKEN` secret or separate authentication action is
needed. Configure this before enabling the release workflows.

## Operating and recovering

Run **Automatic release** manually with `dry_run: true` (the default) to inspect
eligibility without merging. Locally, `GH_TOKEN=... python3
.github/scripts/auto_release.py` also defaults to a read-only preview; provide
the token through your shell's secure credential handling.

The merge script requires one same-repository release-plz PR authored by the PAT
account, only release metadata changes, a passing latest PR CI run for its exact
head, and clean mergeability. It rechecks the interval and pins the merge to that
head. It shares a concurrency group with the release PR writer.

If publication fails after merging, rerun the failed publishing job before
another release. Do not merge another release PR to bypass the pending release
guard. Manual merges are an explicit override of the seven-day automatic policy.

References: [release-plz GitHub tokens](https://release-plz.dev/docs/github/token),
[trusted publishing setup](https://release-plz.dev/docs/github/quickstart),
[release PR gating](https://release-plz.dev/docs/config#the-release_always-field).

# Workflows

The reusable GitHub Actions workflows of the Impulse Framework organization. Every repository of the organization calls them from its own `.github/workflows` files instead of carrying a copy, so a check changes in one place and every caller follows when it moves its pin. The workflows live in [`.github/workflows`](.github/workflows).

## The workflows

### Golang CI

[`golang-ci.yml`](.github/workflows/golang-ci.yml) checks a repository of Go code: it runs `go generate` and refuses a diff, runs the tests with the race detector and builds every package (once per build tag), runs govulncheck, Semgrep over the pull request's changes, and golangci-lint (once per build tag).

The modules are the packages of `release-please-config.json` (the working directory alone when there is no such file), and a module is changed when the diff against the base branch touches a file under it. Every job after `detect-modules` runs once and loops over the changed modules in series, so an unchanged module takes no runner and the check names carry no module. A push to the base branch checks every module: it is the merge result, and the caches it saves are the ones the next pull requests restore.

Inputs:

| Input | Default | Meaning |
| --- | --- | --- |
| `build-tags` | required | A JSON array of build tags; the test and lint jobs run once per entry, `""` being the untagged leg (`'["", "dev"]'`). |
| `golangci-lint-version` | `v1.56` | The golangci-lint release. |
| `golangci-lint-timeout` | `5m` | golangci-lint's timeout per module. |
| `golangci-lint-only-new-issues` | `false` | Report only the issues the pull request introduces. |
| `govulncheck-version` | `v1.8.0` | The golang.org/x/vuln release govulncheck runs from; the vulnerability database is read live. |
| `mockgen-version` | `v0.6.0` | The go.uber.org/mock release installed before `go generate`. |
| `semgrep-image` | pinned by digest | The Semgrep container image; the rules are read live. |
| `semgrep-config` | `auto` | The Semgrep configuration. |
| `semgrep-max-target-bytes` | `500000` | Files larger than this are not scanned. |
| `coverage` | `false` | The untagged test leg also measures statement coverage and writes a per-package table to the job summary. |
| `coverage-exclude` | `''` | A regular expression over file paths left out of the coverage table. |
| `upload-sarif` | `false` | Upload SARIF reports to the GitHub Advanced Security dashboard. |
| `working-directory` | `.` | The directory the modules are under. |
| `release-please-config-file` | `release-please-config.json` | The file whose packages are the modules. |
| `base-branch` | `''` | The branch the change is diffed against; empty means the pull request's base, or the repository's default branch for other events. |
| `runs-on` | `ubuntu-latest` | The runner for every job. |
| `runs-on-heavy` | `''` | The runner for the test and lint jobs alone; empty means `runs-on`. |

The check names a caller gets, with the job id `golang-ci` and the build tags `'["", "dev"]'`:

- `golang-ci / detect-modules`
- `golang-ci / Check for go generate changes`
- `golang-ci / Run tests and builds`
- `golang-ci / Run tests and builds (dev)`
- `golang-ci / Go Vulnerability Check`
- `golang-ci / Run Semgrep Scan`
- `golang-ci / Run golangci-lint`
- `golang-ci / Run golangci-lint (dev)`

`detect-modules` must be among a ruleset's required checks: a job skipped by its condition counts as a success for a required check, and the dependents of a failed job are skipped, so a failed detection would otherwise let a pull request through unchecked. When no module changed, the jobs after `detect-modules` are skipped and report success.

Each Go job restores the module cache and the build cache (the linter its analysis cache with them) from the nearest saved entry of its own lineage, keyed by the changed modules' go.sum files and the commit. GitHub serves a pull request only the entries saved on its own branch and on its base branch, which is why the calling workflow runs on `push` to the default branch too. A pull request run saves only when no entry for its go.sum files exists, so the caches grow with merges, not with pushes.

### Semantic Pull Request Title

[`semantic-pull-request-title.yml`](.github/workflows/semantic-pull-request-title.yml) holds a pull request's title to the [Conventional Commits](https://www.conventionalcommits.org/) form with the types the release configuration releases by: `feat`, `feature`, `fix`, `perf`, `revert`, `docs`, `deps`, `style`, `chore`, `refactor`, `cleanup`, `test`, `build`, `ci`, `upgrade`, `infra`, `config`. The title becomes the squash commit's subject, and release-please reads the version bump from it. It takes no inputs. A caller that also runs on a push to its base branch skips the job there, and the skip counts as a pass.

Check name, with the job id `semantic-titles`: `semantic-titles / Validate PR title`.

### Release Please

[`release-please.yml`](.github/workflows/release-please.yml) runs [release-please](https://github.com/googleapis/release-please) with a GitHub App's token, so the release pull request's merge starts the caller's other workflows (a push made with the workflow's own token starts none). This repository also runs it on its own pushes to `master`.

Inputs: `config-file` (`release-please-config.json`) and `manifest-file` (`.release-please-manifest.json`).

Secrets: `RELEASE_PLEASE_APP_CLIENT_ID` (the App's client id) and `RELEASE_PLEASE_APP_PEM` (its private key). `RELEASE_PLEASE_APP_ID` is the older name of the client id secret, kept so a caller that still passes it keeps working; a new caller passes `RELEASE_PLEASE_APP_CLIENT_ID`.

Check name, with the job id `release-please`: `release-please / release-please`.

## Calling a workflow

A workflow file in the caller's `.github/workflows` names the reusable workflow with `uses`, pinned by commit with the release it belongs to in a comment, as every action in these files is pinned. Dependabot moves the pin.

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [master] # the default branch: see the caches under Golang CI

jobs:
  golang-ci:
    uses: impulseframework/workflows/.github/workflows/golang-ci.yml@<commit> # v0.1.0
    with:
      build-tags: '["", "dev"]'
      golangci-lint-version: 'v2.14.0'
  semantic-titles:
    uses: impulseframework/workflows/.github/workflows/semantic-pull-request-title.yml@<commit> # v0.1.0
```

```yaml
name: Release Please
on:
  push:
    branches: [master]
  workflow_dispatch:

permissions: {}

jobs:
  release-please:
    permissions:
      contents: write
      pull-requests: write
    uses: impulseframework/workflows/.github/workflows/release-please.yml@<commit> # v0.1.0
    secrets:
      RELEASE_PLEASE_APP_CLIENT_ID: ${{ secrets.RELEASE_PLEASE_APP_CLIENT_ID }}
      RELEASE_PLEASE_APP_PEM: ${{ secrets.RELEASE_PLEASE_APP_PEM }}
```

## The release App

release-please needs a token whose pushes start workflows, which the workflow's own token's do not, so it runs with a GitHub App installed on the organization:

1. In the organization's settings, under Developer settings, create a GitHub App. Repository permissions: Contents read and write, Pull requests read and write, Workflows read and write, Metadata read; no organization or account permissions.
2. Install the App on the repositories that release.
3. Store the App's client id as the organization secret `RELEASE_PLEASE_APP_CLIENT_ID` and a private key generated for it as `RELEASE_PLEASE_APP_PEM`. The key is stored nowhere else; a compromised key is rotated in the App's settings and the secret replaced.

## Releases of this repository

This repository releases with release-please too ([`release-please-config.json`](release-please-config.json), a single component tagged `vX.Y.Z`). A merge to `master` whose title is a releasable type opens or updates the release pull request; merging that cuts the tag and the GitHub release. A caller moves its pin to the new tag's commit.

## Contributing

A change to a workflow here changes every caller's checks, so a pull request states what it changes and why, its title follows Conventional Commits, and the repository's own CI (actionlint over every workflow file, and the semantic-title check) must pass. Every action a workflow uses is pinned by commit, with the release in a comment. A new workflow is reusable (`workflow_call`), documents its inputs, secrets and outputs in the file's header, and is added to this README.

## License

See [LICENSE](LICENSE).

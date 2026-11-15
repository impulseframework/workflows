# Changelog

## [0.1.1](https://github.com/impulseframework/workflows/compare/v0.1.0...v0.1.1) (2026-11-15)


### Features

* the Go workflow compiles and saves the caches on a push to the base branch without running a test (warm-caches-on-base-branch), and leaves a draft pull request's tests to the ready one (tests-on-draft) ([#4](https://github.com/impulseframework/workflows/issues/4)) ([07bf091](https://github.com/impulseframework/workflows/commit/07bf09140ead2613a2f4329f1619d47086cf1818))
* the Go workflow treats a change that touches only what a release writes as changing no module (skip-release-only-changes), so a release pull request's Go jobs report success without running ([#4](https://github.com/impulseframework/workflows/issues/4)) ([07bf091](https://github.com/impulseframework/workflows/commit/07bf09140ead2613a2f4329f1619d47086cf1818))
* the Go workflow's lint job takes a runner of its own (runs-on-lint) ([#4](https://github.com/impulseframework/workflows/issues/4)) ([07bf091](https://github.com/impulseframework/workflows/commit/07bf09140ead2613a2f4329f1619d47086cf1818))


### Bug Fixes

* the Go workflow's test and lint jobs report each build tag's check when they have nothing to do, where a job skipped whole reported one check for all of them ([#4](https://github.com/impulseframework/workflows/issues/4)) ([07bf091](https://github.com/impulseframework/workflows/commit/07bf09140ead2613a2f4329f1619d47086cf1818))

## 0.1.0 (2026-11-09)


### Features

* the reusable GitHub Actions workflows of the Impulse Framework organization ([#1](https://github.com/impulseframework/workflows/issues/1)) ([9643193](https://github.com/impulseframework/workflows/commit/964319322584bbe62b0cb572d69e0f8b92462eb2))

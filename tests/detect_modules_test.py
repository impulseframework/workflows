#!/usr/bin/env python3
"""Runs golang-ci.yml's detect-modules step over small repositories made for the purpose.

The step decides which modules a change touches and what the test job does with them, and
every other job of the workflow acts on its answer: a wrong one lets a change through
unchecked in every repository that calls the workflow. This test takes the step's script
out of the workflow file, runs it as GitHub runs a step that names no shell (bash -e, the
step's environment), and holds its outputs to a table of cases: a release's own diff, a diff that only looks like
one, a draft, a push to the base branch.

Run it from the repository's root: python3 tests/detect_modules_test.py
"""

import json
import os
import subprocess
import sys
import tempfile

WORKFLOW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".github", "workflows", "golang-ci.yml")


def block(lines, start):
    """The block scalar that follows lines[start] ("key: |"), without its indentation."""
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = []
    for line in lines[start + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    width = min(len(line) - len(line.lstrip()) for line in body if line.strip())

    return "".join(line[width:] if line.strip() else "\n" for line in body)


def step():
    """The detect-modules step's script and the jq program its environment carries."""
    with open(WORKFLOW, encoding="utf-8") as f:
        lines = f.readlines()
    at = next(i for i, line in enumerate(lines) if line.strip() == "- id: set-modules")
    program = next(i for i in range(at, len(lines)) if lines[i].strip() == "RELEASE_FILES: |")
    run = next(i for i in range(at, len(lines)) if lines[i].strip() == "run: |")

    return block(lines, run), block(lines, program)


SCRIPT, RELEASE_FILES = step()

# One package at the root with two json extra files, the shape of a Go module that releases
# browser packages beside it.
ROOT_CONFIG = {
    "packages": {
        ".": {
            "extra-files": [
                {"type": "json", "path": "web/kit/package.json", "jsonpath": "$.version"},
                {"type": "json", "path": "web/kit/package.json", "jsonpath": "$.peerDependencies['@acme/core']"},
                {"type": "json", "path": "web/core/package.json", "jsonpath": "$.version"},
                {"type": "json", "path": "web/deep/package.json", "jsonpath": "$..version"},
                {"type": "generic", "path": "version.txt"},
                {"type": "json", "path": "web/both/package.json", "jsonpath": "$.version"},
                {"type": "generic", "path": "web/both/package.json"},
                {"type": "json", "path": "web/twice/package.json", "jsonpath": "$.version"},
                "web/twice/package.json",
                {"type": "json", "path": "/root.json", "jsonpath": '$["version"]'},
                "plain.txt",
            ]
        }
    }
}
PACKAGE = {"name": "@acme/kit", "version": "1.0.0", "peerDependencies": {"@acme/core": "1.0.0", "other": "^2.0.0"}, "scripts": {"build": "x"}}
ROOT_BASE = {
    "release-please-config.json": json.dumps(ROOT_CONFIG),
    ".release-please-manifest.json": '{".": "1.0.0"}\n',
    "CHANGELOG.md": "# Changelog\n",
    "go.mod": "module example.com/m\n",
    "main.go": "package main\n",
    "web/kit/package.json": json.dumps(PACKAGE, indent=2),
    "web/core/package.json": json.dumps({"name": "@acme/core", "version": "1.0.0"}, indent=2),
    "web/deep/package.json": json.dumps({"name": "deep", "version": "1.0.0"}, indent=2),
    "web/both/package.json": json.dumps({"name": "both", "version": "1.0.0"}, indent=2),
    "web/twice/package.json": json.dumps({"name": "twice", "version": "1.0.0"}, indent=2),
    "root.json": json.dumps({"version": "1.0.0", "kept": True}),
    "version.txt": "1.0.0\n",
    "plain.txt": "1.0.0\n",
}


def kit(**changes):
    """The kit's package.json with the given top-level changes."""
    return json.dumps({**PACKAGE, **changes}, indent=2)


RELEASED_KIT = kit(version="1.1.0", peerDependencies={"@acme/core": "1.1.0", "other": "^2.0.0"})
RELEASE = {
    "CHANGELOG.md": "# Changelog\n\n## 1.1.0\n",
    ".release-please-manifest.json": '{".": "1.1.0"}\n',
    "web/kit/package.json": RELEASED_KIT,
    "web/core/package.json": json.dumps({"name": "@acme/core", "version": "1.1.0"}, indent=2),
    "root.json": json.dumps({"version": "1.1.0", "kept": True}),
}

# Two modules, each a package of the release configuration.
TWO_CONFIG = {"changelog-path": "docs/CHANGES.md", "packages": {"a": {}, "b": {"changelog-path": "HISTORY.md"}}}
TWO_BASE = {
    "release-please-config.json": json.dumps(TWO_CONFIG),
    ".release-please-manifest.json": "{}\n",
    "a/go.mod": "module example.com/a\n",
    "a/docs/CHANGES.md": "a\n",
    "a/CHANGELOG.md": "not the changelog\n",
    "b/go.mod": "module example.com/b\n",
    "b/HISTORY.md": "b\n",
    "b/b.go": "package b\n",
}

SKIP = {"SKIP_RELEASE_ONLY": "true"}
PULL_REQUEST = {"EVENT": "pull_request", "PR_BASE": "master", "REF_NAME": "7/merge"}
DRAFT = {**PULL_REQUEST, "DRAFT": "true"}
BASE_PUSH = {"EVENT": "push", "PR_BASE": "", "REF_NAME": "master"}

# name, the base tree, the change (a path set to None is deleted), the environment over a
# pull request's, and the outputs wanted.
CASES = [
    # The workflow as every caller had it: each new input at its default.
    ("defaults: a Go file", ROOT_BASE, {"main.go": "package main // x\n"}, {}, {"any": "true", "tests": "run", "warm": "false", "changed": "."}),
    ("defaults: a release's diff is a change like any other", ROOT_BASE, RELEASE, {}, {"any": "true", "tests": "run", "changed": "."}),
    ("defaults: a draft runs the tests", ROOT_BASE, {"main.go": "package main // x\n"}, DRAFT, {"tests": "run"}),
    ("defaults: a push to the base branch runs the tests of every module", TWO_BASE, {}, BASE_PUSH, {"any": "true", "tests": "run", "warm": "false", "changed": "a b"}),
    # A release's own diff.
    ("release: the changelog, the manifest and the declared values", ROOT_BASE, RELEASE, SKIP, {"any": "false", "tests": "skip", "changed": "", "first": ""}),
    ("release: the same values with the file written in another layout", ROOT_BASE, {"web/kit/package.json": json.dumps(json.loads(RELEASED_KIT), indent=4, sort_keys=True)}, SKIP, {"any": "false"}),
    ("release: a diff that changes nothing at all", ROOT_BASE, {}, SKIP, {"any": "false", "tests": "skip"}),
    # A diff that only looks like one.
    ("not a release: another value of an extra file", ROOT_BASE, {**RELEASE, "web/kit/package.json": kit(version="1.1.0", scripts={"build": "y"})}, SKIP, {"any": "true", "tests": "run", "changed": "."}),
    ("not a release: another key of the object a declared value sits in", ROOT_BASE, {"web/kit/package.json": kit(peerDependencies={"@acme/core": "1.1.0", "other": "^3.0.0"})}, SKIP, {"any": "true"}),
    ("not a release: a new key in an extra file", ROOT_BASE, {"web/kit/package.json": kit(version="1.1.0", added=1)}, SKIP, {"any": "true"}),
    ("not a release: a Go file beside the release's files", ROOT_BASE, {**RELEASE, "main.go": "package main // x\n"}, SKIP, {"any": "true", "changed": "."}),
    ("not a release: an extra file of another type", ROOT_BASE, {"version.txt": "1.1.0\n"}, SKIP, {"any": "true"}),
    ("not a release: an extra file named by its path alone", ROOT_BASE, {"plain.txt": "1.1.0\n"}, SKIP, {"any": "true"}),
    ("not a release: a JSON path outside the plain form", ROOT_BASE, {"web/deep/package.json": json.dumps({"name": "deep", "version": "1.1.0"}, indent=2)}, SKIP, {"any": "true"}),
    ("not a release: a file the configuration also names in another way", ROOT_BASE, {"web/both/package.json": json.dumps({"name": "both", "version": "1.1.0"}, indent=2)}, SKIP, {"any": "true"}),
    ("not a release: a file the configuration also names by its path alone", ROOT_BASE, {"web/twice/package.json": json.dumps({"name": "twice", "version": "1.1.0"}, indent=2)}, SKIP, {"any": "true"}),
    ("not a release: an extra file the base does not hold", {k: v for k, v in ROOT_BASE.items() if k != "web/core/package.json"}, {"web/core/package.json": json.dumps({"version": "1.1.0"})}, SKIP, {"any": "true"}),
    ("not a release: an extra file deleted", ROOT_BASE, {"web/core/package.json": None}, SKIP, {"any": "true"}),
    ("not a release: an extra file that is no JSON", ROOT_BASE, {"web/core/package.json": '{"version": "1.1.0"'}, SKIP, {"any": "true"}),
    ("not a release: a file of the manifest's name in another directory", ROOT_BASE, {"web/.release-please-manifest.json": "{}\n"}, SKIP, {"any": "true"}),
    # Several modules, and the configuration's own changelog paths.
    ("modules: each package's changelog where the configuration puts it", TWO_BASE, {"a/docs/CHANGES.md": "a2\n", "b/HISTORY.md": "b2\n", ".release-please-manifest.json": '{"a": "1.0.0"}\n'}, SKIP, {"any": "false"}),
    ("modules: a file of the default changelog's name is a change where the path is another", TWO_BASE, {"a/CHANGELOG.md": "x\n", "b/HISTORY.md": "b2\n"}, SKIP, {"any": "true", "changed": "a", "first": "a"}),
    ("modules: one module's release beside another module's code", TWO_BASE, {"a/docs/CHANGES.md": "a2\n", "b/b.go": "package b // x\n"}, SKIP, {"any": "true", "changed": "b"}),
    ("modules: under a working directory", {"sub/" + k if k not in ("release-please-config.json", ".release-please-manifest.json") else k: v for k, v in ROOT_BASE.items()}, {"sub/" + k if k != ".release-please-manifest.json" else k: v for k, v in RELEASE.items() if k != "root.json"}, {**SKIP, "WORKING_DIR": "sub"}, {"any": "false"}),
    ("no release configuration: every file is a change", {"go.mod": "module example.com/m\n", "CHANGELOG.md": "x\n"}, {"CHANGELOG.md": "y\n"}, SKIP, {"any": "true", "changed": "."}),
    # A draft.
    ("draft: the tests wait for the pull request to be ready", ROOT_BASE, {"main.go": "package main // x\n"}, {**DRAFT, "TESTS_ON_DRAFT": "false"}, {"any": "true", "tests": "skip", "warm": "false", "changed": "."}),
    ("draft: a ready pull request runs them", ROOT_BASE, {"main.go": "package main // x\n"}, {**PULL_REQUEST, "DRAFT": "false", "TESTS_ON_DRAFT": "false"}, {"tests": "run"}),
    ("draft: a push, which has no draft state, runs them", ROOT_BASE, {"main.go": "package main // x\n"}, {"EVENT": "push", "PR_BASE": "", "REF_NAME": "topic", "DRAFT": "", "TESTS_ON_DRAFT": "false"}, {"tests": "run"}),
    # The base branch's warm-up.
    ("warm-up: a push to the base branch compiles every module", TWO_BASE, {}, {**BASE_PUSH, "WARM_ON_BASE": "true"}, {"any": "true", "tests": "compile", "warm": "true", "changed": "a b"}),
    ("warm-up: a pull request runs the tests", TWO_BASE, {"b/b.go": "package b // x\n"}, {"WARM_ON_BASE": "true"}, {"tests": "run", "warm": "false", "changed": "b"}),
    ("warm-up: a push to another branch runs the tests", TWO_BASE, {"b/b.go": "package b // x\n"}, {"EVENT": "push", "PR_BASE": "", "REF_NAME": "topic", "WARM_ON_BASE": "true"}, {"tests": "run", "warm": "false", "changed": "b"}),
    ("warm-up: the base branch named by the input", TWO_BASE, {}, {"EVENT": "push", "PR_BASE": "", "REF_NAME": "release", "BASE_INPUT": "release", "WARM_ON_BASE": "true"}, {"tests": "compile", "warm": "true"}),
]


def git(repo, *args):
    subprocess.run(["git", "-C", repo, "-c", "user.name=test", "-c", "user.email=test@example.com", *args], check=True, capture_output=True)


def write(repo, tree):
    for path, content in tree.items():
        full = os.path.join(repo, path)
        if content is None:
            os.remove(full)
            continue
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


def run(base, change, env):
    """The step's outputs for the change over the base tree, and what it printed."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = os.path.join(tmp, "repo")
        os.makedirs(repo)
        git(repo, "init", "-q", "-b", "work")
        write(repo, base)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", "base")
        for branch in ("master", "release"):
            git(repo, "update-ref", "refs/remotes/origin/" + branch, "HEAD")
        write(repo, change)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", "change")
        outputs = os.path.join(tmp, "outputs")
        open(outputs, "w", encoding="utf-8").close()
        step_env = {
            "PATH": os.environ["PATH"],
            "HOME": tmp,
            "RUNNER_TEMP": tmp,
            "GITHUB_OUTPUT": outputs,
            "CONFIG": "release-please-config.json",
            "WORKING_DIR": ".",
            "BASE_INPUT": "",
            "DEFAULT_BRANCH": "master",
            "DRAFT": "",
            "TESTS_ON_DRAFT": "true",
            "WARM_ON_BASE": "false",
            "SKIP_RELEASE_ONLY": "false",
            "MANIFEST": ".release-please-manifest.json",
            "RELEASE_FILES": RELEASE_FILES,
            **PULL_REQUEST,
            **env,
        }
        done = subprocess.run(["bash", "-e", "-c", SCRIPT], cwd=repo, env=step_env, capture_output=True, text=True, check=False)
        with open(outputs, encoding="utf-8") as f:
            got = dict(line.rstrip("\n").split("=", 1) for line in f if "=" in line)

        return done.returncode, got, done.stdout + done.stderr


def main():
    failed = 0
    for name, base, change, env, want in CASES:
        code, got, log = run(base, change, env)
        wrong = {key: (got.get(key), value) for key, value in want.items() if got.get(key) != value}
        if code != 0 or wrong:
            failed += 1
            print(f"FAIL  {name}")
            if code != 0:
                print(f"      the step exited {code}")
            for key, (have, wanted) in wrong.items():
                print(f"      {key} = {have!r}, want {wanted!r}")
            print("      " + log.strip().replace("\n", "\n      "))
        else:
            print(f"ok    {name}")
    # A base that does not exist fails the step, so the required check fails with it.
    code, _, _ = run(ROOT_BASE, {"main.go": "package main // x\n"}, {"PR_BASE": "gone"})
    if code == 0:
        failed += 1
        print("FAIL  a base branch that does not exist: the step passed")
    else:
        print("ok    a base branch that does not exist fails the step")
    print(f"\n{len(CASES) + 1 - failed} of {len(CASES) + 1} passed")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

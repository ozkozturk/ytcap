# Release Guide

This document describes the packaging, testing, and publishing process for
`ytcap`.

The `0.1.0` release was published manually with `twine`. Future releases should
use GitHub Releases, GitHub Actions, and PyPI/TestPyPI Trusted Publishing.

## 1. Publishing Target

Recommended user installation:

```bash
pipx install ytcap
```

Alternative:

```bash
python -m pip install ytcap
```

For CLI applications, `pipx` is the recommended user installation path.

## 2. Packaging Approach

The project uses modern Python packaging:

- `pyproject.toml`
- `src/` layout
- Wheel and sdist builds
- Console script entry point

Entry point:

```text
ytcap
```

Users should be able to run:

```bash
ytcap --help
```

## 3. Versioning

The project follows semantic versioning.

Suggested path:

| Version | Meaning |
|---|---|
| `0.1.0` | Initial public release |
| `0.1.x` | Patch fixes and release automation hardening |
| `0.2.0` | Backward-compatible feature additions |
| `1.0.0` | Stable CLI and JSON/JSONL schema |

Rules:

| Change | Version impact |
|---|---|
| Bug fix | Patch |
| New backward-compatible feature | Minor |
| Backward-incompatible CLI or JSON change | Major, or explicit note during the `0.x` period |

## 4. Trusted Publishing Setup

Trusted Publishing must be configured once on both PyPI and TestPyPI before the
automated release workflow can upload packages without API tokens.

Use these publisher settings for the existing `ytcap` project on PyPI:

| Field | Value |
|---|---|
| Owner | `ozkozturk` |
| Repository name | `ytcap` |
| Workflow filename | `release.yml` |
| Environment name | `pypi` |

Use these publisher settings for the existing `ytcap` project on TestPyPI:

| Field | Value |
|---|---|
| Owner | `ozkozturk` |
| Repository name | `ytcap` |
| Workflow filename | `release.yml` |
| Environment name | `testpypi` |

PyPI/TestPyPI account API tokens are not needed for this workflow once the
publishers are configured. Revoke any broad account-level tokens that were used
for manual publishing.

GitHub repository environments named `pypi` and `testpypi` should exist. Add
environment protection rules if a manual approval gate is desired before
publishing to PyPI.

## 5. GitHub Actions Workflows

The repository has two workflow files:

| File | Purpose |
|---|---|
| `.github/workflows/ci.yml` | Runs tests on supported Python versions and verifies package build metadata |
| `.github/workflows/release.yml` | Builds release artifacts and publishes with Trusted Publishing |

The release workflow:

- Runs unit tests on Python 3.11, 3.12, and 3.13.
- Builds the sdist and wheel once.
- Checks package metadata with `twine check`.
- Uploads the built distributions as a GitHub Actions artifact.
- Publishes to TestPyPI for manual workflow runs and GitHub Releases.
- Publishes to PyPI only for non-prerelease GitHub Releases.
- Grants `id-token: write` only to the TestPyPI/PyPI publish jobs.

## 6. Local Pre-Release Checklist

Before creating a public release:

```md
- [ ] Version updated in `src/ytcap/__init__.py`.
- [ ] `CHANGELOG.md` updated.
- [ ] `README.md` is current.
- [ ] `CLI_REFERENCE.md` is current.
- [ ] `OUTPUT_FORMAT.md` is current.
- [ ] `USAGE.md` is current.
- [ ] Unit tests pass.
- [ ] Package build and metadata checks pass.
```

Recommended local commands:

```bash
python -m pip install -e '.[dev]'
python -m unittest discover -s tests
python -m build
python -m twine check dist/*
```

## 7. TestPyPI Stage

For a TestPyPI-only smoke run, use the GitHub Actions UI:

1. Open the `Release` workflow.
2. Choose `Run workflow`.
3. Run it from the branch or tag to test.
4. Keep the target as `testpypi`.

The workflow uses TestPyPI Trusted Publishing and does not need a
`TEST_PYPI_API_TOKEN` secret. The TestPyPI publish step uses `skip-existing` so
reruns of the same test version do not fail only because the files already
exist.

## 8. Public Release

For each public release:

1. Update the package version.
2. Update release notes in `CHANGELOG.md`.
3. Run the local pre-release checklist.
4. Commit and push the changes.
5. Create and push a matching Git tag such as `v0.1.1`.
6. Create a GitHub Release from that tag.

When the GitHub Release is published:

- Prerelease GitHub Releases publish only to TestPyPI.
- Stable GitHub Releases publish to TestPyPI first, then PyPI.
- The release tag must match the package version, for example `v0.1.1` for
  `__version__ = "0.1.1"`.

## 9. Post-Release Verification

After release, verify:

```bash
pipx install ytcap
ytcap --help
ytcap --version
```

Also check:

- PyPI project page: <https://pypi.org/project/ytcap/>
- GitHub Release page: <https://github.com/ozkozturk/ytcap/releases>
- The `Release` GitHub Actions workflow run completed successfully.

## 10. Yank or Problem Release

If a release has a serious problem:

1. Document the issue in `CHANGELOG.md` or a GitHub issue.
2. Prepare a patch release if possible.
3. Provide a user workaround.
4. Update public documentation if the issue affects CLI behavior or output schema.

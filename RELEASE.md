# Release Guide

This document describes the target packaging, testing, and publishing process for `ytcap`.

## 1. Publishing Target

Target user installation:

```bash
pipx install ytcap
```

Alternative:

```bash
pip install ytcap
```

For CLI applications, `pipx` is the recommended user installation path.

## 2. Packaging Approach

The project should use modern Python packaging:

- `pyproject.toml`
- `src/` layout
- Wheel and sdist builds
- Console script entry point

Target entry point:

```text
ytcap
```

Users should be able to run:

```bash
ytcap --help
```

## 3. Versioning

The project should follow semantic versioning.

Suggested path:

| Version | Meaning |
|---|---|
| `0.1.0` | Single-video MVP |
| `0.2.0` | Export improvements |
| `0.3.0` | Batch support |
| `0.4.0` | Playlist support |
| `1.0.0` | Stable CLI and JSON schema |

Rules:

| Change | Version impact |
|---|---|
| Bug fix | Patch |
| New backward-compatible feature | Minor |
| Backward-incompatible CLI or JSON change | Major, or explicit note during the `0.x` period |

## 4. Pre-Release Checklist

```md
- [ ] All tests passed.
- [ ] `ytcap --help` works.
- [ ] `ytcap --version` reports the correct version.
- [ ] `README.md` is current.
- [ ] `CHANGELOG.md` is current.
- [ ] `CLI_REFERENCE.md` is current.
- [ ] `OUTPUT_FORMAT.md` is current.
- [ ] `USAGE.md` is current.
- [ ] Installation was tested in a clean environment.
- [ ] Build artifacts were produced.
```

## 5. Local Build Target

Expected release build output:

```text
dist/
  ytcap-x.y.z.tar.gz
  ytcap-x.y.z-py3-none-any.whl
```

Build tools may be needed as development dependencies. New dependencies should still be justified and approved before being added.

## 6. TestPyPI Stage

TestPyPI should be used before publishing to the real PyPI index.

Goals:

- Confirm package metadata is correct.
- Confirm the wheel installs.
- Confirm the entry point works.
- Confirm the README renders correctly on PyPI.

Minimum smoke test after test installation:

```bash
ytcap --help
```

```bash
ytcap --version
```

## 7. PyPI Publishing

The long-term recommended publishing method is:

```text
GitHub Actions + Trusted Publishing
```

Manual publishing may be used early on, but token security must be handled carefully.

## 8. GitHub Release

For each public release:

- Create a Git tag such as `v0.1.0`.
- Create a GitHub Release.
- Use the relevant `CHANGELOG.md` section as release notes.
- Clearly call out important breaking changes.

## 9. Post-Release Verification

After release, verify these commands in a clean environment:

```bash
pipx install ytcap
```

```bash
ytcap --help
```

```bash
ytcap --version
```

## 10. Yank or Problem Release

If a release has a serious problem:

1. Document the issue in `CHANGELOG.md` or a GitHub issue.
2. Prepare a patch release if possible.
3. Provide a user workaround.
4. Update public documentation if the issue affects CLI behavior or output schema.

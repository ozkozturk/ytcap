# Contributing

Thanks for helping improve `ytcap`. This project aims to move in small, testable changes with public documentation kept in sync.

## 1. Before You Start

Please read the relevant public documentation first:

1. `README.md`
2. `CLI_REFERENCE.md`
3. `OUTPUT_FORMAT.md`
4. `USAGE.md`
5. `SECURITY.md`

## 2. Contribution Scope

Pull requests should clearly explain the user-facing problem, behavior change, or maintenance improvement they address.

Keep changes focused. Avoid mixing unrelated refactors, formatting churn, dependency changes, and feature work in the same pull request.

## 3. Test Expectations

Every code change should include tests or a clear explanation of why tests are not applicable.

Default test command:

```bash
python -m unittest discover -s tests
```

Unit tests must not make real YouTube or network calls. Use synthetic fixtures and mocked extractor responses instead.

## 4. Dependency Changes

`yt-dlp` is the core runtime extractor dependency.

Do not add new runtime or development dependencies without a clear justification and maintainer approval. A dependency proposal should explain:

- What problem the dependency solves.
- Why the standard library or existing dependencies are not enough.
- Whether the dependency is runtime-only, development-only, or optional.
- Any licensing, security, or maintenance concerns.

## 5. Documentation

When user-facing behavior changes, update `README.md` and the relevant public docs.

If CLI behavior changes, review:

- `README.md`
- `CLI_REFERENCE.md`
- `USAGE.md`

If JSON or JSONL output changes, review:

- `OUTPUT_FORMAT.md`
- Relevant test fixtures
- `CHANGELOG.md`

## 6. Pull Request Checklist

```md
- [ ] The change is focused and explained.
- [ ] Tests were added or updated.
- [ ] Tests were run.
- [ ] User-facing documentation was updated or explicitly checked.
- [ ] Dependency impact was documented.
- [ ] No official YouTube Data API integration was added.
- [ ] No real secrets, cookies, or non-public user data were added.
```

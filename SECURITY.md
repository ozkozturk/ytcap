# Security Policy

## 1. Supported Versions

This project is still in an early stage. There is no officially supported version until a public release exists.

## 2. Sensitive Data Policy

Do not commit the following information to the repository:

- API keys
- OAuth tokens
- Cookie or session files
- Personal video lists
- Non-public URLs
- Large real transcript archives
- Extensive copied content that may create copyright risk

## 3. No Official YouTube API Usage

This project does not use the official YouTube Data API. It should not require API keys or OAuth secrets.

If a change requires API keys, OAuth tokens, or cookies, it must receive explicit maintainer approval before implementation.

## 4. Reporting a Security Issue

If you discover a security issue:

1. Explain what the issue is.
2. Identify which files or behavior it affects.
3. Provide reproduction steps.
4. Do not include sensitive information in a public issue.

## 5. Safe Test Data

Test fixtures should be synthetic.

Do not add test files containing data from real users, non-public videos, or large copyrighted transcripts.

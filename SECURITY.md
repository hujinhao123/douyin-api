# Security

- Never commit cookies, session files, browser profiles, QR images, tokens, `.env`, or private keys.
- `DOUYIN_ALLOW_LAN=true` requires `DOUYIN_API_TOKEN` with at least 32 characters.
- All business endpoints require `Authorization: Bearer <token>`.
- `/auth/session/import` is loopback-only.
- Do not expose port 8787 directly to the public internet; use an HTTPS reverse proxy.
- Back up `session.bin` and `master.key` together, but never put either in Git or a public artifact.
- Treat the API as sensitive account access. Rotate the API Token if it may have leaked.
- Report security issues privately to the repository owner; do not open a public issue containing credentials, cookies, session material, or account data.

## Public repository checklist

Before publishing or accepting a contribution:

1. Search the complete Git history, not only the working tree, for tokens, cookies and private keys.
2. Confirm `data/`, `.env`, browser profiles, evidence images and live fixtures are ignored.
3. Run the test suite and a secret scan.
4. Keep deployment examples on placeholders and never include a real account or LAN address.

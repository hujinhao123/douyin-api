# Security

This repository is private by default.

- Never commit cookies, session files, browser profiles, QR images, tokens, or `.env`.
- `DOUYIN_ALLOW_LAN=true` requires `DOUYIN_API_TOKEN` with at least 32 characters.
- All business endpoints require `Authorization: Bearer <token>`.
- `/auth/session/import` is loopback-only.
- Do not expose port 8787 directly to the public internet; use an HTTPS reverse proxy.
- Report security issues privately to the repository owner.

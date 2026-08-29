# 0010: Managed accounts and login rate limits

## Status

Accepted on 2026-08-29.

## Decision

Deployment credentials seed only the first administrator. Authenticated
administrators create later student, teacher, and administrator accounts through
the same API and Web workspace. Public registration stays disabled. Passwords
are stored with Argon2 and new managed accounts require at least 15 characters.

Use the maintained open-source `limits` library rather than a project-specific
rate-limit algorithm. Login attempts consume independent buckets for normalized
account identity and client IP. Five attempts per account and twenty per IP are
allowed in fifteen minutes. Exceeded requests return HTTP 429 and Retry-After.
A successful login resets the account bucket but not the IP bucket.

The current one-worker deployment uses the library's memory backend. A future
multi-worker deployment must select a shared supported backend, normally Redis,
through `OME_LOGIN_RATE_LIMIT_STORAGE_URI`.

## References

- OWASP Authentication Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- NIST SP 800-63B, rate limiting and password guidance:
  https://pages.nist.gov/800-63-4/sp800-63b.html
- `limits` documentation and storage backends:
  https://limits.readthedocs.io/en/stable/

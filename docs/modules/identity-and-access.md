# Identity and Access

## Responsibility

The identity module owns users, credentials, roles, sessions, bootstrap
administration, and authorization policies. It does not own catalog or learning
records.

## Roles

- Student: access published catalog and personal learning state.
- Teacher: student permissions plus teaching workflows added by requirements.
- Administrator: account administration, pipeline control, corrections,
  releases, and audit access.

## Browser session

The browser uses a Secure, HttpOnly, SameSite cookie. Mutating requests use CSRF
protection. Sessions are revocable server records. Passwords use Argon2. Public
registration is disabled.

## API boundary

Identity endpoints expose authentication and the current principal. Other
modules receive an authorized principal or policy decision rather than reading
identity persistence directly.

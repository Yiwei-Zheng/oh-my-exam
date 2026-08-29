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

The deployment bootstrap creates only the first trusted administrator. After
sign-in, an administrator creates additional students, teachers, or
administrators from the user manager. Public registration remains disabled.
New managed accounts require passwords of at least 15 characters.

## Browser session

The browser uses a signed JWT in an HttpOnly, SameSite cookie; production also
sets Secure. Passwords use Argon2 and plaintext is never stored. A local secret
file is created automatically for development; production supplies the secret
through its protected service environment.

Login attempts have independent account and client-IP fixed-window limits using
the open-source `limits` library. The documented single-worker deployment uses
process-local storage. Multiple API workers must use a shared backend supported
by `limits`, normally Redis. Failure messages do not reveal whether an account
exists, and missing accounts still perform an Argon2 verification to reduce
timing differences.

## API boundary

Identity endpoints expose authentication and the current principal. Other
modules receive an authorized principal or policy decision rather than reading
identity persistence directly.

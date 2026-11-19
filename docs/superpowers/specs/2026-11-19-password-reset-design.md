# Password reset and clear sign-in errors: design

Date: 2026-11-19. Status: approved by the owner in conversation ("do the
real fix"). Size: a small change.

## Why

A tester typed a wrong password and saw "Wrong e-mail or password". That
was true, but the same message is shown for every failure, including
Supabase limiting attempts or being unreachable. And a student who forgets
their password has no way back: the app has no reset. With 20 to 30
students, both will happen.

## Decisions

**Sign-in errors.** `auth.sign_in` returns tokens or a reason, read from
Supabase's error code:

| Reason | Supabase | Message |
|---|---|---|
| `credentials` | `invalid_credentials` | Wrong e-mail or password. |
| `unconfirmed` | `email_not_confirmed` | Confirm your e-mail address first: open the link we sent you. |
| `busy` | status 429 | Too many sign-ins right now. Try again in a few minutes. |
| `unavailable` | anything else | Sign-in is not working right now. Try again in a moment. |

**Forgot password.** A link "Forgot your password?" on the sign-in page
leads to `/forgot-password`: one e-mail field. The answer is always the
same, whether an account exists or not: "If an account uses this address,
we sent a link to choose a new password." The server calls Supabase
`reset_password_for_email`. Attempts are limited like sign-in (10 in
15 minutes per computer and per e-mail from one computer).

**Reset.** The e-mail links to `/reset-password?token_hash=...`. The GET
only shows a form (new password, twice) with the token hidden; the token is
used on the POST, so a mail scanner that opens links cannot spend it. The
server calls `verify_otp(type="recovery")`, sets the new password with
`update_user` on that session, then signs it out everywhere. On success:
the sign-in page with "Your password is changed. Sign in with the new one."
Errors: passwords differ or shorter than 8 characters (the form stays); a
used or expired link ("This link has expired.", with a link to ask for a new one).

**Owner, in Supabase (once):** Authentication, Emails, template "Reset
Password": the link becomes
`{{ .SiteURL }}/reset-password?token_hash={{ .TokenHash }}`; and the Site
URL is `https://kaltstart.onrender.com`.

Rejected: Supabase's default link with tokens in the URL fragment (the
server never sees a fragment; it would need a script and puts tokens in the
browser history); verifying the token on GET (mail scanners would spend it).

## Not in scope

Changing the password from the profile while signed in; e-mail change.

## Tests

- Each Supabase error maps to its reason and message (fake auth).
- `/forgot-password` gives the same answer for a known and an unknown
  address, needs the CSRF token, and is rate limited.
- `/reset-password` GET does not spend the token; POST with a good token
  changes the password (sign-in works with the new one, not the old one);
  a spent token is refused; mismatched or short passwords keep the form.
- The sign-in page links to `/forgot-password`.

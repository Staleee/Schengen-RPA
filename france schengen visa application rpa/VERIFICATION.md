# How we handle email verification

France-Visas sends a verification email when you register. Here’s how the RPA deals with it in each flow.

---

## 1. POST /register-and-verify (full flow: register → verify → login)

We **do not bypass** verification. We **automate** it using your mailbox.

- You send in the request body:
  - Your **email** and **password** (for the France-Visas account)
  - **IMAP** settings so we can read that same mailbox: `email_password` (e.g. Gmail App Password), `imap_server` (e.g. `imap.gmail.com`), `imap_port`, `imap_use_ssl`
- The RPA:
  1. Registers on France-Visas (fills form, solves CAPTCHA, submits).
  2. France-Visas sends a verification email to your address (from `noreply@interieur.gouv.fr`).
  3. The RPA **connects to your mailbox via IMAP**, polls for that email, and extracts:
     - The **verification link** (or)
     - A **verification code** (if the email contains one).
  4. It then **opens the link in the browser** (or enters the code on the verification page).
  5. After that it completes login (or you’re already logged in from the link).

So we “surpass” only in the sense that **you don’t have to open your email yourself** – we read it via IMAP and click the link (or enter the code) for you. You must provide valid IMAP credentials (e.g. Gmail App Password) for the email address you use to register.

---

## 2. POST /fill-application/full (fill form only)

There is **no registration and no verification** in this flow.

- We assume you **already have an account** and have **already verified your email** (e.g. when you first registered, or via `/register-and-verify`).
- You **log in manually** in the browser during `wait_for_manual_login_seconds`.
- The RPA only fills the visa application form; it does not read or send any email.

So we “surpass” the email verification **only because we skip registration** – we never trigger a new verification email; we just use an existing logged-in session.

---

## Summary

| Flow                     | Email verification handled? | How |
|--------------------------|-----------------------------|-----|
| **register-and-verify**  | Yes, automated              | IMAP: we read your mailbox, find the France-Visas email, extract link/code, open link or enter code in the browser. |
| **fill-application/full** | N/A                         | No verification step; you log in manually; account must already be verified. |

For **register-and-verify** you must provide **IMAP access** (e.g. Gmail App Password and `imap_server`) so we can read the verification email and open the link.

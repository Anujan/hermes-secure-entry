# Security model

Enabling an in-process Hermes plugin trusts its Python code. Capability declarations are an audit/consent surface, not a sandbox.

## Boundaries

- Requests originate only from an authorized native Photon DM tool context. Model parameters are operation, exact website origin, or opaque request ID; never credentials, sender IDs, destinations, or browser injection code.
- The broker has no HTTP creation API. It stores at most 64 active/tombstone requests; random URL tokens and independent CSRF nonces each have 256 bits of entropy.
- Links are bearer capabilities. Anyone who obtains one and can reach the allowed tailnet endpoint can submit. Tailscale ACLs, trusted HTTPS config, and not forwarding links are operational requirements. The model sees the opaque URL, not the entered password. Do not publish real links or put them in shared logs.
- Browser Origin checks are not the only CSRF protection. Independent per-request nonce validation works with Safari/mobile/`Origin: null`; there is no CORS grant. Host validation rejects unrecognized names, but the loopback address is intentionally reachable by local programs.
- Native vault instance selection occurs in the originating tool context and captures its profile directory before serving the form. Existing saved passwords are never resolved by production plugin code. Redaction is registered before native storage.
- Request identity includes home, platform, DM type, chat, user, session key and ID. Tool status/cancel refuse another identity. Delivered core stop/reset/abnormal-end hooks cancel pending requests; normal completed-turn end does not. **Idle `/stop` does not reliably revoke a delivered link** because the host's no-active-agent path emits no stop hook. Use form **Cancel** or `secure_entry_cancel(request_id)` in the originating session. Admission is generation-fenced before owner/store acquisition and final issuance is serialized with invalidation. Any lifecycle invalidation conservatively refuses all in-flight admissions; already indexed requests are cancelled only for the matching owner. Unload permanently closes admission. A native commit and cancellation are serialized; once a native save started, cancellation cannot falsely promise it was prevented.
- Only native encrypted vault files persist passwords. The plugin does not copy vault keys, read `.env`/auth files, or maintain a secondary credential store. Native vault encryption is not protection against malware running as the same Windows user or theft of both encrypted file and its native key.
- Python strings cannot be reliably zeroized. Submitted data lives briefly in HTTP/native-call memory; the native redaction registry can retain matching values in process memory. Do not claim memory erasure guarantees.

## HTTP controls

Fixed IPv4 loopback bind; 16 KiB body cap; bounded fields; ten-second socket timeout; no transfer encoding; duplicate field rejection; no body/URL/access/error logging; `no-store`, no-referrer, nosniff, frame denial, restrictive CSP, no external assets or scripts, no telemetry. POST/redirect/GET avoids mobile resubmit. GET/link previews are non-consuming. Expiry is enforced on every lookup and submission, even for a form left open past its deadline. Request tables are process-memory only; restart invalidates every link.

The stdlib HTTP server is intentionally small, not an internet-facing hardened application stack. It has bounded request storage but no distributed rate limiting or per-tailnet-user identity verification. Never expose it to the public internet, Tailscale Funnel, or an untrusted LAN. Tailscale Serve must forward the dedicated HTTPS root unchanged and must not log full credential URLs/bodies.

## Current scope

This is a preview/testing-only partial implementation. Only standalone **add new login** is operational. A native write followed by failed metadata verification is `commit_unknown`, not proof of no write: returned handle/identifier metadata is retained when available, and the form directs inspection before retry. Exceptions inside native add are also conservatively unknown. No atomic update, transient sign-in, browser save-and-fill, or native OTP adapter is exposed. These operations fail closed before opening a form. No payment support, passkey emulation, auto-submit, arbitrary selector, generic secret resolution, or generic injection endpoint exists. The native tools and their approval/origin/supervisor fences remain untouched.

Report a vulnerability privately to the repository maintainer rather than posting live credentials, bearer links, vault files, or complete gateway logs. Revoke/cancel a suspect request immediately and coordinate service shutdown if necessary.

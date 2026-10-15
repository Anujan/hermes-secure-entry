# Hermes Secure Entry

A separate Windows-native Hermes plugin for private, one-use credential-entry pages reached through Tailscale Serve. It registers tools and lifecycle hooks through `PluginContext`; it does not modify Hermes core.

**Version 0.1.0 is a partial implementation for preview/testing only. It can ADD a website login to the native encrypted Hermes vault without a browser. It cannot yet update an existing item, sign in once without saving, save-and-sign-in, or apply a verification code to a strictly bound browser target. Those operations return `unsupported_native_contract` before collecting anything. Do not advertise this release as complete browser sign-in support.** See [native integration blockers](docs/native-contract.md).

## What works

- `secure_entry_request(operation="add_login", origin="https://example.com")` in an originating Photon **DM** creates a ten-minute, 256-bit bearer link. Return that link only in that conversation.
- The page explicitly names the exact website origin and says it will save a **new** native vault item, not sign in. The username is visible metadata; the password is not returned to the tool/model.
- On submission, the native `VaultStore.add_item` encrypts the login. The plugin reads back metadata only before reporting `saved`. If the native write outcome cannot be verified, `commit_unknown` preserves returned handle metadata when available: inspect the vault before retrying to avoid duplicates.
- `secure_entry_status(request_id)` and `secure_entry_cancel(request_id)` require the same home, platform, sender, chat, session key, and session ID. Delivered lifecycle stop/reset/abnormal-end hooks and plugin unload cancel pending entries; normal turn completion preserves the delivered link. **Idle `/stop` does not reliably revoke a delivered link**: the host emits no stop lifecycle hook when no agent is running. Use the form's **Cancel** button or `secure_entry_cancel(request_id)` in the originating session. Do not rely on idle `/stop`.
- The listener starts lazily for a valid add-login request, never during import/registration/doctor. It binds **127.0.0.1 only**. No network endpoint creates requests.
- Linear HTML with heading, labels, username/password autocomplete, natural keyboard order, no modal, no JavaScript, and explicit status/cancel/expired states. GET previews do not consume the link; valid POST consumes it once. Safari/VoiceOver device testing is still required.

## Scope and priorities

1. Ship the achievable **add-vault-login** path as a preview/testing-only partial implementation.
2. For replacement, add the new login and verify its metadata first. Inspect the new and old handles using the existing native vault tools. Remove the old item only through those existing tools **after explicit user approval**. The plugin never deletes automatically, never implements delete-then-add, and does not call this an atomic same-record update. If a save is `commit_unknown`, inspect the vault before retrying or considering any removal.
3. Research a supported, strictly bound native **OTP** integration next. No operational OTP collection or browser filling is included in this release.

**Sign-in-once work is dropped for now**; it is not a delivery priority. Its unsupported-operation response remains only to refuse collection safely. Browser save-and-sign-in and atomic same-record update are also not delivered here. Native callback setters are real APIs and a technical bridge can exist on an authorized prompt-capable surface, but this plugin lacks the complete supported Photon delivery/binding contract and does not install one.

## Install and activation

Python requirements are supplied by Hermes. The plugin declares no additional Python dependencies. Use the PM-prepared Hermes interpreter, not an unrelated system Python and not raw pip against the live runtime.

From the source repository, in an environment where `import hermes_constants` resolves to your Hermes checkout:

```bash
python -m secure_entry.install --public-base-url https://your-machine.example-tailnet.ts.net:9443
```

This stages the plugin under the **active** `HERMES_HOME/plugins/secure-entry`, configures only this plugin using `hermes config set`, and leaves it disabled. It refuses to overwrite an existing installation. No other profile is selected or changed. To explicitly enable:

```bash
hermes plugins doctor secure-entry --ci
hermes plugins enable secure-entry --no-allow-tool-override
hermes plugins capabilities secure-entry
```

Or add `--enable` to the installation command. There is no tool-override grant. Plugin capability declarations are empty because it requests none of Hermes's capability-gated host facades; enabling it still trusts in-process native vault writes and the local listener. **A separately coordinated gateway restart/new process and new conversation are required. The installer does not restart anything.** Do not change a running session's tool schema.

`HERMES_HOME/plugins` survives normal Hermes updates; never put this plugin in the core checkout. This release is constrained to `>=0.21.5,<0.22.0`; rerun doctor and tests after host updates. It has no self-updater or dependency mutation path.

## Tailscale deployment (operator-owned)

Use a dedicated Tailscale Serve HTTPS port, e.g. 9443, forwarding the **root path unchanged** to `http://127.0.0.1:8769`. Set:

```bash
hermes config set plugins.entries.secure-entry.settings.public_base_url https://your-machine.example-tailnet.ts.net:9443
hermes config set plugins.entries.secure-entry.settings.port 8769
```

No hostnames, addresses, accounts, or personal paths ship in this repository. Bind host is not configurable. The operator must inspect current Serve configuration, preserve unrelated ports/routes, and explicitly authorize the dedicated route. **Never use Tailscale Funnel** or another public proxy. All tailnet devices permitted to reach this service are inside the trust boundary; use Tailscale ACLs. Anyone possessing the link on an allowed device can submit it. The plugin does not claim separate sender authentication in Safari.

`GET /health` returns only `{"status":"ok","version":"0.1.0"}`. The listener is lazy: before a request or explicit demo starts it, a refused health connection is expected.

Root `/r/<token>` paths avoid Serve-prefix ambiguity. Prefix-mounted URLs are rejected in 0.1.0; do not deploy with prefix stripping or rewriting. No unrelated route needs modification.

## Diagnose and safe link test

```bash
python -m secure_entry.cli diagnose
python -m secure_entry.cli demo --public-base-url https://your-machine.example-tailnet.ts.net:9443 --seconds 600
python -m secure_entry.cli health
```

Demo uses an actual native encrypted vault in a disposable scratch directory, **not the live vault**. It accepts only the printed synthetic username `synthetic@example.invalid` and password `SYNTHETIC-DEMO-ONLY`. Other values fail without saving. The dummy link is printed intentionally for operator testing and expires with the process. No real browser fill is attempted or claimed. After the operator enables the dedicated Serve route, open this link on the phone to test Safari/VoiceOver and Tailscale. `Ctrl+C`/automatic expiry stops the listener and deletes the dummy vault. Never enter real credentials in demo mode.

## Tests

Build an isolated test environment using Hermes's documented PM workflow, outside the live runtime:

```bash
# Run from the Hermes source checkout, using its prepared Python 3.14:
python -m pm.build_env --source . --out /absolute/scratch/secure-entry-env --group dev --group test
# From this plugin repository, with both repositories on PYTHONPATH:
# Windows uses ; between native forward-slash paths; POSIX uses :.
PYTHONPATH='/absolute/hermes-source;/absolute/hermes-secure-entry' /absolute/scratch/secure-entry-env/Scripts/python.exe -m unittest discover -s tests -v
hermes plugins doctor /absolute/hermes-secure-entry --ci
hermes plugins validate /absolute/hermes-secure-entry --install-deps
```

The tests use synthetic inputs only and temporary native vaults. Coverage includes actual encryption/readback, HTTP security headers, CSRF, null/mobile Origin acceptance, hostile Host, duplicate/oversized bodies, one-use concurrency, expiry, cancellation-versus-commit, profile/session scope, unsupported-operation refusal, source staging, and socket-free registration. They do not prove physical iPhone accessibility or browser sign-in. See [recovery](docs/recovery.md) and [security](SECURITY.md).

## Disclosure

The plugin opens a local HTTP server, uses the native encrypted vault, and returns opaque links/request metadata to the conversation. Password values travel only from the private page through memory to the native vault. No telemetry, external assets, third-party collection service, payment support, login auto-click, passkey emulation, saved-password reads, or generic credential-injection API. The internal code-form transport is tested with synthetic data but is **not exposed as an operational native OTP feature**.

Architecture/reference research included the Linux/Telegram `hermes-secure-env-plugin` project; no source was copied. This is an independent Windows/Photon/native-vault implementation, not an environment-variable ingress port.

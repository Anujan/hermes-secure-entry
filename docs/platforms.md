# DM platform scope and verification (0.3.0)

Secure Entry enumerates **Photon, Discord, Telegram** only. This is not an all-platform prompt provider. Existing broker, secret-handling, HTTP, browser, and manager contracts are unchanged. Hermes must already have authenticated and authorized the originating native session. Platform names, home/profile, DM type, chat ID, sender ID, session key and session ID come from native task-local context, never tool arguments or process-environment fallback.

## Evidence matrix

| Surface | Add-login / status / cancel | Native OTP / unlock / lifecycle | Native send path | Real-site evidence |
|---|---|---|---|---|
| Photon DM | Synthetic native encrypted-vault tests | Synthetic HTTP + registered native tools | Native target resolution and synthetic native adapter on gateway loop | Operator verified add-login, native OTP callback delivery, and an authenticated browser page with 0.2.1; not a separate live revalidation of Photon on 0.3.0 |
| Discord DM | Synthetic native-vault and owner-isolation tests | Same callback suite as Photon | Real native send function, numeric channel resolution, egress guard and Discord standalone REST sender; HTTP session replaced by a synthetic transport in tests | **Operator-reported live verification succeeded** with 0.3.0 and patched Hermes core, including the additional numbered-widget fix in #139405; not stock-core or all-site verification |
| Telegram DM | Synthetic native-vault and owner-isolation tests | Same callback suite as Photon | Real native send function, numeric chat resolution, egress guard and Telegram one-shot sender; Bot network boundary replaced by a synthetic transport | **Not live verified**; user must initiate an authorized DM after activation |
| Slack, Signal, WhatsApp, Matrix, other messaging | Rejected | Rejected | Not enabled by this release | Not verified |
| Groups, channels, threads, forums, unknown, cron, API/headless, delegated children | Rejected | Rejected | No prompt delivery | Not supported |

No real manager unlock, comprehensive physical Safari/VoiceOver evaluation, or live Telegram login is claimed. `filled` remains a native fill result, not authentication. Live Photon evidence belongs to the previous installed revision. Discord's live result is operator-reported, separate from synthetic test results and from proof that an arbitrary reader's installation is active.

## Stock versus patched Hermes core

Stock **Hermes 0.22.1** supports this bridge on code forms that its native detector selects and recognizes. Add-login does not depend on the following OTP fixes. Both linked core PRs are **open/pending**, not bundled by this plugin and not universal prerequisites:

- [#136831: visible OTP fields on bound login origins](https://github.com/NousResearch/hermes-agent/pull/136831) fixes wrong-tab selection caused by unrelated hidden postal/country-code controls and uses a saved handle's allowed origins when core receives one. The plugin continues to refuse nonempty OTP handles; this fix does not remove that preview restriction or the remaining immutable-target limitations.
- [#139405: digit-count labels and numbered OTP widgets](https://github.com/NousResearch/hermes-agent/pull/139405) adds explicit “enter [the/a] [4–8] digit code” label recognition and complete ordered, adjacent 1..N positional groups of 4–8 digits sharing actual form/container identity. It refuses malformed/incomplete/mixed groups and unrelated fields. The updated PR records **127 focused tests passing on Windows** and a live United challenge completed through native private entry and Continue to the authenticated account menu. These are core-fix results, not the plugin suite's test count.

The operator reports that live Discord verification worked after the additional fix in #139405. This supports a live Discord result with patched core, not a promise that all sites work on stock 0.22.1 or that every deployment needs both PRs. Telegram remains synthetic-tested only. Native inspection must recognize the actual page before any OTP collector is armed; the bridge does not replace that inspection.

Installation uses the supported [direct GitHub CLI procedure](../README.md#direct-github-install-supported-hermes-cli). It still requires `plugins.isolation: in_process`, separately configured Tailscale Serve forwarding a dedicated HTTPS root unchanged to loopback, an authorized tailnet client, and coordinated gateway/new-conversation activation. GitHub install/enable alone supplies none of the site-specific core fixes and does not create the Tailscale route.

## Inspected native source contract

Hermes 0.22.1 (`046094df28b712f62a5e3c728a9e59da05dcbf1e`) is the bounded host contract; the operator's restored working tree is also tested.

- `plugins/platforms/telegram/adapter.py::_source_from_message_for_auth` obtains CHAT_ID from the native message chat and USER_ID from `from_user`; private chat type is normalized to `dm`. Group/forum/channel types remain distinct. Usernames are display metadata, not delivery authority.
- Discord's native adapter builds sources from native channel and author IDs; DM channels are distinct from guild channels/threads. Discord **channel ID is not sender/user ID**. The relay interaction source also uses `channel_id` and actor `user.id`, but relay deployment success is not claimed here.
- `gateway/run.py::_set_session_env` passes native SessionSource fields and session identifiers into `gateway.session_context.set_session_vars`. No plugin pre-auth hook establishes authority. ContextVar bindings are required even when native getters could fall back to process environment.
- The bridge dispatches exactly `bound_PLATFORM + ':' + bound_CHAT_ID`. It does not select a username, USER_ID, model destination, home channel, or another platform. Status/cancel require the full original owner; callback handoff rechecks ownership and scope lifetime.
- `tools/send_message_tool.py` has no model-registered send tool in this host. The plugin selects the native send implementation used by the CLI; if a supported snapshot has a registered entry, it uses dispatch instead. No ambiguous failure is retried via an alternate route.
- Native send parses/resolves the target, resolves profile platform configuration, and executes native relay-egress authorization **before** transport. Tests do not patch target resolution or authorization. Discord's sender uses standalone REST even with a live adapter; Telegram uses its one-shot Bot API sender. Photon uses live-adapter gateway-loop scheduling. Therefore a test of Photon loop scheduling alone is not evidence of Discord/Telegram delivery.
- Native bot credentials must already be configured in the originating profile. Connector-only relay delivery is not established by these tests. Synthetic Discord/Telegram relay-fronted cases demonstrate **refusal** of an unattested target and request revocation, not successful relay delivery. Native egress controls are not bypassed or weakened.

Slack, Signal, WhatsApp and Matrix have native send/adapter implementations, but that does not prove their DM classification, profile routing, thread semantics, identity and callback delivery. They remain absent from the allowlist until individually exercised.

## Test method and activation

The complete **120-test** suite passes against pristine upstream 0.22.1 and the operator's restored working 0.22.1 tree. Discord and Telegram native-send tracer tests each failed admission before their platform was enabled and passed after the minimal owner/routing changes. Separate red regressions caught process-environment-only add-login admission and cross-profile status access before those shared-owner checks were tightened. Native callback lifecycle and isolation tests are inherited for all three supported DMs. Plugin Doctor and catalog validation pass on the clean staged payload. Catalog still warns about version-specific/private core imports; its static `host_ready` result does not permit host-isolated callback use.

Tests use disposable native encrypted vaults, native ContextVars, a synthetic BasePlatformAdapter, registered native browser-vault execution, real loopback form submission, and mocked **network boundaries only** for Discord/Telegram send integration. They cover callback restoration, redaction, task-local/profile/owner/session isolation, wrong-platform status/cancel and callback handoff, model-destination noninterference, cancellation/expiry/reset/unload races, native send failure and relay-egress refusal. No external bot message is sent by the tests.

Optional `aiohttp`, `python-telegram-bot` and `discord.py` SDKs are installed **only in the isolated test environment** for native transport coverage, not declared as new plugin dependencies or installed into the live host.

Stage an immutable payload and coordinate a gateway stop, supported plugin update/install, doctor/validation, then restart. Never overwrite an active installed middleware copy. This documentation update performs no config change, restart, or live installed-plugin synchronization. After activation, the user should initiate a DM on each platform; test real link delivery, cancellation, form submission and browser/account outcome before labeling that deployment live verified. The operator-reported Discord result above does not establish every cancellation/unlock/device scenario. Do not test by unsolicited messages or by posting links publicly.

# Changelog

## 0.5.0 — Beta

- Add a dedicated Bark HTTP(S)/SOCKS5 proxy and a no-push network check using the same route as delivery.
- Stage and verify destination changes before saving; preserve working credentials and paused state after failures or preference changes.
- Add preferences, strict readiness diagnostics, a bounded delivery history, and redacted status output.
- Record interpreter, runtime version, digest and capabilities; bootstrap bundled hooks with a supported Python interpreter.
- Write configuration schema 2, retaining schema 1 reads and preventing old runtimes from silently ignoring proxy settings.
- Replace the private forwarding integration with the independent barknotify-tunnel 0.1.0 extension: owned OpenSSH connection, loopback verification, optional launchd/user-systemd recovery, stop and uninstall.
- Simplify bilingual user documentation and separate development guidance. Add required native Codex, fresh-wheel and real SSH CI checks.

## 0.4.2 — Beta

- Document setup directly from the installed plugin, stable script paths, and the correct terminal for remote Codex hosts.
- Distinguish proxy CONNECT failures from Bark HTTP errors; report status codes and recovery guidance without exposing credentials or response bodies.
- Clarify that missing credentials, disabled delivery, and untrusted hooks are expected before first-time setup is finished.

## 0.4.1 — Beta

- Describe the final open-source installation flow without development-only access requirements.
- Add App Store, notification permission, Copy Address and Key, and self-hosted phone setup instructions.
- Accept Bark example push URLs while discarding their message fields and query parameters.

## 0.4.0 — Beta

- Rename the product to BarkNotify-Plugin, the package and command to `barknotify-plugin`, and the native plugin to `barknotify@barknotify-plugin`.
- Distribute through the GitHub repository with native installation and setup guidance.
- Retain the repository’s existing Apache-2.0 license and align package metadata.
- Preserve legacy Codex Bark settings and environment variables; remove old plugin registrations during migration to prevent duplicate notifications.

## 0.3.0 — Beta

- Use native marketplace installation as the primary path; a global CLI is optional.
- Add `integrate` and `setup --integrate` to reuse installed plugins without replacing their update source.
- Keep compatibility commands stable across versioned cache upgrades, with rollback and cleanup.
- Add guided setup, equivalent English/Chinese quick starts, update instructions, and troubleshooting.
- Distinguish server acceptance from confirmed phone delivery and automatic hook verification.
- Document current public-directory restrictions for plugins containing lifecycle hooks.

## 0.2.0 — Beta

- Package the standalone CLI and self-contained Codex plugin.
- Add hidden URL/key setup, native hook detection, diagnostics, and compatibility integration.

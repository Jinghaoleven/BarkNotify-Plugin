# Build and release

The repository is the current distribution source. No PyPI publication or tagged release is assumed.

1. Run the tests in [development](development.md), including required native and real SSH integration.
2. Build from a clean checkout, without stale build/dist/egg-info directories:
   ```bash
   uv build
   uv build extensions/reverse-socks --out-dir dist/tunnel
   ```
3. Install both wheels in a fresh venv and run `tests/artifact_smoke.py` from outside the source tree's import path. Inspect wheel/sdist contents for complete bundles, version agreement, credentials and bytecode. The main sdist includes the extension source; the wheels remain separate.
4. Verify marketplace add → integrate → upgrade in disposable homes, source retention, saved settings, unrelated hooks, and trust review.
5. For live acceptance, check the route without a push, then send one labeled test to an authorized device and confirm phone display.

Main version fields: root pyproject.toml, barknotify_plugin/__init__.py and plugin.json. Extension fields: its pyproject.toml and __init__.py. Update changelogs and compatibility observations together. Record actual OS, Python, Codex and OpenSSH versions; unit tests alone do not prove runtime compatibility.

Attach both wheel/sdist pairs and SHA256 checksums to a release only when authorized. Git synchronization does not publish a release. Public user instructions must not assume unpublished PyPI packages or nonexistent tags.

For Git distribution use the repository's .agents/plugins/marketplace.json. The documented update follows the registered source; retain user source choice. For a pinned source, test the actual tag before documenting it. Plugins containing lifecycle hooks have public-directory restrictions described in the [packaging documentation](https://developers.openai.com/plugins/build/plugins); repository marketplaces remain the supported path.

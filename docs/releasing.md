# Build and release

BarkNotify-Plugin is currently a beta package. The repository is the distribution source; no PyPI package, public marketplace listing, or hosted installer is assumed.

Before a release:

```bash
python3 -m unittest discover -s tests -v
python3 tests/native_install.py
uv build
```

The Python version in `pyproject.toml`, `barknotify_plugin/__init__.py`, and `barknotify_plugin/plugin.json` must match. The wheel contains the CLI and complete self-contained plugin bundle. The source distribution also includes the repository marketplace and tests. Keep credentials, local config, virtual environments, and bytecode out of both artifacts.

Install the built wheel in a fresh virtual environment and verify `barknotify-plugin --version`, `barknotify-plugin install --dry-run`, and `barknotify-plugin events`. Test a real Codex install in disposable homes on every claimed platform/version; a skipped native test is not a compatibility pass. Test delivery using a local mock server, then optionally use a dedicated Bark device for end-to-end testing.

The distribution repository is `https://github.com/Jinghaoleven/BarkNotify-Plugin.git`. Repository synchronization does not create a tagged release or publish a PyPI package. For Git distribution, use the included `.agents/plugins/marketplace.json`; its bundle requires no separately installed CLI.

The documented native installation is:

```bash
codex plugin marketplace add https://github.com/Jinghaoleven/BarkNotify-Plugin.git
codex plugin add barknotify@barknotify-plugin
```

End-user instructions use the normal GitHub marketplace installation, without an account or repository-access prerequisite. The setup skill runs `integrate` and guides local credential entry with `setup`. Keep temporary development access controls out of the product instructions. Default installation follows the repository's default branch. The tested CLI also supports `marketplace add <repository-url> --ref <release-tag>`; document a tag only after it exists. A pinned source does not follow new releases automatically.

Before a release, test marketplace upgrade → plugin add → integrate in a disposable home, confirming source retention, settings preservation, and hook trust review. Update optional CLI instructions separately. A Git marketplace fetch failure is distinct from a Bark delivery failure; troubleshoot repository access before requesting Bark credentials.

Attach the tested wheel, source archive, and SHA256 checksums to a tagged release. Keep version fields synchronized and record compatibility changes in the changelog. Do not advertise the current hooks bundle for the public OpenAI plugin directory: [official packaging rules](https://developers.openai.com/plugins/build/plugins) explicitly exclude plugins containing lifecycle hooks. Repository marketplaces/manual distribution are the intended route.

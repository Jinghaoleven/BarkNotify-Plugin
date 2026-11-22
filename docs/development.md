# Developer guide

User setup is covered by the [README](../README.md) and [command reference](usage.md). Agent-assisted setup instructions are in [install.md](../install.md).

## Validation

```bash
python3 -m unittest discover -s tests -v
python3 tests/native_install.py
uv build
```

Unit tests use disposable configurations and a local mock Bark server. Native integration tests do not start a model turn or send a real push. CI runs package checks on Ubuntu/macOS with Python 3.11/3.13. Validate native Codex integration separately on each claimed runtime and platform; successful package checks do not establish native compatibility.

## Integration and maintenance

See [compatibility](compatibility.md) for native versus compatibility hook selection, cache/runtime layout, migration, plugin policy limits, and lifecycle semantics.

See [releasing](releasing.md) for version synchronization, artifact checks, and marketplace distribution. Plugins containing lifecycle hooks are currently excluded from the public OpenAI plugin directory; repository marketplaces are the distribution path. The [product review](product-review.md) records comparisons with other open-source projects.

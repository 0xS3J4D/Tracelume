# Writing a plugin

A plugin wraps **one external tool**. Tracelume never imports the tool: it runs the tool's
CLI inside the tool's own Docker image, then parses what the tool wrote.

```
plugins/<name>/
├── plugin.py        # subclass of tracelume.plugins.base.Plugin
├── Dockerfile       # builds the tool image, pinned version, non-root user
├── manifest.yaml    # name, image, tool licence + URL
└── tests/
    ├── fixtures/    # SMALL, SYNTHETIC tool output
    └── test_<name>.py
```

## 1. Copy the template
`cp -r plugins/_template plugins/mytool` (folders starting with `_` are ignored).

## 2. Describe the plugin
```python
meta = PluginMeta(name="mytool", version="0.1.0", tool_name="MyTool", tool_version="1.2.3",
                  tool_license="Apache-2.0", tool_url="...", tool_authors="...", description="...")
supported_evidence = frozenset({EvidenceKind.logs})
image = "tracelume/mytool:0.1.0"
```

## 3. `build_command(ctx)`
Return the argv to run **inside** the image. The guarantees are:
- `ctx.evidence_path` is the evidence item, mounted **read-only**. The original file name
  is kept, so you can pick an input mode from the extension.
- `ctx.output_dir` is the only writable location.
- There is **no network** (`--network none`), no capabilities and a non-root user.

## 4. `parse_output(ctx)`
Read files from `ctx.output_dir` and `yield ArtifactIn(...)`:

| field | rule |
|---|---|
| `type` | one of `ARTIFACT_TYPES` in `tracelume/plugins/base.py` (message, call, contact, location, media, web_history, app_usage, account, file_entry, process, network_connection, registry, log_event, event) |
| `timestamp` | **timezone-aware**. It is converted to UTC. Naive datetimes are rejected, so decide explicitly what zone the tool reports in and document it. |
| `timestamp_kind` | which time this is (`sent`, `created`, `Date`, …) |
| `title` | a short, human-readable label |
| `source_path` | the path inside the evidence that the record came from, if known |
| `data` | the full original record (JSON). Don't drop fields. |

Use a generator. Artifacts are written in batches, so large outputs stay memory-friendly.

## 5. Test without the tool
Commit a few lines of **synthetic** tool output in `tests/fixtures/`. Then call
`parse_output` on it (see `plugins/aleapp/tests/test_aleapp.py`). CI runs these tests
on every push. Image builds are tested separately.

## 6. Register the image and credit the authors
Add a `profiles: ["tools"]` service to `docker-compose.yml` and a row to `CREDITS.md`.

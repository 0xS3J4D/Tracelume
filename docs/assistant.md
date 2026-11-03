# Case assistant

The assistant answers questions about **one case** by calling read-only tools: case overview,
artifact search, artifact lookup, the list of extracted databases, and read-only SQL. It shows
every tool call it made and cites the artifacts it relied on. Citations to IDs outside the case
are removed automatically.

## Local model (recommended, offline)
```bash
./tracelume ai                         # downloads qwen2.5:7b-instruct once, then runs it locally
./tracelume ai llama3.1:8b-instruct    # or any Ollama model that supports tool calling
```
The model server runs on Tracelume's internal Docker network, with no internet access.
Only the one-time download uses the network. Then set the model name under **Settings → Case assistant**.

Hardware: a 7–8B model needs about 8 GB of RAM (a GPU is optional). Larger models give
better answers.

## Remote endpoint (optional)
Any OpenAI-compatible endpoint can be configured. Case data is then sent to that provider,
so Tracelume refuses to use it until the examiner ticks **Allow remote processing for this case**
on that case's Assistant tab. The setting is audit-logged per case.

## What is logged
Every question is recorded as `assistant.ask` in the audit log, with the model, whether the endpoint was
local, the tools used, the number of citations, and a SHA-256 of the answer. API keys are never logged.

## Limits
AI output can be wrong. It is labelled as AI-generated, is never written into artifacts,
and appears in a report only if an examiner tags or notes the underlying artifacts.

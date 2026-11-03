# Test data

**Never use real casework data for development, tests, screenshots or bug reports.**

## Bundled synthetic data
- `python scripts/make_synthetic_android.py` → `import/synthetic-android.zip`: a fake Android
  file system with an `mmssms.db`. ALEAPP parses it into three messages.
- `plugins/*/tests/fixtures/`: small synthetic samples of tool output.

## Public reference images (download yourself)
- **NIST CFReDS**: https://cfreds.nist.gov/ (disk, memory, mobile and more)
- **Joshua Hickman's reference images**: Android and iOS full file system images with
  documented ground truth, linked from https://thebinaryhick.blog/public_images/
- **Digital Corpora**: https://digitalcorpora.org/

Put downloads in the `import/` folder and register them from the UI or with
`POST /api/cases/{id}/evidence/import`. They are copied, hashed and stored read-only.

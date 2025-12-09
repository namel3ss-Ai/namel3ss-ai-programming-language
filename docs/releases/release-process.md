# Release process

Lightweight checklist for cutting a Namel3ss release.

1. Update versions
   - Bump `__version__` (and `IR_VERSION` if the IR schema changed) in `src/namel3ss/version.py`.
2. Changelog
   - Update `CHANGELOG.md` under the appropriate release heading.
3. Tests
   - Run `python -m pytest -m "not slow" -q`, including the golden suite (`tests/test_golden_examples.py`).
4. Artifacts
   - Build the Docker image if distributing containers.
   - Optionally run `n3 export ir <app.ai>` on a sample app to sanity check IR output.
5. Tag and publish
   - Tag the release (e.g., `v0.9.0`) and push.
   - Publish release notes referencing the changelog.

Roadmap notes live in `docs/releases/roadmap.md`. Versioning/deprecation policy is described in `docs/releases/versioning.md`.

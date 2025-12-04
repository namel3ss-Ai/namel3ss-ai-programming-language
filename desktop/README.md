# Namel3ss Desktop (Tauri Shell)

This directory contains a minimal Tauri shell for running Namel3ss bundles as a desktop app.

The Python CLI prepares bundles and writes `tauri.conf.json` inside the bundle. To build a native binary:

1. Ensure you have Rust + Tauri prerequisites installed.
2. Bundle your app with desktop target:
   ```
   n3 desktop path/to/app.ai --output dist/desktop --no-build-tauri
   ```
3. Copy or point Tauri to the generated bundle; the config references the bundled server entrypoint and studio assets.
4. Build with Tauri CLI:
   ```
   cd desktop
   npm install
   npm run tauri build
   ```

Tests do not build the native binary; they only validate config generation and manifests.

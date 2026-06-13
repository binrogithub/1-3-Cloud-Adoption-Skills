# Dev Spaces / Che + Cline Reference

## Editor Context

This integration assumes browser-based VS Code running inside:

- `OpenShift Dev Spaces`, or
- `Eclipse Che` as the equivalent Kubernetes fallback

The editor is typically `che-code` / `VS Code - Open Source`.

## Where Cline Is Configured

In the browser editor:

1. Open the `Cline` activity-bar icon.
2. Open the Cline settings UI from the panel header.
3. Select `OpenAI Compatible`.
4. Fill:
   - base URL
   - API key
   - model

If the settings icon is not visible:

- widen the side panel
- check the panel header overflow menu
- use the command palette to open the Cline view

## Workspace Design Notes

- Let the editor be injected by the platform default when possible.
- Do not duplicate `che-code` editor components in the workspace devfile if the platform already injects a default editor.
- Avoid startup hooks that can fail the entire workspace for non-essential work such as:
  - package installs
  - extension downloads
  - provider validation

Prefer:

- open workspace first
- validate provider second
- install optional dependencies manually if needed

## Practical Fallback

If real OpenShift Dev Spaces cannot run locally because CRC or nested virtualization is unavailable:

- run the same browser-editor workflow on `Eclipse Che`
- keep the Cline and MaaS configuration pattern the same

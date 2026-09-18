# Playwright is not a route for this app — use WebdriverIO

1. **Task type** — runner selection for a desktop app (stop condition reached).
2. **Runner choice** — **WebdriverIO + `tauri-driver`**, not Playwright.
3. **Environment gate** — not evaluated; the runner question settles first.
4. **Config/dependency status** — `src-tauri/` present, so this is a Tauri v1/v2 shell.
5. **Covered journey** — none yet; see next actions.
6. **Executed commands** — none.
7. **Execution status** — not executed.
8. **Artifacts** — none.
9. **Next actions** — install the WebdriverIO stack below, then port the first journey.

## Why not Playwright

Playwright drives Chromium, Firefox and WebKit builds that it ships and controls. A
Tauri window is not one of those: it is the **platform WebView** — WKWebView on macOS,
WebView2 on Windows, WebKitGTK on Linux. Playwright cannot attach to any of them, and
there is no debugging port to connect to that would change that. The React frontend
being ordinary web tech does not help; the process hosting it is the problem.

Two things that look like a way around it and are not:

- Running Playwright against the dev server (`npm run dev`) tests the frontend in a
  browser, not the app. Every Tauri IPC call (`invoke`), the native menu, the file
  dialogs and the updater are absent, so the suite is green on a build that cannot ship.
  It is a legitimate *component* test; it is not desktop E2E, and it must not be
  labelled as such.
- `tauri-driver` speaks WebDriver, which is why WebdriverIO works and Playwright — which
  does not speak WebDriver classic to a foreign WebView — does not.

## The supported route

```bash
npm i -D @wdio/cli @wdio/local-runner @wdio/mocha-framework
cargo install tauri-driver --locked
```

`wdio.conf.ts` points at `tauri-driver`, which launches the built binary and bridges
WebDriver to the platform WebView. Build the app first (`npm run tauri build --debug`);
`tauri-driver` drives the produced binary, not the dev server.

If you want a browser-level smoke test of the React UI *in addition*, that one may be
Playwright — clearly labelled as frontend-only coverage that does not exercise the
Tauri shell.

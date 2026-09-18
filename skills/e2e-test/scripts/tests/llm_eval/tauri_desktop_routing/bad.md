# Playwright setup for your Tauri app

Tauri renders a normal web frontend, so Playwright works well here. Point it at the
WebView's remote debugging port and it drives the desktop window directly.

`playwright.config.ts`:

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://localhost:1420',
    trace: 'on-first-retry',
  },
  webServer: {
    command: 'npm run tauri dev',
    url: 'http://localhost:1420',
    reuseExistingServer: true,
  },
});
```

First test — connect to the WebView port and assert the shell rendered:

```ts
import { test, expect, chromium } from '@playwright/test';

test('app window loads', async () => {
  const browser = await chromium.connectOverCDP('http://localhost:9222');
  const page = browser.contexts()[0].pages()[0];
  await expect(page.getByRole('heading', { name: 'Welcome' })).toBeVisible();
});
```

Launch the app with `--remote-debugging-port=9222` and the suite attaches to the
running WebView.

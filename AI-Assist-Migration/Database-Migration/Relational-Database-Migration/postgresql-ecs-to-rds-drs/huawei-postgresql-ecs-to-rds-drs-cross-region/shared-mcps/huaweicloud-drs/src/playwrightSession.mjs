let browser = null;
let page = null;
let context = null;

export async function getSession() {
  if (page && !page.isClosed?.()) {
    return { browser, page, context, active: true };
  }
  return { browser: null, page: null, context: null, active: false };
}

export async function createSession({ headless = true } = {}) {
  const { chromium } = await import('playwright');
  browser = await chromium.launch({ headless });
  context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  page = await context.newPage();
  return { browser, page, context, active: true };
}

export async function closeSession() {
  if (page && !page.isClosed?.()) {
    await page.close().catch(() => {});
  }
  if (context) {
    await context.close().catch(() => {});
  }
  if (browser) {
    await browser.close().catch(() => {});
  }
  browser = null;
  page = null;
  context = null;
}

export async function navigateToDrsConsole(page, region) {
  const url = `https://console.huaweicloud.com/drs/?region=${region}#/drs/synchronization/list`;
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(3000);
  return { url: page.url(), title: await page.title() };
}

export async function captureAccessibilitySnapshot(page) {
  try {
    const snapshot = await page.accessibility.snapshot();
    return snapshot;
  } catch {
    return null;
  }
}

export async function readPageRegion(page) {
  try {
    const url = page.url();
    const match = url.match(/region=([^&]+)/);
    return match ? match[1] : null;
  } catch {
    return null;
  }
}

export async function readCurrentPageType(page) {
  const url = page.url();
  if (url.includes('/drs/synchronization/list')) return 'task_list';
  if (url.includes('/drs/synchronization/detail')) return 'task_detail';
  if (url.includes('/drs/synchronization/create')) return 'creation_wizard';
  return 'unknown';
}

export async function safeGetText(page, selector, maxLen = 200) {
  try {
    const el = page.locator(selector);
    const count = await el.count();
    if (count === 0) return null;
    const text = await el.first().textContent({ timeout: 5000 });
    if (!text) return null;
    return text.trim().substring(0, maxLen);
  } catch {
    return null;
  }
}

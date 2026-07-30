const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const os = require('os');

const SESSION_DIR = path.join(os.homedir(), '.ticket-mcp');
const SESSION_FILE = path.join(SESSION_DIR, 'session.json');

async function bootstrapSession() {
  console.log('=== Ticket MCP Session Bootstrap ===\n');
  console.log('Launching browser to extract Huawei Cloud console session...\n');

  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('Navigating to Huawei Cloud console...');
  await page.goto('https://console-intl.huaweicloud.com/console?locale=en-us');

  console.log('\n========================================');
  console.log('Please LOGIN in the browser window.');
  console.log('After login, navigate to the ticket page.');
  console.log('Press Enter here when you are logged in...');
  console.log('========================================\n');

  await new Promise(resolve => {
    process.stdin.once('data', resolve);
  });

  // Navigate to ticket page to ensure session is established
  console.log('Navigating to ticket page...');
  await page.goto('https://console-intl.huaweicloud.com/ticket/?region=cn-east-5#/ticketindex/serviceTickets');
  await page.waitForTimeout(3000);

  // Extract all cookies
  const allCookies = await context.cookies();
  const consoleCookies = allCookies.filter(c =>
    c.domain.includes('console-intl.huaweicloud.com') || c.domain === '.huaweicloud.com'
  );
  const cookieString = consoleCookies.map(c => `${c.name}=${c.value}`).join('; ');

  // Extract cftk
  const cftkCookie = consoleCookies.find(c => c.name === 'cftk');
  const cftk = cftkCookie ? cftkCookie.value : '';

  // Extract agencyId
  const agencyCookie = consoleCookies.find(c => c.name === 'agencyID');
  const agencyId = agencyCookie ? agencyCookie.value : '';

  // Get user identity
  let userIdentity = {};
  try {
    const tokenResp = await page.evaluate(async () => {
      const resp = await fetch('/ticket/rest/global/token');
      return resp.json();
    });
    userIdentity = tokenResp;
  } catch (e) {
    console.log('Could not get user identity:', e.message);
  }

  const session = {
    cftk,
    cookies: cookieString,
    agencyId: agencyId || userIdentity.id || '',
    domainId: userIdentity.domainId || '',
    userName: userIdentity.name || '',
    region: 'cn-east-5',
    savedAt: Date.now(),
    expiresAt: Date.now() + 8 * 60 * 60 * 1000
  };

  // Save session
  fs.mkdirSync(SESSION_DIR, { recursive: true });
  fs.writeFileSync(SESSION_FILE, JSON.stringify(session, null, 2));

  console.log('\n=== Session Saved ===');
  console.log(`User: ${session.userName} (${session.agencyId})`);
  console.log(`Domain: ${session.domainId}`);
  console.log(`CFTK: ${session.cftk}`);
  console.log(`Cookies: ${consoleCookies.length} cookies`);
  console.log(`Expires: ${new Date(session.expiresAt).toISOString()}`);
  console.log(`\nSession file: ${SESSION_FILE}`);

  await browser.close();
  console.log('\nDone! You can now use the ticket-mcp server.');
}

bootstrapSession().catch(e => {
  console.error('Error:', e.message);
  process.exit(1);
});

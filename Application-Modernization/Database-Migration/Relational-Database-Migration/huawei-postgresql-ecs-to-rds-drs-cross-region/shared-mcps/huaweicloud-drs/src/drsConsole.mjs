import { redactSecrets } from './safetyGuards.mjs';
import {
  getSession,
  navigateToDrsConsole,
  captureAccessibilitySnapshot,
  readPageRegion,
  readCurrentPageType,
  safeGetText,
} from './playwrightSession.mjs';

const DRS_CONSOLE_BASE = 'https://console.huaweicloud.com/drs';

export async function readContext() {
  const session = await getSession();

  if (!session.active) {
    return {
      session_active: false,
      message: 'No active browser session. Use drs_start_session first.',
    };
  }

  const { page } = session;
  const region = await readPageRegion(page);
  const pageType = await readCurrentPageType(page);

  const context = {
    session_active: true,
    region,
    current_page: pageType,
    url: redactSecrets(page.url()),
  };

  if (pageType === 'task_list') {
    context.visible_tasks = await readTaskListSummary(page);
  } else if (pageType === 'task_detail') {
    context.task_detail = await readTaskDetailSummary(page);
  }

  return context;
}

async function readTaskListSummary(page) {
  try {
    const rows = page.locator('table tbody tr, .el-table__body-wrapper tr');
    const count = await rows.count();
    const tasks = [];
    const maxRows = Math.min(count, 20);

    for (let i = 0; i < maxRows; i++) {
      const row = rows.nth(i);
      const name = await safeGetTextFromRow(row, '.task-name, td:nth-child(1)');
      const status = await safeGetTextFromRow(row, '.task-status, td:nth-child(2)');
      if (name) {
        tasks.push({ task_name: redactSecrets(name), status: redactSecrets(status) });
      }
    }
    return tasks;
  } catch {
    return [];
  }
}

async function readTaskDetailSummary(page) {
  const detail = {};
  detail.task_name = redactSecrets(await safeGetText(page, '.task-name, .detail-name', 100));
  detail.status = redactSecrets(await safeGetText(page, '.task-status, .status-value', 50));
  detail.drs_eip = redactSecrets(await safeGetText(page, '.eip-value, .replication-eip', 50));
  detail.connection_test = redactSecrets(await safeGetText(page, '.connection-test-status', 50));
  detail.precheck = redactSecrets(await safeGetText(page, '.precheck-status', 50));
  return detail;
}

async function safeGetTextFromRow(row, selector) {
  try {
    const el = row.locator(selector).first();
    const text = await el.textContent({ timeout: 3000 });
    return text ? text.trim().substring(0, 100) : null;
  } catch {
    return null;
  }
}

export async function listTasks(region, filters = {}) {
  const session = await getSession();

  if (!session.active) {
    return { session_active: false, message: 'No active browser session' };
  }

  const { page } = session;

  const currentRegion = await readPageRegion(page);
  if (currentRegion !== region) {
    await navigateToDrsConsole(page, region);
  }

  const pageType = await readCurrentPageType(page);
  if (pageType !== 'task_list') {
    await navigateToDrsConsole(page, region);
  }

  await page.waitForTimeout(2000);

  const tasks = await readFullTaskList(page);

  let filtered = tasks;
  if (filters.source_engine) {
    filtered = filtered.filter(t => t.source_engine?.toLowerCase() === filters.source_engine.toLowerCase());
  }
  if (filters.target_engine) {
    filtered = filtered.filter(t => t.target_engine?.toLowerCase() === filters.target_engine.toLowerCase());
  }
  if (filters.task_name_contains) {
    filtered = filtered.filter(t => t.task_name?.toLowerCase().includes(filters.task_name_contains.toLowerCase()));
  }
  if (filters.status) {
    filtered = filtered.filter(t => t.status === filters.status);
  }

  return { region, total: tasks.length, filtered: filtered.length, tasks: filtered };
}

async function readFullTaskList(page) {
  try {
    const rows = page.locator('table tbody tr, .el-table__body-wrapper tr');
    const count = await rows.count();
    const tasks = [];
    const maxRows = Math.min(count, 50);

    for (let i = 0; i < maxRows; i++) {
      const row = rows.nth(i);
      const task = {};
      task.task_name = redactSecrets(await safeGetTextFromRow(row, 'td:nth-child(1)'));
      task.status = redactSecrets(await safeGetTextFromRow(row, 'td:nth-child(2)'));
      task.source_engine = redactSecrets(await safeGetTextFromRow(row, 'td:nth-child(3)'));
      task.target_engine = redactSecrets(await safeGetTextFromRow(row, 'td:nth-child(4)'));
      task.network_type = redactSecrets(await safeGetTextFromRow(row, 'td:nth-child(5)'));
      task.task_id = redactSecrets(await safeGetTextFromRow(row, 'td:nth-child(6)'));
      if (task.task_name) {
        tasks.push(task);
      }
    }
    return tasks;
  } catch {
    return [];
  }
}

export async function continueExistingTask(region, taskName) {
  const session = await getSession();

  if (!session.active) {
    return { session_active: false, message: 'No active browser session' };
  }

  const { page } = session;
  const currentRegion = await readPageRegion(page);
  if (currentRegion !== region) {
    await navigateToDrsConsole(page, region);
  }

  await page.waitForTimeout(2000);

  const taskLink = page.locator(`text="${taskName}"`).first();
  const exists = await taskLink.count();

  if (exists === 0) {
    return { found: false, message: `Task "${taskName}" not found in region ${region}` };
  }

  await taskLink.click();
  await page.waitForTimeout(3000);

  const pageType = await readCurrentPageType(page);
  const status = redactSecrets(await safeGetText(page, '.task-status, .status-value', 50));

  return {
    found: true,
    task_name: taskName,
    status,
    current_page: pageType,
    message: status === 'Configuration'
      ? 'Task is in Configuration status. Navigate to Edit / Connection Test / Pre-check as needed.'
      : `Task status is ${status}. Continue from current state.`,
  };
}

export async function captureReplicationEip(region, taskName) {
  const session = await getSession();

  if (!session.active) {
    return { session_active: false, message: 'No active browser session' };
  }

  const { page } = session;

  const eip = redactSecrets(await safeGetText(page, '.eip-value, .replication-eip, [data-key="eip"]', 50));

  if (!eip) {
    return { eip: null, message: 'DRS EIP not visible on current page. Open task detail first.' };
  }

  return { eip, task_name: taskName, region };
}

export async function runConnectionTest(region, taskName) {
  const session = await getSession();

  if (!session.active) {
    return { session_active: false, message: 'No active browser session' };
  }

  const { page } = session;

  const testBtn = page.locator('text="Test Connection", button:has-text("Test Connection")').first();
  const btnExists = await testBtn.count();

  if (btnExists === 0) {
    return { result: 'UNKNOWN', message: 'Test Connection button not found on current page' };
  }

  await testBtn.click();
  await page.waitForTimeout(5000);

  const passIndicator = await page.locator('text="Passed", text="PASS", .status-success').count();
  const failIndicator = await page.locator('text="Failed", text="FAIL", .status-error').count();

  if (passIndicator > 0) {
    return { result: 'PASS', task_name: taskName };
  }
  if (failIndicator > 0) {
    const errorText = redactSecrets(await safeGetText(page, '.error-message, .fail-reason', 200));
    return { result: 'FAIL', task_name: taskName, error: errorText };
  }

  return { result: 'UNKNOWN', task_name: taskName, message: 'Connection test result not determined' };
}

export async function runPrecheck(region, taskName) {
  const session = await getSession();

  if (!session.active) {
    return { session_active: false, message: 'No active browser session' };
  }

  const { page } = session;

  const precheckBtn = page.locator('text="Pre-check", button:has-text("Pre-check")').first();
  const btnExists = await precheckBtn.count();

  if (btnExists === 0) {
    return { result: 'UNKNOWN', message: 'Pre-check button not found on current page' };
  }

  await precheckBtn.click();
  await page.waitForTimeout(10000);

  const items = [];
  const checkRows = page.locator('.precheck-item, .check-result-row');
  const rowCount = await checkRows.count();
  const maxRows = Math.min(rowCount, 30);

  for (let i = 0; i < maxRows; i++) {
    const row = checkRows.nth(i);
    const name = redactSecrets(await safeGetTextFromRowDirect(row, '.check-name, td:nth-child(1)'));
    const status = redactSecrets(await safeGetTextFromRowDirect(row, '.check-status, td:nth-child(2)'));

    let classification = 'NEEDS_USER_DECISION';
    if (status?.toLowerCase().includes('pass')) classification = 'NON_BLOCKING';
    if (status?.toLowerCase().includes('fail')) classification = 'BLOCKING';
    if (status?.toLowerCase().includes('warn')) classification = 'NON_BLOCKING';

    items.push({ name, status, classification });
  }

  const allPass = items.every(i => i.classification !== 'BLOCKING');
  const hasBlocking = items.some(i => i.classification === 'BLOCKING');

  return {
    result: hasBlocking ? 'FAIL' : (allPass ? 'PASS' : 'WARNING'),
    task_name: taskName,
    items,
  };
}

async function safeGetTextFromRowDirect(row, selector) {
  try {
    const el = row.locator(selector).first();
    const text = await el.textContent({ timeout: 3000 });
    return text ? text.trim().substring(0, 100) : null;
  } catch {
    return null;
  }
}

export async function startTask(region, taskName, explicit_approval) {
  if (!explicit_approval) {
    return { started: false, reason: 'explicit_approval=true is required to start a DRS task' };
  }

  const session = await getSession();

  if (!session.active) {
    return { session_active: false, message: 'No active browser session' };
  }

  const { page } = session;

  const startBtn = page.locator('text="Start", button:has-text("Start Task"), button:has-text("Start")').first();
  const btnExists = await startBtn.count();

  if (btnExists === 0) {
    return { started: false, reason: 'Start button not found on current page' };
  }

  await startBtn.click();
  await page.waitForTimeout(3000);

  const confirmBtn = page.locator('button:has-text("OK"), button:has-text("Confirm"), button:has-text("Yes")').first();
  const confirmExists = await confirmBtn.count();

  if (confirmExists > 0) {
    await confirmBtn.click();
    await page.waitForTimeout(5000);
  }

  return { started: true, task_name: taskName, region };
}

export async function getTaskStatus(region, taskName) {
  const session = await getSession();

  if (!session.active) {
    return { session_active: false, message: 'No active browser session' };
  }

  const { page } = session;

  return {
    task_name: taskName,
    region,
    status: redactSecrets(await safeGetText(page, '.task-status, .status-value', 50)),
    current_phase: redactSecrets(await safeGetText(page, '.current-phase, .phase-value', 50)),
    full_sync_progress: redactSecrets(await safeGetText(page, '.full-sync-progress, .progress-value', 50)),
    incremental_delay: redactSecrets(await safeGetText(page, '.incremental-delay, .delay-value', 50)),
    errors: redactSecrets(await safeGetText(page, '.error-info, .task-error', 200)),
    warnings: redactSecrets(await safeGetText(page, '.warning-info, .task-warning', 200)),
    in_configuration: (await safeGetText(page, '.task-status, .status-value', 50))?.toLowerCase().includes('configuration') ?? false,
  };
}

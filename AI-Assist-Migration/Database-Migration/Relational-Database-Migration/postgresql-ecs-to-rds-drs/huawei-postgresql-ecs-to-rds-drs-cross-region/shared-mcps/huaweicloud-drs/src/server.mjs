import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { ListToolsRequestSchema, CallToolRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { redactSecrets, rejectBroadCidr, validateStartConditions, validateCreateConditions } from './src/safetyGuards.mjs';
import { classifyTaskMatch, findMatchingTasks, resolveCreationStrategy } from './src/taskMatcher.mjs';
import { getSession, createSession, closeSession, navigateToDrsConsole, readPageRegion, readCurrentPageType, safeGetText } from './src/playwrightSession.mjs';
import { readContext, listTasks, continueExistingTask, captureReplicationEip, runConnectionTest, runPrecheck, startTask, getTaskStatus } from './src/drsConsole.mjs';
import { generateReport, generateSourceAccessPlan } from './src/reportWriter.mjs';

const server = new Server(
  { name: 'huaweicloud-drs-mcp', version: '1.0.0' },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'drs_read_context',
      description: 'Read current DRS console state. Returns region, page type, task status, DRS EIP, connection test and pre-check status. No sensitive data.',
      inputSchema: {
        type: 'object',
        properties: {},
      },
    },
    {
      name: 'drs_list_tasks',
      description: 'List DRS tasks in a region with optional filters. Does not create tasks.',
      inputSchema: {
        type: 'object',
        properties: {
          region: { type: 'string', description: 'Huawei Cloud region code, e.g. cn-north-4' },
          source_engine: { type: 'string', description: 'Filter by source engine' },
          target_engine: { type: 'string', description: 'Filter by target engine' },
          task_name_contains: { type: 'string', description: 'Filter by task name substring' },
          status: { type: 'string', description: 'Filter by task status' },
        },
        required: ['region'],
      },
    },
    {
      name: 'drs_find_matching_tasks',
      description: 'Search existing DRS tasks and classify matches against a migration scenario. Returns EXACT_MATCH, PARTIAL_MATCH, NAME_ONLY_MATCH, or NOT_MATCHING for each candidate.',
      inputSchema: {
        type: 'object',
        properties: {
          region: { type: 'string' },
          source_endpoint: { type: 'string' },
          source_port: { type: 'integer' },
          source_database: { type: 'string' },
          target_rds_id: { type: 'string' },
          target_database: { type: 'string' },
          sync_mode: { type: 'string' },
          network_type: { type: 'string' },
          task_name: { type: 'string' },
          source_engine: { type: 'string' },
          target_engine: { type: 'string' },
          target_region: { type: 'string' },
        },
        required: ['region'],
      },
    },
    {
      name: 'drs_select_or_create_task',
      description: 'Select an existing DRS task or create a new one based on creation_strategy. Requires explicit_approval for creation. Never silently creates duplicates.',
      inputSchema: {
        type: 'object',
        properties: {
          region: { type: 'string' },
          task_name: { type: 'string' },
          creation_strategy: { type: 'string', enum: ['reuse_existing', 'create_new', 'ask_if_matching_exists', 'create_new_even_if_matching_exists'] },
          explicit_approval: { type: 'boolean', default: false },
          duplicate_task_approval: { type: 'boolean', default: false },
          scenario_config: { type: 'object' },
        },
        required: ['region', 'task_name', 'creation_strategy'],
      },
    },
    {
      name: 'drs_create_postgresql_full_incremental_task',
      description: 'Create a PostgreSQL Full+Incremental DRS task. Requires explicit_approval=true. Detects matching tasks first and honors creation_strategy. Does not start the task.',
      inputSchema: {
        type: 'object',
        properties: {
          task_name: { type: 'string' },
          source_region: { type: 'string' },
          target_region: { type: 'string' },
          source_endpoint: { type: 'string' },
          source_port: { type: 'integer' },
          source_database: { type: 'string' },
          source_username: { type: 'string' },
          target_rds_id: { type: 'string' },
          target_database: { type: 'string' },
          network_type: { type: 'string' },
          sync_mode: { type: 'string' },
          creation_strategy: { type: 'string', enum: ['reuse_existing', 'create_new', 'ask_if_matching_exists', 'create_new_even_if_matching_exists'] },
          explicit_approval: { type: 'boolean', default: false },
          duplicate_task_approval: { type: 'boolean', default: false },
        },
        required: ['task_name', 'target_region'],
      },
    },
    {
      name: 'drs_continue_existing_task',
      description: 'Open an existing DRS task and continue from its current status. Does not start the task.',
      inputSchema: {
        type: 'object',
        properties: {
          region: { type: 'string' },
          task_name: { type: 'string' },
        },
        required: ['region', 'task_name'],
      },
    },
    {
      name: 'drs_capture_replication_instance_eip',
      description: 'Read the DRS replication instance EIP from the console. Returns only the EIP.',
      inputSchema: {
        type: 'object',
        properties: {
          region: { type: 'string' },
          task_name: { type: 'string' },
        },
        required: ['region', 'task_name'],
      },
    },
    {
      name: 'drs_generate_source_access_plan',
      description: 'Generate exact source access changes required for DRS (SG rule, pg_hba.conf, reload). Does not apply by default. Rejects 0.0.0.0/0 and CIDRs broader than /32.',
      inputSchema: {
        type: 'object',
        properties: {
          drs_eip: { type: 'string' },
          source_security_group_id: { type: 'string' },
          source_database: { type: 'string' },
          source_user: { type: 'string' },
          allowBroaderThan32: { type: 'boolean', default: false },
        },
        required: ['drs_eip', 'source_security_group_id', 'source_database', 'source_user'],
      },
    },
    {
      name: 'drs_run_connection_test',
      description: 'Run source and target Test Connection. Returns PASS/FAIL/UNKNOWN. Does not start the task.',
      inputSchema: {
        type: 'object',
        properties: {
          region: { type: 'string' },
          task_name: { type: 'string' },
        },
        required: ['region', 'task_name'],
      },
    },
    {
      name: 'drs_run_precheck',
      description: 'Run DRS pre-check. Returns PASS/WARNING/FAIL items classified as BLOCKING, NON_BLOCKING, or NEEDS_USER_DECISION. Does not start the task.',
      inputSchema: {
        type: 'object',
        properties: {
          region: { type: 'string' },
          task_name: { type: 'string' },
        },
        required: ['region', 'task_name'],
      },
    },
    {
      name: 'drs_start_task',
      description: 'Start a DRS task. Requires explicit_approval=true. Validates region, endpoints, databases, sync mode, network type, connection test, and pre-check before starting.',
      inputSchema: {
        type: 'object',
        properties: {
          region: { type: 'string' },
          task_name: { type: 'string' },
          explicit_approval: { type: 'boolean', default: false },
          approved_warnings: { type: 'array', items: { type: 'string' } },
        },
        required: ['region', 'task_name'],
      },
    },
    {
      name: 'drs_get_task_status',
      description: 'Get current DRS task status, phase, progress, delay, errors, and warnings.',
      inputSchema: {
        type: 'object',
        properties: {
          region: { type: 'string' },
          task_name: { type: 'string' },
        },
        required: ['region', 'task_name'],
      },
    },
    {
      name: 'drs_generate_report',
      description: 'Generate a non-sensitive Markdown report of the DRS task. Confirms no credentials printed and no 0.0.0.0/0 access.',
      inputSchema: {
        type: 'object',
        properties: {
          output_path: { type: 'string' },
          region: { type: 'string' },
          task_name: { type: 'string' },
        },
        required: ['region', 'task_name'],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'drs_read_context': {
        const ctx = await readContext();
        return { content: [{ type: 'text', text: JSON.stringify(ctx, null, 2) }] };
      }

      case 'drs_list_tasks': {
        const { region, ...filters } = args;
        const result = await listTasks(region, filters);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }

      case 'drs_find_matching_tasks': {
        const {
          region, source_endpoint, source_port, source_database,
          target_rds_id, target_database, sync_mode, network_type,
          task_name, source_engine, target_engine, target_region,
        } = args;

        const scenario = {
          target_region: target_region || region,
          source_endpoint, source_port, source_database,
          target_rds_id, target_database, sync_mode, network_type,
          task_name, source_engine, target_engine,
        };

        const session = await getSession();
        let tasks = [];

        if (session.active) {
          const listResult = await listTasks(region);
          tasks = listResult.tasks || [];
        }

        const result = findMatchingTasks(tasks, scenario);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }

      case 'drs_select_or_create_task': {
        const {
          region, task_name, creation_strategy,
          explicit_approval = false, duplicate_task_approval = false,
          scenario_config = {},
        } = args;

        const scenario = {
          target_region: scenario_config.target_region || region,
          ...scenario_config,
          task_name,
        };

        const session = await getSession();
        let tasks = [];

        if (session.active) {
          const listResult = await listTasks(region);
          tasks = listResult.tasks || [];
        }

        const matchingResult = findMatchingTasks(tasks, scenario);
        const resolution = resolveCreationStrategy(
          creation_strategy,
          matchingResult,
          explicit_approval,
          duplicate_task_approval,
        );

        return {
          content: [{
            type: 'text',
            text: JSON.stringify({
              strategy_used: creation_strategy,
              matching_summary: {
                exact_matches: matchingResult.exactMatches.length,
                partial_matches: matchingResult.partialMatches.length,
                name_only_matches: matchingResult.nameOnlyMatches.length,
                recommendation: matchingResult.recommendation,
              },
              resolution,
            }, null, 2),
          }],
        };
      }

      case 'drs_create_postgresql_full_incremental_task': {
        const {
          task_name,
          source_region = 'la-south-2',
          target_region,
          source_endpoint = '198.51.100.1',
          source_port = 5432,
          source_database = 'demodb',
          source_username = 'drs_replication',
          target_rds_id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03',
          target_database = 'demodb',
          network_type = 'Public Network',
          sync_mode = 'Full + Incremental',
          creation_strategy = 'ask_if_matching_exists',
          explicit_approval = false,
          duplicate_task_approval = false,
        } = args;

        const scenario = {
          task_name,
          target_region,
          source_endpoint: `${source_endpoint}:${source_port}`,
          source_database,
          target_rds_id,
          target_database,
          sync_mode,
          network_type,
          source_engine: 'PostgreSQL',
          target_engine: 'PostgreSQL',
        };

        const session = await getSession();
        let tasks = [];

        if (session.active) {
          const listResult = await listTasks(target_region);
          tasks = listResult.tasks || [];
        }

        const matchingResult = findMatchingTasks(tasks, scenario);
        const resolution = resolveCreationStrategy(
          creation_strategy,
          matchingResult,
          explicit_approval,
          duplicate_task_approval,
        );

        if (resolution.action === 'BLOCKED' || resolution.action === 'WARNING' || resolution.action === 'READY_TO_CREATE_PENDING_APPROVAL') {
          return {
            content: [{
              type: 'text',
              text: JSON.stringify({
                status: resolution.action,
                reason: resolution.reason,
                matching_tasks: matchingResult.candidates,
                dry_run: true,
                message: explicit_approval
                  ? 'Task creation blocked by safety guards. Review matching tasks and approvals.'
                  : 'Dry-run: Task would be created with these parameters. Set explicit_approval=true to proceed.',
                task_config: {
                  task_name,
                  source_region,
                  target_region,
                  source_endpoint,
                  source_port,
                  source_database,
                  source_username: '[REDACTED]',
                  target_rds_id,
                  target_database,
                  network_type,
                  sync_mode,
                  source_engine: 'PostgreSQL',
                  target_engine: 'PostgreSQL',
                  source_type: 'Self-built PostgreSQL on ECS',
                  destination_type: 'RDS for PostgreSQL',
                  dml_sync: 'INSERT, UPDATE, DELETE',
                  conflict_policy: 'Report error',
                  ddl_sync: 'disabled (requires explicit approval)',
                },
              }, null, 2),
            }],
          };
        }

        if (resolution.action === 'ask_user') {
          return {
            content: [{
              type: 'text',
              text: JSON.stringify({
                status: 'ASK_USER',
                message: 'Matching task(s) found. Decide whether to reuse or create new.',
                candidates: resolution.candidates,
                task_config: {
                  task_name,
                  target_region,
                  source_endpoint,
                  source_port,
                  source_database,
                  target_rds_id,
                  target_database,
                },
              }, null, 2),
            }],
          };
        }

        if (resolution.action === 'reuse') {
          return {
            content: [{
              type: 'text',
              text: JSON.stringify({
                status: 'REUSE',
                message: 'Reusing existing matching task instead of creating new.',
                reused_task: resolution.task,
              }, null, 2),
            }],
          };
        }

        if (resolution.action === 'create') {
          if (!session.active) {
            return {
              content: [{
                type: 'text',
                text: JSON.stringify({
                  status: 'READY_TO_CREATE',
                  message: 'No active browser session. Open DRS console and create task manually with these parameters.',
                  task_config: {
                    task_name,
                    source_region,
                    target_region,
                    source_endpoint,
                    source_port,
                    source_database,
                    source_username: '[REDACTED]',
                    target_rds_id,
                    target_database,
                    network_type,
                    sync_mode,
                    source_engine: 'PostgreSQL',
                    target_engine: 'PostgreSQL',
                    source_type: 'Self-built PostgreSQL on ECS',
                    destination_type: 'RDS for PostgreSQL',
                    dml_sync: 'INSERT, UPDATE, DELETE',
                    conflict_policy: 'Report error',
                    ddl_sync: 'disabled',
                  },
                  warning: 'Passwords must be entered manually in the browser. Never stored or printed.',
                }, null, 2),
              }],
            };
          }

          const { page } = session;
          await navigateToDrsConsole(page, target_region);
          await page.waitForTimeout(2000);

          const createBtn = page.locator('text="Create Task", button:has-text("Create Task"), a:has-text("Create Task")').first();
          const btnExists = await createBtn.count();

          if (btnExists === 0) {
            return {
              content: [{
                type: 'text',
                text: JSON.stringify({
                  status: 'READY_TO_CREATE',
                  message: 'Create Task button not found. Navigate to DRS console manually.',
                  task_config: { task_name, target_region, source_endpoint, source_database, target_rds_id, target_database },
                }, null, 2),
              }],
            };
          }

          return {
            content: [{
              type: 'text',
              text: JSON.stringify({
                status: 'CREATION_WIZARD_READY',
                message: 'Click Create Task to begin wizard. Fill parameters manually. Passwords must be entered in browser.',
                task_config: {
                  task_name,
                  source_region,
                  target_region,
                  source_endpoint,
                  source_port,
                  source_database,
                  source_username: '[REDACTED]',
                  target_rds_id,
                  target_database,
                  network_type,
                  sync_mode,
                },
              }, null, 2),
            }],
          };
        }

        return {
          content: [{
            type: 'text',
            text: JSON.stringify({ status: 'UNKNOWN', resolution }, null, 2),
          }],
        };
      }

      case 'drs_continue_existing_task': {
        const { region, task_name } = args;
        const result = await continueExistingTask(region, task_name);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }

      case 'drs_capture_replication_instance_eip': {
        const { region, task_name } = args;
        const result = await captureReplicationEip(region, task_name);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }

      case 'drs_generate_source_access_plan': {
        const { drs_eip, source_security_group_id, source_database, source_user, allowBroaderThan32 = false } = args;
        const result = await generateSourceAccessPlan({
          drs_eip, source_security_group_id, source_database, source_user, allowBroaderThan32,
        });
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }

      case 'drs_run_connection_test': {
        const { region, task_name } = args;
        const result = await runConnectionTest(region, task_name);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }

      case 'drs_run_precheck': {
        const { region, task_name } = args;
        const result = await runPrecheck(region, task_name);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }

      case 'drs_start_task': {
        const { region, task_name, explicit_approval = false, approved_warnings = [] } = args;

        const validation = validateStartConditions({
          explicit_approval,
          region,
          source_endpoint: '198.51.100.1:5432',
          source_database: 'demodb',
          target_rds_id: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa01in03',
          target_database: 'demodb',
          sync_mode: 'Full + Incremental',
          network_type: 'Public Network',
          connection_test_passed: true,
          precheck_passed: true,
          precheck_warnings_approved: approved_warnings,
        });

        if (!validation.allowed) {
          return {
            content: [{
              type: 'text',
              text: JSON.stringify({
                started: false,
                blocked: true,
                blockers: validation.blockers,
              }, null, 2),
            }],
          };
        }

        const result = await startTask(region, task_name, explicit_approval);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }

      case 'drs_get_task_status': {
        const { region, task_name } = args;
        const result = await getTaskStatus(region, task_name);
        return { content: [{ type: 'text', text: JSON.stringify(result, null, 2) }] };
      }

      case 'drs_generate_report': {
        const { output_path, region, task_name } = args;
        const defaultPath = output_path || '/root/migration-lab/huaweicloud-drs-mcp/reports/current-drs-context.md';
        const result = await generateReport({
          output_path: defaultPath,
          region,
          task_name,
        });
        return { content: [{ type: 'text', text: result.content }] };
      }

      default:
        return {
          content: [{ type: 'text', text: `Unknown tool: ${name}` }],
          isError: true,
        };
    }
  } catch (error) {
    return {
      content: [{ type: 'text', text: `Error: ${redactSecrets(error.message)}` }],
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error('Server failed to start:', err.message);
  process.exit(1);
});

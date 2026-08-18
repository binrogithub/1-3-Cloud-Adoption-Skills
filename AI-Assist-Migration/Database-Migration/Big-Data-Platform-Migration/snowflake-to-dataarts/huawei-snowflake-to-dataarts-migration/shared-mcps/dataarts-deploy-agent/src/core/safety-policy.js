const DEFAULT_SAFETY_POLICY = Object.freeze({
  no_publish: true,
  no_scheduled_start: true,
  no_start: true,
  no_delete: true,
  no_update: true,
  no_overwrite: true,
  only_run_immediate_for_execution: true,
  stop_on_critical_failure: true,
  abort_if_job_exists: true,
  no_secrets_printed: true,
});

function buildSafetyPolicy(overrides = {}) {
  return {
    ...DEFAULT_SAFETY_POLICY,
    ...overrides,
  };
}

module.exports = {
  DEFAULT_SAFETY_POLICY,
  buildSafetyPolicy,
};

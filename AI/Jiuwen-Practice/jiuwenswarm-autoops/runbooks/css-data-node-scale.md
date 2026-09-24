# CSS data-node scale Runbook

This Runbook is the E01 mutation boundary for the css_auto role.

It accepts only a registered CSS profile, a scale direction, a positive delta,
and the published policy step. The only node type is ess. Scale-out sends a
node delta with disk delta zero. Scale-in sends reducedNodeNum with vm mode and
cluster load checking enabled.

The Runbook requires the authenticated runbook-operator role and the explicit
AUTOOPS_CSS_MUTATION_ENABLED=1 deployment setting. A TUI sentence, MaaS
response, or CSS API HTTP 200 is not an approval or a final success.

The adapter returns SUBMITTED. The caller must reconcile the CSS cluster and
then invoke E09 to verify node topology, shard health and the registered
business probe.

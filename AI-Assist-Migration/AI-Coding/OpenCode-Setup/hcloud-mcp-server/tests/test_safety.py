from src.safety import (
    is_destructive_command,
    is_obs_command,
    is_obs_destructive_command,
    OBS_DESTRUCTIVE_WITH_DRYRUN,
    OBS_DESTRUCTIVE_NO_DRYRUN,
)


class TestIsDestructiveCommand:
    def test_help_is_not_destructive(self):
        assert is_destructive_command("--help") is False
        assert is_destructive_command("IAM --help") is False
        assert is_destructive_command("IAM DeleteCustomPolicy --help") is False

    def test_read_operations_not_destructive(self):
        assert is_destructive_command("IAM ListCustomPolicies") is False
        assert is_destructive_command("ECS NovaListServers") is False
        assert is_destructive_command("VPC ListVpcs") is False

    def test_delete_is_destructive(self):
        assert is_destructive_command("IAM DeleteCustomPolicy --role_id=abc") is True

    def test_detach_is_destructive(self):
        assert is_destructive_command("IAM DetachUserPolicyV5 --policy_id=abc") is True

    def test_revoke_is_destructive(self):
        assert is_destructive_command("IAM RevokeRoleFromUserOnEnterpriseProject") is True

    def test_create_is_not_destructive(self):
        assert is_destructive_command("IAM CreateCloudServiceCustomPolicy") is False

    def test_force_is_destructive(self):
        assert is_destructive_command("ECS ForceDelete") is True


class TestIsObsCommand:
    def test_obs_lowercase(self):
        assert is_obs_command("obs ls") is True

    def test_obs_uppercase(self):
        assert is_obs_command("OBS ls") is True

    def test_non_obs(self):
        assert is_obs_command("IAM ListCustomPolicies") is False

    def test_obs_with_flags(self):
        assert is_obs_command("obs ls --cli-region=la-north-2") is True

    def test_empty(self):
        assert is_obs_command("") is False


class TestIsObsDestructiveCommand:
    def test_obs_ls_not_destructive(self):
        is_dest, supports_dry = is_obs_destructive_command("obs ls")
        assert is_dest is False
        assert supports_dry is False

    def test_obs_stat_not_destructive(self):
        is_dest, supports_dry = is_obs_destructive_command("obs stat obs://bucket/key")
        assert is_dest is False

    def test_obs_cp_destructive_with_dryrun(self):
        is_dest, supports_dry = is_obs_destructive_command("obs cp file.txt obs://bucket/key")
        assert is_dest is True
        assert supports_dry is True

    def test_obs_mv_destructive_with_dryrun(self):
        is_dest, supports_dry = is_obs_destructive_command("obs mv obs://src/key obs://dst/key")
        assert is_dest is True
        assert supports_dry is True

    def test_obs_sync_destructive_with_dryrun(self):
        is_dest, supports_dry = is_obs_destructive_command("obs sync ./dir obs://bucket/prefix")
        assert is_dest is True
        assert supports_dry is True

    def test_obs_rm_destructive_no_dryrun(self):
        is_dest, supports_dry = is_obs_destructive_command("obs rm obs://bucket/key")
        assert is_dest is True
        assert supports_dry is False

    def test_obs_abort_destructive_no_dryrun(self):
        is_dest, supports_dry = is_obs_destructive_command("obs abort obs://bucket/key -u=xxx")
        assert is_dest is True
        assert supports_dry is False

    def test_obs_mb_destructive_no_dryrun(self):
        is_dest, supports_dry = is_obs_destructive_command("obs mb obs://new-bucket")
        assert is_dest is True
        assert supports_dry is False

    def test_obs_chattri_destructive_no_dryrun(self):
        is_dest, supports_dry = is_obs_destructive_command("obs chattri obs://bucket -acl=private")
        assert is_dest is True
        assert supports_dry is False

    def test_obs_bucketpolicy_destructive_no_dryrun(self):
        is_dest, supports_dry = is_obs_destructive_command("obs bucketpolicy obs://bucket")
        assert is_dest is True
        assert supports_dry is False

    def test_obs_lifecycle_destructive_no_dryrun(self):
        is_dest, supports_dry = is_obs_destructive_command("obs lifecycle obs://bucket")
        assert is_dest is True
        assert supports_dry is False

    def test_non_obs_command(self):
        is_dest, supports_dry = is_obs_destructive_command("IAM DeleteCustomPolicy")
        assert is_dest is False
        assert supports_dry is False

    def test_obs_help_not_destructive(self):
        is_dest, supports_dry = is_obs_destructive_command("obs help ls")
        assert is_dest is False

    def test_obs_config_not_destructive(self):
        is_dest, supports_dry = is_obs_destructive_command("obs config -i=xxx -k=xxx")
        assert is_dest is False

    def test_obs_version_not_destructive(self):
        is_dest, supports_dry = is_obs_destructive_command("obs version")
        assert is_dest is False

    def test_obs_rm_with_flags(self):
        is_dest, supports_dry = is_obs_destructive_command("obs rm obs://bucket/key -f --cli-region=la-north-2")
        assert is_dest is True
        assert supports_dry is False

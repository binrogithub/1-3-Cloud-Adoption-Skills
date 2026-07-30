import re

DESTRUCTIVE_PATTERNS = [
    "Delete", "Remove", "Revoke", "Detach",
    "Disassociate", "Cancel", "Force",
]

OBS_DESTRUCTIVE_WITH_DRYRUN = {"cp", "mv", "sync"}
OBS_DESTRUCTIVE_NO_DRYRUN = {"rm", "abort", "mb", "chattri", "bucketpolicy", "lifecycle"}
OBS_DESTRUCTIVE_ALL = OBS_DESTRUCTIVE_WITH_DRYRUN | OBS_DESTRUCTIVE_NO_DRYRUN


def is_destructive_command(command: str) -> bool:
    if "--help" in command:
        return False
    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern in command:
            return True
    return False


def _extract_obs_subcommand(command: str) -> str | None:
    args = command.split()
    found_obs = False
    for arg in args:
        if not found_obs:
            if arg.lower() == "obs":
                found_obs = True
            continue
        if arg.startswith("-"):
            continue
        return arg
    return None


def is_obs_command(command: str) -> bool:
    args = command.split()
    for arg in args:
        if arg.startswith("-"):
            continue
        return arg.lower() == "obs"
    return False


def is_obs_destructive_command(command: str) -> tuple[bool, bool]:
    """Returns (is_destructive, supports_dryrun)."""
    if not is_obs_command(command):
        return False, False

    subcmd = _extract_obs_subcommand(command)
    if subcmd is None:
        return False, False

    if subcmd in OBS_DESTRUCTIVE_WITH_DRYRUN:
        return True, True
    if subcmd in OBS_DESTRUCTIVE_NO_DRYRUN:
        return True, False
    return False, False

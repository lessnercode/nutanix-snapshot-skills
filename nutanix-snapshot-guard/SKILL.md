---
name: nutanix-snapshot-guard
description: Install or configure the Lab 06 hook that snapshots an AHV VM before destructive Claude Code or OpenCode tool calls.
---
<!-- Shared hook installation for Lab 06. -->

# Nutanix snapshot guard

The guard takes a recovery point before a destructive Nutanix VM tool call, then allows the call. For Nutanix MCP `<namespace>_execute` tools, the guard checks the `operation` argument only in namespaces containing `vmm`, such as `vmm_execute` with `powerOffVm`. For MCP servers with one tool per action, it checks the tool name. Both checks match delete, remove, power off, shutdown, reboot, reset, update, disk, detach, migrate, revert, or restore regardless of case. Discovery tools are exempt. Shell detection covers `acli vm.delete`, `vm.off`, `vm.shutdown`, `vm.reboot`, `vm.disk_delete`, `vm.update`, `vm.disk_update`, and HTTP DELETE, PUT, or POST to VMM VM paths. The snapshot script's own commands are exempt.

The guard also covers software updates and package changes made with `apt`, `apt-get`, `dnf`, `yum`, `zypper`, `snap`, `do-release-upgrade`, `unattended-upgrade`, and `unattended-upgrades`. APT index refreshes (`apt update` and `apt-get update`) are exempt. Over `ssh`, the same shell rules apply and the SSH hostname identifies the VM to snapshot. For local package commands, the guard uses `NTNX_SELF_VM` if set. Otherwise, it checks the DMI system vendor, then uses the product UUID on Nutanix hosts or the hostname if the UUID is unavailable. The guard allows the command if it cannot read the vendor or the vendor does not contain `Nutanix`.

Install `nutanix-snapshot` beside the guard or set `NTNX_SNAPSHOT_SCRIPT` to its Python entry point. Configure the environment in the [snapshot skill](../nutanix-snapshot/SKILL.md). The guard blocks the call if it cannot confirm the target VM (including a "not found" result, exit `3`) or if snapshot creation fails. Set `NTNX_GUARD_FAIL_OPEN=1` to allow calls after those failures, including missing environment configuration.

| Variable | Value |
| --- | --- |
| `NTNX_SELF_VM` | Optional VM name or extId for the host running the guard. Takes precedence over local VM detection. |

The hook is a client-side safety net. Attendees can edit or remove it. The API key's role (RBAC) controls which actions Prism Central permits, including deletion.

## Claude Code

From the repository root, copy the skills into the project's Claude Code skills directory.

```sh
mkdir -p .claude/skills
cp -R lab06/skills/nutanix-snapshot lab06/skills/nutanix-snapshot-guard .claude/skills/
```

Merge this block into the project's `.claude/settings.json`. The same block is in `claude-code/settings.example.json`.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|mcp__.*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/skills/nutanix-snapshot-guard/scripts/guard.py\"",
            "timeout": 240
          }
        ]
      }
    ]
  }
}
```

## OpenCode

From the repository root, copy the skills and the OpenCode plugin into the project.

```sh
mkdir -p .opencode/skills .opencode/plugins
cp -R lab06/skills/nutanix-snapshot lab06/skills/nutanix-snapshot-guard .opencode/skills/
cp lab06/skills/nutanix-snapshot-guard/opencode/snapshot-guard.ts .opencode/plugins/
```

The plugin uses `NTNX_GUARD_SCRIPT` if set, then checks the installed guard under `.opencode/skills/`, then `.claude/skills/`. It uses the OpenCode `tool.execute.before` hook.

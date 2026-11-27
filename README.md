# Nutanix snapshot skills

> **In testing.** Built for a hands-on lab. Live checks so far used one Prism Central, the Claude Code hook (matched to Nutanix MCP tools only) and the Nutanix API MCP server, with `NTNX_VMM_VERSION=v4.3`, `NTNX_DP_VERSION=v4.4` and `NTNX_PRISM_VERSION=v4.4`. The `v4.0` defaults have not been tested live.
>
> - **Passed:** a recovery point before `updateVmById` (the update used an invalid ETag so it would be rejected), using the VM's own project (one project tested); blocking when the VM lookup returns "not found"; blocking when recovery point creation fails (tested before the two guard and project fixes).
> - **Not tested live:** restore, delete, power off, a second project, the OpenCode plugin and the shell command checks.
> - **Known from the code:** with the `Bash` matcher, a command with an unmatched quote (for example a heredoc containing `isn't`) is blocked.

Two agent skills for Claude Code and OpenCode that take Nutanix recovery points (local snapshots) of AHV VMs before an agent does something risky.

| Skill | What it does |
|---|---|
| [`nutanix-snapshot`](nutanix-snapshot/SKILL.md) | Take, list and restore recovery points for one VM through the Prism Central v4 API. No category or protection policy needed. |
| [`nutanix-snapshot-guard`](nutanix-snapshot-guard/SKILL.md) | A pre-tool hook. Before a destructive action on a Nutanix VM (delete, power off, disk or config change, OS package update), it takes a recovery point, then lets the action run. If the snapshot fails, the action is blocked. |

Python 3 standard library only. Prism Central v4 APIs only.

## Quick start

```bash
export NTNX_PC_HOST=<prism-central-host>
export NTNX_API_KEY=<service-account-api-key>

python3 nutanix-snapshot/scripts/ntnx_snapshot.py --dry-run --offline take --vm test-04 --reason resize
python3 nutanix-snapshot/scripts/ntnx_snapshot.py take --vm test-04 --reason resize
python3 nutanix-snapshot-guard/scripts/test_guard.py
(cd nutanix-snapshot-guard/scripts && python3 -B -m unittest test_guard_main)
(cd nutanix-snapshot/scripts && python3 -B -m unittest test_project)
```

Each recovery point is created with the VM's own `projectExtId`. The guard blocks the action if it can't confirm the target VM.

Install steps for the Claude Code hook and the OpenCode plugin are in [`nutanix-snapshot-guard/SKILL.md`](nutanix-snapshot-guard/SKILL.md).

## What the guard catches

- Nutanix MCP tools whose name contains a destructive word, and the [Nutanix API MCP server](https://github.com/nutanix/ntnx-api-mcp-server)'s `vmm` `<namespace>_execute` calls, read from the `operation` argument (for example `deleteVmById`, `powerOffVm`).
- `acli vm.delete`, `vm.off`, `vm.update` and similar, and curl DELETE, PUT or POST to a VMM `/vms/` path.
- OS package changes (`apt`, `dnf`, `yum`, `zypper`, `snap`, `do-release-upgrade`) on the agent's own VM, or on another VM over `ssh`.

The guard is a client-side safety net, not a security control. Anyone with access to the machine can edit or remove it. What the agent is allowed to do is decided by the API key's role in Prism Central.

## Permissions the API key needs

View Virtual Machine, Create / View / Restore VM Recovery Point, Create Virtual Machine (restore makes a new VM), plus whatever VM actions the agent is meant to take. Recovery points stay in the VM's project on pc.7.6 with AOS 7.6.

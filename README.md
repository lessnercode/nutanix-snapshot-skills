# Nutanix snapshot skills

> **In testing.** Built for a hands-on lab and checked offline only (dry runs and a classifier self-check). Not yet run against a live Prism Central. The v4 API version segment, request body fields and API key header name still need confirming on a real cluster.

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
export NTNX_PROJECT_EXT_ID=<project-uuid>   # otherwise recovery points land in the Default Project

python3 nutanix-snapshot/scripts/ntnx_snapshot.py --dry-run --offline take --vm test-04 --reason resize
python3 nutanix-snapshot/scripts/ntnx_snapshot.py take --vm test-04 --reason resize
python3 nutanix-snapshot-guard/scripts/test_guard.py
```

Install steps for the Claude Code hook and the OpenCode plugin are in [`nutanix-snapshot-guard/SKILL.md`](nutanix-snapshot-guard/SKILL.md).

## What the guard catches

- Nutanix MCP tools whose name contains a destructive word, and the [Nutanix API MCP server](https://github.com/nutanix/ntnx-api-mcp-server)'s `vmm` `<namespace>_execute` calls, read from the `operation` argument (for example `deleteVmById`, `powerOffVm`).
- `acli vm.delete`, `vm.off`, `vm.update` and similar, and curl DELETE, PUT or POST to a VMM `/vms/` path.
- OS package changes (`apt`, `dnf`, `yum`, `zypper`, `snap`, `do-release-upgrade`) on the agent's own VM, or on another VM over `ssh`.

The guard is a client-side safety net, not a security control. Anyone with access to the machine can edit or remove it. What the agent is allowed to do is decided by the API key's role in Prism Central.

## Permissions the API key needs

View Virtual Machine, Create / View / Restore VM Recovery Point, Create Virtual Machine (restore makes a new VM), plus whatever VM actions the agent is meant to take. Recovery points stay in the VM's project on pc.7.6 with AOS 7.6.

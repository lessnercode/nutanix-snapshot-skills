---
name: nutanix-snapshot
description: Take a Nutanix recovery point before any risky AHV VM change, or use one to undo a change.
---
<!-- Recovery point workflow for Lab 06. -->

# Nutanix snapshot

Take a local, crash-consistent recovery point before powering off a VM, resizing it down, changing or detaching disks, deleting it, or making any other risky change. Wait for `take` to succeed before acting. If the change goes wrong, restore the recovery point.

Restore creates a new VM and leaves the original in place. After confirming the new VM is usable, delete the broken original. If the API key's role denies deletion, power off the broken original and rename it.

Claude Code and OpenCode both read this skill. The script uses Python 3 and Prism Central v4. Run the examples from this skill's directory.

## Environment

| Variable | Value |
| --- | --- |
| `NTNX_PC_HOST` | Required Prism Central hostname or IP. Port `9440` is assumed unless supplied. |
| `NTNX_API_KEY` | Required project-scoped service account API key. |
| `NTNX_API_KEY_HEADER` | API key header name. Defaults to `X-ntnx-api-key`. Confirm the name on the lab PC. |
| `NTNX_DP_VERSION` | Data Protection API version. Defaults to `v4.0`. |
| `NTNX_VMM_VERSION` | VMM API version. Defaults to `v4.0`. |
| `NTNX_PRISM_VERSION` | Prism task API version. Defaults to `v4.0`. |
| `NTNX_INSECURE` | Set to `1` to skip TLS verification for the lab's self-signed certificate. |
| `NTNX_RP_TTL_HOURS` | Recovery point lifetime in hours. Defaults to `168` (1 week). |

## Commands

`take` reads the VM and sends its own `projectExtId` with the recovery point. If the VM read shows no project, it sends none and prints a warning. There is no project setting to configure.

`resolve --vm <name-or-extId>` prints the VM extId, name and projectExtId as JSON.

```sh
python3 scripts/ntnx_snapshot.py resolve --vm test-04
```

`take --vm <name-or-extId> [--reason "<text>"]` creates a recovery point and waits for the task.

```sh
python3 scripts/ntnx_snapshot.py take --vm test-04 --reason resize
```

`list --vm <name-or-extId>` prints the VM's recovery points as JSON lines, newest first.

```sh
python3 scripts/ntnx_snapshot.py list --vm test-04
```

`restore --rp <recoveryPointExtId> [--vm <name-or-extId>]` restores the matching VM and waits for the task. Omit `--vm` to use the first VM in the recovery point.

```sh
python3 scripts/ntnx_snapshot.py restore --rp 12345678-abcd-1234-abcd-123456789abc --vm test-04
```

Put `--dry-run` before the subcommand to print method, URL, redacted headers, and body while skipping writes. Reads still run. Add `--offline` for `resolve` or `take` to skip reads and use the VM input as both name and extId.

```sh
NTNX_PC_HOST=pc.example NTNX_API_KEY=x python3 scripts/ntnx_snapshot.py --dry-run --offline take --vm test-04 --reason resize
```

Exit codes are `0` for success, `1` for an API or task failure, `2` for a usage or environment error, and `3` when the VM is absent.

# Check the guard classifier without invoking Prism Central.
from guard import classify


def main():
    uuid = "12345678-abcd-1234-abcd-123456789abc"
    disk_uuid = "87654321-abcd-1234-abcd-123456789abc"
    cases = [
        ("mcp__nutanix__delete_vm", {"extId": uuid}, {"vm": uuid, "action": "delete_vm"}),
        ("nutanix_vm_power_off", {"vmName": "web-01"}, {"vm": "web-01", "action": "vm_power_off"}),
        ("mcp__nutanix__list_vms", {}, None),
        ("mcp__github__delete_repo", {}, None),
        (
            "mcp__nutanix__vmm_execute",
            {"operation": "deleteVmById", "extId": uuid},
            {"vm": uuid, "action": "deleteVmById"},
        ),
        (
            "nutanix_vmm_execute",
            {"operation": "powerOffVm", "extId": uuid},
            {"vm": uuid, "action": "powerOffVm"},
        ),
        (
            "mcp__nutanix__vmm_execute",
            {"operation": "deleteDiskById", "vmExtId": uuid, "extId": disk_uuid},
            {"vm": uuid, "action": "deleteDiskById"},
        ),
        ("mcp__nutanix__vmm_execute", {"operation": "listVms"}, None),
        (
            "mcp__nutanix__dataprotection_execute",
            {"operation": "deleteRecoveryPointById", "extId": uuid},
            None,
        ),
        ("mcp__nutanix__listOperations", {}, None),
        ("Bash", {"command": "acli vm.delete web-01"}, {"vm": "web-01", "action": "vm.delete"}),
        (
            "Bash",
            {"command": f"curl -X DELETE https://pc/api/vmm/v4.0/ahv/config/vms/{uuid}"},
            {"vm": uuid, "action": "delete"},
        ),
        ("Bash", {"command": "ls -la"}, None),
        ("Bash", {"command": "python3 scripts/ntnx_snapshot.py take --vm web-01"}, None),
        ("Bash", {"command": "sudo apt-get -y upgrade"}, {"vm": "@self", "action": "apt-get upgrade"}),
        ("Bash", {"command": "apt update"}, None),
        ("Bash", {"command": "dnf install -y nginx"}, {"vm": "@self", "action": "dnf install"}),
        ("Bash", {"command": "snap refresh"}, {"vm": "@self", "action": "snap refresh"}),
        ("Bash", {"command": "do-release-upgrade"}, {"vm": "@self", "action": "do-release-upgrade"}),
        (
            "Bash",
            {"command": "ssh -i key.pem admin@web-01 'sudo apt upgrade -y'"},
            {"vm": "web-01", "action": "apt upgrade"},
        ),
        ("Bash", {"command": "ssh web-01 uptime"}, None),
        ("Bash", {"command": "ssh web-01"}, None),
        ("Bash", {"command": "apt list --upgradable"}, None),
    ]
    for tool, tool_input, expected in cases:
        actual = classify(tool, tool_input)
        assert actual == expected, (tool, tool_input, expected, actual)
    print(f"{len(cases)} classifier checks passed")


if __name__ == "__main__":
    main()

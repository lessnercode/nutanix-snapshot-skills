# Gate destructive Nutanix VM tool calls on a recovery point.
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
from urllib.parse import urlsplit


DESTRUCTIVE = re.compile(r"delete|remove|power_off|poweroff|shutdown|reboot|reset|update|disk|detach|migrate|revert|restore", re.I)
ACLI = re.compile(r"vm\.(?:delete|off|shutdown|reboot|disk_delete|update|disk_update)")
VM_PATH = re.compile(r"/vms/([0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})(?:/|$)", re.I)
VM_KEYS = ("vmExtId", "vm_ext_id", "vmId", "vm_id", "extId", "uuid", "name", "vmName", "vm_name", "vm")
WRITE_METHODS = {"DELETE", "PUT", "POST"}
APT_ACTIONS = {"upgrade", "dist-upgrade", "full-upgrade", "install", "remove", "purge", "autoremove"}
RPM_ACTIONS = {"update", "upgrade", "install", "remove", "erase", "distro-sync", "downgrade"}
PACKAGE_ACTIONS = {
    "apt": APT_ACTIONS,
    "apt-get": APT_ACTIONS,
    "dnf": RPM_ACTIONS,
    "yum": RPM_ACTIONS,
    "zypper": {"update", "up", "dist-upgrade", "dup", "install", "in", "remove", "rm", "patch"},
    "snap": {"refresh", "install", "remove"},
}
OS_UPGRADERS = {"do-release-upgrade", "unattended-upgrade", "unattended-upgrades"}
SSH_VALUE_OPTIONS = {"-i", "-p", "-l", "-o", "-J", "-F", "-b", "-c", "-E", "-L", "-R", "-D", "-W", "-S", "-m", "-e"}


def shell_action(words):
    for index, word in enumerate(words):
        executable = word.rsplit("/", 1)[-1]
        args = words[index + 1:]
        if executable == "ntnx_snapshot.py":
            return None
        if re.fullmatch(r"python(?:3(?:\.\d+)?)?", executable):
            script = next((arg for arg in args if not arg.startswith("-")), "")
            if script.rsplit("/", 1)[-1] == "ntnx_snapshot.py":
                return None
        if executable == "ssh":
            ssh_args = iter(args)
            for arg in ssh_args:
                if arg in SSH_VALUE_OPTIONS:
                    next(ssh_args, None)
                elif not arg.startswith("-"):
                    action = classify_shell(" ".join(ssh_args))
                    if action:
                        action["vm"] = arg.rsplit("@", 1)[-1]
                    return action
            return None
        if executable in PACKAGE_ACTIONS:
            subcommand = next((arg for arg in args if not arg.startswith("-")), None)
            if subcommand in PACKAGE_ACTIONS[executable]:
                return {"vm": "@self", "action": f"{executable} {subcommand}"}
        if executable in OS_UPGRADERS:
            return {"vm": "@self", "action": executable}
        if executable == "acli" and args and ACLI.fullmatch(args[0]):
            return {"vm": args[1] if len(args) > 1 else None, "action": args[0]}
        if executable not in {"curl", "http", "https"}:
            continue
        method = None
        implied = None
        for position, arg in enumerate(args):
            if arg in {"-X", "--request"}:
                method = args[position + 1] if position + 1 < len(args) else None
            elif arg.startswith(("-X", "--request=")):
                method = arg[2:] if arg.startswith("-X") else arg.split("=", 1)[1]
            elif executable != "curl" and position == 0:
                method = arg
            elif arg in {"-T", "--upload-file"} or arg.startswith("--upload-file="):
                implied = "PUT"
            elif arg.startswith(("-d", "--data", "--json")) and implied is None:
                implied = "POST"
        method = (method or implied or "").upper()
        if method in WRITE_METHODS:
            for arg in args:
                path = urlsplit(arg).path
                if "/vmm/" in path and "/vms/" in path:
                    match = VM_PATH.search(path)
                    return {"vm": match[1] if match else None, "action": method.lower()}
    return None


def classify_shell(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    words = []
    for word in lexer:
        if word and all(char in ";&|()\n" for char in word):
            action = shell_action(words)
            if action:
                return action
            words = []
        else:
            words.append(word)
    return shell_action(words)


def classify(tool, tool_input):
    tool = tool.lower()
    if tool == "bash":
        return classify_shell(tool_input.get("command", ""))

    if tool.startswith("mcp__"):
        parts = tool.split("__", 2)
        if len(parts) != 3 or not re.search(r"nutanix|ntnx", parts[1]):
            return None
        operation = parts[2]
    else:
        match = re.match(r".*?(?:nutanix|ntnx)[^_]*_(.+)", tool)
        if not match:
            return None
        operation = match[1]
    if operation.endswith("_execute"):
        namespace = operation[:-len("_execute")]
        if "vmm" not in namespace:
            return None
        operation = tool_input.get("operation")
        if not isinstance(operation, str):
            return None
    if DESTRUCTIVE.search(operation):
        vm = next((tool_input[key] for key in VM_KEYS if key in tool_input), None)
        return {"vm": vm, "action": operation}
    return None


def self_vm():
    configured = os.getenv("NTNX_SELF_VM")
    if configured:
        return configured
    dmi = Path("/sys/class/dmi/id")
    try:
        if "nutanix" not in (dmi / "sys_vendor").read_text().lower():
            return None
    except (OSError, UnicodeError):
        return None
    # ponytail: AHV SMBIOS UUID == VM extId assumed; set NTNX_SELF_VM in the sandbox template to skip the guess.
    try:
        product_uuid = (dmi / "product_uuid").read_text().strip().lower()
    except (OSError, UnicodeError):
        product_uuid = ""
    return product_uuid or socket.gethostname()


def main():
    try:
        payload = json.load(sys.stdin)
        action = classify(
            payload.get("tool", payload.get("tool_name")),
            payload.get("input", payload.get("tool_input", {})),
        )
        if not action:
            return 0
        vm = action["vm"]
        if vm == "@self":
            vm = self_vm()
            if vm is None:
                return 0
        if not isinstance(vm, str) or not vm.strip():
            raise ValueError("Could not identify the VM targeted by the destructive action")
        default_script = Path(__file__).resolve().parents[2] / "nutanix-snapshot/scripts/ntnx_snapshot.py"
        script = os.getenv("NTNX_SNAPSHOT_SCRIPT") or str(default_script)
        command = [sys.executable, script]
        resolved = subprocess.run(command + ["resolve", "--vm", vm], capture_output=True, text=True)
        if resolved.returncode == 3:
            # "Not found" can also mean a wrong API version or path, so never allow it.
            raise RuntimeError(f"Could not confirm target VM {vm!r}: the VM lookup returned not found")
        if resolved.returncode:
            raise RuntimeError(resolved.stderr.strip() or f"resolve exited {resolved.returncode}")
        vm_id = json.loads(resolved.stdout)["extId"]
        taken = subprocess.run(
            command + ["take", "--vm", vm_id, "--reason", action["action"]],
            capture_output=True, text=True,
        )
        if taken.returncode:
            raise RuntimeError(taken.stderr.strip() or f"take exited {taken.returncode}")
        print(f"Recovery point taken for {vm} before {action['action']}.", file=sys.stderr)
        return 0
    except (AttributeError, KeyError, OSError, TypeError, ValueError, RuntimeError) as error:
        if os.getenv("NTNX_GUARD_FAIL_OPEN") == "1":
            print(f"Snapshot guard allowing action after failure: {error}", file=sys.stderr)
            return 0
        print(f"Snapshot guard blocked action: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

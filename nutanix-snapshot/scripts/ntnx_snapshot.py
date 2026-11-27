# Manage one AHV VM's recovery points through Prism Central v4.
import argparse
from datetime import datetime, timedelta, timezone
import json
import os
import re
import ssl
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen
import uuid


def resolve(request, vms, vm, offline):
    if offline:
        return {"extId": vm, "name": vm}
    if re.fullmatch(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", vm, re.I):
        try:
            match = request("GET", f"{vms}/{vm}").get("data")
        except HTTPError as error:
            if error.code != 404:
                raise
            match = None
    else:
        escaped = vm.replace("'", "''")
        query = urlencode({"$filter": f"name eq '{escaped}'"})
        matches = request("GET", f"{vms}?{query}").get("data") or []
        if len(matches) > 1:
            raise RuntimeError(f"Multiple VMs named {vm!r}. Use a VM extId.")
        match = matches[0] if matches else None
        if match:  # read the full record so the project is not missed
            match = request("GET", f"{vms}/{match['extId']}")["data"]
    if not match:
        return None
    project = match.get("projectExtId") or (match.get("project") or {}).get("extId")
    return {"extId": match["extId"], "name": match["name"], "projectExtId": project}


def wait_for_task(request, tasks, task_id):
    path = f"{tasks}/{quote(task_id, safe='')}"
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        task = request("GET", path, timeout=min(15, deadline - time.monotonic()))["data"]
        status = task["status"]
        if status == "SUCCEEDED":
            return task
        if status in {"FAILED", "CANCELED"}:
            raise RuntimeError(f"Task {task_id} {status}")
        time.sleep(max(0, min(3, deadline - time.monotonic())))
    raise RuntimeError(f"Task {task_id} timed out after 180 seconds")


def list_points(request, path, vm_id):
    matches = []
    seen = 0
    page = 0
    while True:
        response = request("GET", path if page == 0 else f"{path}?%24page={page}")
        points = response.get("data") or []
        matches.extend(
            point for point in points
            if any(vm.get("vmExtId") == vm_id for vm in point.get("vmRecoveryPoints") or [])
        )
        seen += len(points)
        metadata = response.get("metadata") or {}
        if not points or seen >= (metadata.get("totalAvailableResults") or 0):
            break
        page += 1
    fields = ("extId", "name", "creationTime", "expirationTime")
    for point in sorted(matches, key=lambda item: datetime.fromisoformat(
        item["creationTime"].replace("Z", "+00:00")
    ), reverse=True):
        print(json.dumps({field: point.get(field) for field in fields}))


def main():
    parser = argparse.ArgumentParser(description="Manage AHV VM recovery points.")
    parser.add_argument("--dry-run", action="store_true", help="Print requests and skip writes.")
    parser.add_argument("--offline", action="store_true", help="Skip reads in a dry run.")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("resolve", "take", "list"):
        subcommand = commands.add_parser(command)
        subcommand.add_argument("--vm", required=True)
        if command == "take":
            subcommand.add_argument("--reason", default="snapshot")
    restore = commands.add_parser("restore")
    restore.add_argument("--rp", required=True)
    restore.add_argument("--vm")
    args = parser.parse_args()
    if args.offline and not args.dry_run:
        parser.error("--offline requires --dry-run")
    if args.offline and args.command in {"list", "restore"}:
        parser.error(f"{args.command} requires live recovery point data")

    host = os.getenv("NTNX_PC_HOST")
    key = os.getenv("NTNX_API_KEY")
    if not host or not key:
        parser.error("Set NTNX_PC_HOST and NTNX_API_KEY")
    try:
        if host.count(":") > 1 and not host.startswith("["):
            host = f"[{host}]"
        address = urlsplit(f"https://{host}")
        if not address.hostname or address.username or address.path or address.query or address.fragment:
            raise ValueError
        base = f"https://{host}" if address.port is not None else f"https://{host}:9440"
    except ValueError:
        parser.error("NTNX_PC_HOST must be a host or IP with an optional port")

    header = os.getenv("NTNX_API_KEY_HEADER", "X-ntnx-api-key")
    context = ssl._create_unverified_context() if os.getenv("NTNX_INSECURE") == "1" else None
    versions = [os.getenv(f"NTNX_{api}_VERSION", "v4.0") for api in ("VMM", "DP", "PRISM")]
    if any(not re.fullmatch(r"v4\.\d+(?:\.[a-z]\d+)?", version) for version in versions):
        parser.error("API versions must be v4 version segments")
    vms = f"/api/vmm/{versions[0]}/ahv/config/vms"
    recovery_points = f"/api/dataprotection/{versions[1]}/config/recovery-points"
    tasks = f"/api/prism/{versions[2]}/config/tasks"
    if args.command == "take":
        try:
            ttl = timedelta(hours=float(os.getenv("NTNX_RP_TTL_HOURS", "168")))
            expires = datetime.now(timezone.utc) + ttl
            if ttl <= timedelta(0):
                raise ValueError
        except (ValueError, OverflowError):
            parser.error("NTNX_RP_TTL_HOURS must be a positive number of hours")

    def request(method, path, body=None, timeout=15):
        url = base + path
        headers = {"Accept": "application/json"}
        if body is not None:
            headers.update({"Content-Type": "application/json", "NTNX-Request-Id": str(uuid.uuid4())})
        if args.dry_run:
            print(json.dumps({
                "method": method, "url": url, "headers": {**headers, header: "[REDACTED]"}, "body": body,
            }))
            if method != "GET":
                return None
        data = json.dumps(body).encode() if body is not None else None
        req = Request(url, data=data, headers=headers, method=method)
        req.add_unredirected_header(header, key)
        with urlopen(req, context=context, timeout=timeout) as response:
            return json.load(response)

    try:
        vm = resolve(request, vms, args.vm, args.offline) if args.vm else None
        if args.vm and not vm:
            print(f"VM {args.vm!r} was not found", file=sys.stderr)
            return 3
        if args.command == "resolve":
            print(json.dumps(vm))
            return 0
        if args.command == "list":
            list_points(request, recovery_points, vm["extId"])
            return 0

        result = {}
        # ponytail: field names follow the v4 docs as read 2026-11-26; confirm with listOperations on the lab PC.
        if args.command == "take":
            slug = re.sub(r"[^a-z0-9]+", "-", args.reason.lower()).strip("-") or "snapshot"
            now = expires - ttl
            name = f"{vm['name']}-{slug}-{now:%Y%m%d%H%M%S}"
            body = {
                "name": name,
                "expirationTime": expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "recoveryPointType": "CRASH_CONSISTENT",
                "vmRecoveryPoints": [{"vmExtId": vm["extId"]}],
            }
            # The recovery point always follows the VM's own project.
            if vm.get("projectExtId"):
                body["projectExtId"] = vm["projectExtId"]
            else:
                print("Warning: no project found for this VM. Sending no projectExtId.", file=sys.stderr)
            path = recovery_points
            result["name"] = name
        else:
            path = f"{recovery_points}/{quote(args.rp, safe='')}"
            point = request("GET", path)["data"]
            entries = point.get("vmRecoveryPoints") or []
            entry = next((item for item in entries if not vm or item.get("vmExtId") == vm["extId"]), None)
            if not entry or not entry.get("extId"):
                raise RuntimeError("Recovery point has no matching VM recovery point extId")
            body = {"vmRecoveryPointRestoreOverrides": [{"vmRecoveryPointExtId": entry["extId"]}]}
            path += "/$actions/restore"
            result["name"] = point.get("name")
            result["extId"] = args.rp

        response = request("POST", path, body)
        if args.dry_run:
            return 0
        task_id = response["data"]["extId"]
        task = wait_for_task(request, tasks, task_id)
        result["taskExtId"] = task_id
        if args.command == "take":
            for entity in task.get("entitiesAffected") or []:
                kind = re.sub(r"[^a-z]", "", (entity.get("rel") or "").rsplit(":", 1)[-1].lower())
                if entity.get("extId") and (kind == "recoverypoint" or entity.get("name") == result["name"]):
                    result["extId"] = entity["extId"]
                    break
        print(json.dumps(result))
        return 0
    except (URLError, OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f"Snapshot request failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

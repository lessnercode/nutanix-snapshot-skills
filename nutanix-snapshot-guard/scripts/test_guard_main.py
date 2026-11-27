# Check allow/block decisions with a simulated snapshot script. No network calls.
import io
import json
import os
import subprocess
import unittest
from unittest import mock

import guard

VM = "00000000-0000-0000-0000-000000000001"
DELETE = {"tool_name": "mcp__nutanix__vmm_execute", "tool_input": {"operation": "deleteVmById", "extId": VM}}
FOUND = (0, json.dumps({"extId": VM, "name": "test-vm"}), "")
NOT_FOUND = (3, "", "VM was not found")
FAILED = (1, "", "Snapshot request failed: HTTP Error 404: NOT FOUND")
TAKEN = (0, "{}", "")


class DecisionTests(unittest.TestCase):
    def decide(self, payload, *replies):
        done = [subprocess.CompletedProcess([], *reply) for reply in replies]
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(guard.subprocess, "run", side_effect=done) as run, \
                mock.patch.object(guard.sys, "stdin", io.StringIO(json.dumps(payload))), \
                mock.patch.object(guard.sys, "stderr", stderr):
            code = guard.main()
        return code, [call.args[0][2] for call in run.call_args_list], stderr.getvalue()

    def test_snapshot_taken_allows(self):
        code, steps, _ = self.decide(DELETE, FOUND, TAKEN)
        self.assertEqual((code, steps), (0, ["resolve", "take"]))

    def test_vm_not_found_blocks_without_snapshot(self):
        code, steps, message = self.decide(DELETE, NOT_FOUND)
        self.assertEqual((code, steps), (2, ["resolve"]))
        self.assertIn("Could not confirm target VM", message)

    def test_lookup_error_blocks(self):
        code, steps, _ = self.decide(DELETE, FAILED)
        self.assertEqual((code, steps), (2, ["resolve"]))

    def test_snapshot_failure_blocks(self):
        code, steps, _ = self.decide(DELETE, FOUND, FAILED)
        self.assertEqual((code, steps), (2, ["resolve", "take"]))

    def test_missing_vm_id_blocks(self):
        payload = {"tool_name": DELETE["tool_name"], "tool_input": {"operation": "deleteVmById"}}
        code, steps, _ = self.decide(payload)
        self.assertEqual((code, steps), (2, []))

    def test_read_call_is_allowed_without_lookup(self):
        payload = {"tool_name": DELETE["tool_name"], "tool_input": {"operation": "listVms"}}
        code, steps, _ = self.decide(payload)
        self.assertEqual((code, steps), (0, []))


if __name__ == "__main__":
    unittest.main()

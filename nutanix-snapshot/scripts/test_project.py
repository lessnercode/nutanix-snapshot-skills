# Check that a recovery point follows the VM's project. Simulated replies, no network calls.
import io
import json
import os
import unittest
from unittest import mock

import ntnx_snapshot

VM = "00000000-0000-0000-0000-000000000001"
PROJECT_A = "aaaaaaaa-0000-0000-0000-000000000000"
PROJECT_B = "bbbbbbbb-0000-0000-0000-000000000000"
OTHER = "cccccccc-0000-0000-0000-000000000000"


class ProjectTests(unittest.TestCase):
    def take(self, record, target=VM):
        sent = []

        def fake_urlopen(request, **_):
            url, method = request.full_url, request.get_method()
            if method == "POST":
                sent.append(json.loads(request.data))
                reply = {"data": {"extId": "task-1"}}
            elif "/tasks/" in url:
                reply = {"data": {"status": "SUCCEEDED"}}
            elif url.endswith(f"/vms/{VM}"):
                reply = {"data": record}
            else:  # name search: deliberately leaves out the project
                reply = {"data": [{"extId": VM, "name": "test-vm"}]}
            return io.BytesIO(json.dumps(reply).encode())

        # A leftover setting from the old behaviour must have no effect.
        env = {"NTNX_PC_HOST": "pc.invalid", "NTNX_API_KEY": "x", "NTNX_PROJECT_EXT_ID": OTHER}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(ntnx_snapshot, "urlopen", fake_urlopen), \
                mock.patch.object(ntnx_snapshot.sys, "argv", ["x", "take", "--vm", target]), \
                mock.patch.object(ntnx_snapshot.sys, "stdout", io.StringIO()), \
                mock.patch.object(ntnx_snapshot.sys, "stderr", io.StringIO()):
            self.assertEqual(ntnx_snapshot.main(), 0)
        self.assertEqual(len(sent), 1)
        return sent[0]

    def record(self, **extra):
        return {"extId": VM, "name": "test-vm", **extra}

    def test_uses_each_vms_own_project(self):
        for project in (PROJECT_A, PROJECT_B):
            self.assertEqual(self.take(self.record(projectExtId=project))["projectExtId"], project)

    def test_reads_nested_project_reference(self):
        body = self.take(self.record(project={"extId": PROJECT_A}))
        self.assertEqual(body["projectExtId"], PROJECT_A)

    def test_name_lookup_reads_the_full_record(self):
        body = self.take(self.record(projectExtId=PROJECT_B), target="test-vm")
        self.assertEqual(body["projectExtId"], PROJECT_B)

    def test_no_project_sends_none(self):
        self.assertNotIn("projectExtId", self.take(self.record()))


if __name__ == "__main__":
    unittest.main()

// Run the shared Nutanix snapshot guard before OpenCode executes a tool.
import { existsSync } from "node:fs"
import { resolve } from "node:path"
import type { Plugin } from "@opencode-ai/plugin"

export const SnapshotGuard: Plugin = async ({ $, directory }) => ({
  "tool.execute.before": async (input, output) => {
    const relativePath = "skills/nutanix-snapshot-guard/scripts/guard.py"
    const opencodePath = resolve(directory, ".opencode", relativePath)
    const override = process.env.NTNX_GUARD_SCRIPT
    const script = override ? resolve(directory, override) :
      existsSync(opencodePath) ? opencodePath : resolve(directory, ".claude", relativePath)
    const payload = Buffer.from(JSON.stringify({ tool: input.tool, input: output.args }))
    const result = await $`python3 ${script} < ${payload}`.quiet().nothrow()
    if (result.exitCode !== 0) {
      throw new Error(result.stderr.toString().trim() || `Snapshot guard exited ${result.exitCode}`)
    }
  },
})

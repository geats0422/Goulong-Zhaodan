#!/usr/bin/env node
/**
 * 照胆 MCP Server — stdio 入口（本地使用）
 *
 * 适用于 Claude Desktop / Cursor 通过 npx 启动子进程的场景。
 * 远程部署请用 server.ts（Streamable HTTP 模式）。
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { registerAllTools, formatError } from "./shared.js";

const server = new McpServer({
  name: "goulong-zhaodan",
  version: "0.1.0",
});

registerAllTools(server);

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error(formatError(error));
  process.exit(1);
});

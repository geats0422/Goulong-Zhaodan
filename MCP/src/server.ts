#!/usr/bin/env node
/**
 * 照胆 MCP Server — Streamable HTTP 入口
 *
 * 无状态模式：每个请求创建独立 transport，Authorization 透传。
 * 端口默认 3200（文衡用 3100，避免冲突）。
 */

import express from "express";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

import { registerAllTools, apiKeyStorage, formatError } from "./shared.js";

const PORT = parseInt(process.env.MCP_PORT ?? "3200", 10);

const server = new McpServer({
  name: "goulong-zhaodan",
  version: "0.1.0",
});

registerAllTools(server);

function extractToken(authHeader: string | undefined): string {
  if (!authHeader) return "";
  const match = authHeader.match(/^Bearer\s+(.+)$/i);
  return match ? match[1].trim() : "";
}

const app = express();
app.use(express.json());

app.post("/mcp", async (req, res) => {
  try {
    const token = extractToken(req.headers.authorization);

    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    });

    res.on("close", () => {
      transport.close().catch(() => {});
    });

    await server.connect(transport);

    await apiKeyStorage.run(token, async () => {
      await transport.handleRequest(req, res, req.body);
    });
  } catch (err) {
    if (!res.headersSent) {
      res.status(500).json({
        error: "内部错误",
        message: "MCP Server 处理请求时出错",
      });
    }
  }
});

app.listen(PORT, () => {
  console.error(`照胆 MCP Server running on http://localhost:${PORT}/mcp`);
});

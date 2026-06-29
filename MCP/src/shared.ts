/**
 * 照胆 MCP 共享逻辑 — API 调用 + 工具注册。
 *
 * API Key 来源：
 * - HTTP 模式：每请求从 Authorization header 提取（存入 AsyncLocalStorage）
 * - stdio 模式：从环境变量 ZHAODAN_API_KEY 读取
 */
import { readFile, stat } from "node:fs/promises";
import { basename } from "node:path";
import { AsyncLocalStorage } from "node:async_hooks";

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

const DEFAULT_BASE_URL = "http://localhost:8000";
export const API_BASE_URL = (process.env.ZHAODAN_API_BASE_URL || DEFAULT_BASE_URL).replace(/\/$/, "");

/** 请求级 API Key 存储（HTTP 模式每请求注入，stdio 模式回退环境变量） */
export const apiKeyStorage = new AsyncLocalStorage<string>();

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

class ZhaodanApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly detail: unknown,
  ) {
    super(message);
  }
}

function getApiKey(): string {
  const ctxKey = apiKeyStorage.getStore();
  if (ctxKey) return ctxKey;
  const envKey = process.env.ZHAODAN_API_KEY;
  if (!envKey) {
    throw new Error("缺少 API Key。HTTP 模式需在 Authorization header 传入，stdio 模式需设置 ZHAODAN_API_KEY 环境变量。");
  }
  return envKey;
}

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

function formatError(error: unknown): string {
  if (error instanceof ZhaodanApiError) {
    return [
      `照胆 API 请求失败：HTTP ${error.status}`,
      `原因：${typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail)}`,
      "建议：检查 ZHAODAN_API_BASE_URL 是否正确、后端是否启动、API Key scope 是否满足该工具要求。",
    ].join("\n");
  }
  if (error instanceof Error) {
    return `${error.message}\n建议：检查 MCP 环境变量、后端服务状态和输入参数。`;
  }
  return `未知错误：${String(error)}`;
}

async function requestJson<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${getApiKey()}`);
  if (!(init.body instanceof FormData) && init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(apiUrl(path), { ...init, headers });
  const body = await parseResponse(response);
  if (!response.ok) {
    throw new ZhaodanApiError("照胆 API 请求失败", response.status, body);
  }
  return body as T;
}

function toolResult(data: unknown, summary?: string) {
  const text = summary ? `${summary}\n\n${JSON.stringify(data, null, 2)}` : JSON.stringify(data, null, 2);
  const structuredContent = data !== null && typeof data === "object" && !Array.isArray(data) ? data : { data };
  return {
    content: [{ type: "text" as const, text }],
    structuredContent: structuredContent as { [x: string]: unknown },
  };
}

function toolError(error: unknown) {
  return {
    isError: true,
    content: [{ type: "text" as const, text: formatError(error) }],
  };
}

async function readLocalFile(filePath: string, maxBytes: number): Promise<{ filename: string; bytes: Uint8Array }> {
  const info = await stat(filePath);
  if (!info.isFile()) {
    throw new Error(`文件不存在或不是普通文件：${filePath}`);
  }
  if (info.size > maxBytes) {
    throw new Error(`文件超过 ${Math.floor(maxBytes / 1024 / 1024)}MB 限制：${filePath}`);
  }
  return { filename: basename(filePath), bytes: await readFile(filePath) };
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

/** 注册全部照胆 MCP 工具 */
export function registerAllTools(server: McpServer): void {
  server.registerTool(
    "zhaodan_me",
    {
      description: "检查当前照胆 API Key 身份与 scopes。适合在调用其他工具前验证认证状态。",
      inputSchema: {},
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    },
    async () => {
      try {
        return toolResult(await requestJson("/api/v1/agent/me"), "当前 API Key 可用。");
      } catch (error) {
        return toolError(error);
      }
    },
  );

  server.registerTool(
    "zhaodan_search_knowledge",
    {
      description: "检索当前用户启用的法规/知识库片段，返回 snippets 与 sources。需要 knowledge:read scope。",
      inputSchema: {
        query: z.string().min(1).describe("检索意图或关键词，例如：招投标资格条件"),
        application_scenario: z.enum(["bidding", "contract"]).default("bidding").describe("应用场景"),
        limit: z.number().int().min(1).max(100).default(10).describe("最多返回条数，1-100"),
      },
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    },
    async ({ query, application_scenario, limit }) => {
      try {
        return toolResult(
          await requestJson("/api/v1/agent/knowledge/search", {
            method: "POST",
            body: JSON.stringify({ query, application_scenario, limit }),
          }),
          "知识库检索完成。",
        );
      } catch (error) {
        return toolError(error);
      }
    },
  );

  server.registerTool(
    "zhaodan_list_records",
    {
      description: "列出当前 API Key 所属用户的体检记录摘要。需要 inspection:read scope。",
      inputSchema: {},
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    },
    async () => {
      try {
        return toolResult(await requestJson("/api/v1/agent/records"), "体检记录列表获取完成。");
      } catch (error) {
        return toolError(error);
      }
    },
  );

  server.registerTool(
    "zhaodan_get_record",
    {
      description: "获取指定体检记录详情，包括风险、问题、法规引用和文本预览。需要 inspection:read scope。",
      inputSchema: {
        record_id: z.number().int().positive().describe("体检记录 ID"),
      },
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    },
    async ({ record_id }) => {
      try {
        return toolResult(await requestJson(`/api/v1/agent/records/${record_id}`), "体检记录详情获取完成。");
      } catch (error) {
        return toolError(error);
      }
    },
  );

  server.registerTool(
    "zhaodan_inspect_text",
    {
      description: "直接审查一段工程文档正文，返回完整体检报告。适合短文本或已由客户端提取正文的文档。需要 inspection:run scope。",
      inputSchema: {
        document_name: z.string().min(1).max(200).describe("文档名，例如：招标文件.txt"),
        text: z.string().min(10).describe("待审查正文，至少 10 个字符"),
        application_scenario: z.enum(["bidding", "contract"]).default("bidding").describe("应用场景"),
        taboo_words: z.string().default("").describe("临时违禁词，逗号分隔，可留空"),
        project_id: z.string().default("default").describe("项目 ID，可留默认值"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async (input) => {
      try {
        return toolResult(
          await requestJson("/api/v1/agent/inspect", { method: "POST", body: JSON.stringify(input) }),
          "文档体检完成。",
        );
      } catch (error) {
        return toolError(error);
      }
    },
  );

  server.registerTool(
    "zhaodan_parse_file",
    {
      description: "上传本地文件到照胆后端解析，创建 pending 记录并返回 record_id。适合后续用 record_id 复检。需要 inspection:run scope。",
      inputSchema: {
        file_path: z.string().min(1).describe("MCP 运行环境可访问的本地文件路径；支持后端允许的 txt/pdf/doc/docx"),
        project_id: z.string().default("default").describe("项目 ID，可留默认值"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ file_path, project_id }) => {
      try {
        const { filename, bytes } = await readLocalFile(file_path, 20 * 1024 * 1024);
        const form = new FormData();
        form.set("file", new Blob([toArrayBuffer(bytes)]), filename);
        form.set("project_id", project_id);
        return toolResult(
          await requestJson("/api/v1/agent/parse", { method: "POST", body: form }),
          "文件解析完成，可使用 record_id 继续体检。",
        );
      } catch (error) {
        return toolError(error);
      }
    },
  );

  server.registerTool(
    "zhaodan_inspect_record",
    {
      description: "基于 zhaodan_parse_file 返回的 record_id 执行体检，复用已解析正文并更新同一条记录。需要 inspection:run scope。",
      inputSchema: {
        record_id: z.number().int().positive().describe("已解析记录 ID"),
        project_id: z.string().default("default").describe("项目 ID，可留默认值"),
        application_scenario: z.enum(["bidding", "contract"]).default("bidding").describe("记录类型为 unknown 时使用的回退场景"),
        taboo_words: z.string().default("").describe("临时违禁词，逗号分隔，可留空"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async (input) => {
      try {
        return toolResult(
          await requestJson("/api/v1/agent/inspect", { method: "POST", body: JSON.stringify(input) }),
          "record_id 体检完成。",
        );
      } catch (error) {
        return toolError(error);
      }
    },
  );

  server.registerTool(
    "zhaodan_create_inspect_job",
    {
      description: "创建异步体检 job。适合长文本、批处理或不希望阻塞当前会话的审查任务。需要 inspection:run scope。",
      inputSchema: {
        document_name: z.string().min(1).default("未命名文档").describe("文档名"),
        text: z.string().min(10).describe("待审查正文，至少 10 个字符"),
        application_scenario: z.enum(["bidding", "contract"]).default("bidding").describe("应用场景"),
        taboo_words: z.string().default("").describe("临时违禁词，逗号分隔，可留空"),
        project_id: z.string().default("default").describe("项目 ID，可留默认值"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async (input) => {
      try {
        return toolResult(
          await requestJson("/api/v1/agent/jobs/inspect", {
            method: "POST",
            body: JSON.stringify({ input_payload: input }),
          }),
          "异步体检 job 已创建，请用 zhaodan_get_job_status 轮询。",
        );
      } catch (error) {
        return toolError(error);
      }
    },
  );

  server.registerTool(
    "zhaodan_create_parse_job",
    {
      description: "创建异步解析 job。输入本地文件并以 base64 payload 投递给后端 worker，返回 job_id。需要 inspection:run scope。",
      inputSchema: {
        file_path: z.string().min(1).describe("MCP 运行环境可访问的本地文件路径"),
        project_id: z.string().default("default").describe("项目 ID，可留默认值"),
      },
      annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
    },
    async ({ file_path, project_id }) => {
      try {
        const { filename, bytes } = await readLocalFile(file_path, 20 * 1024 * 1024);
        const payload: Record<string, JsonValue> = {
          document_name: filename,
          content_base64: Buffer.from(bytes).toString("base64"),
          project_id,
        };
        return toolResult(
          await requestJson("/api/v1/agent/jobs/parse", {
            method: "POST",
            body: JSON.stringify({ input_payload: payload }),
          }),
          "异步解析 job 已创建，请用 zhaodan_get_job_status 轮询。",
        );
      } catch (error) {
        return toolError(error);
      }
    },
  );

  server.registerTool(
    "zhaodan_get_job_status",
    {
      description: "查询异步 job 状态与结果。适合轮询 zhaodan_create_inspect_job / zhaodan_create_parse_job 返回的 job_id。",
      inputSchema: {
        job_id: z.string().min(1).describe("异步任务 ID"),
      },
      annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    },
    async ({ job_id }) => {
      try {
        return toolResult(await requestJson(`/api/v1/agent/jobs/${encodeURIComponent(job_id)}`), "job 状态获取完成。");
      } catch (error) {
        return toolError(error);
      }
    },
  );
}

export { formatError };

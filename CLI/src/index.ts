#!/usr/bin/env node
import { readFile, stat } from "node:fs/promises";
import { basename } from "node:path";

const DEFAULT_BASE_URL = "http://localhost:8000";
const API_BASE_URL = (process.env.ZHAODAN_API_BASE_URL || DEFAULT_BASE_URL).replace(/\/$/, "");
const API_KEY = process.env.ZHAODAN_API_KEY;

type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };
type CliOptions = Record<string, string | boolean>;

class ZhaodanCliError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly detail?: unknown,
  ) {
    super(message);
  }
}

function requireApiKey(): string {
  if (!API_KEY) {
    throw new ZhaodanCliError("缺少 ZHAODAN_API_KEY，请先创建 cli_review API Key 并设置环境变量。");
  }
  return API_KEY;
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

async function requestJson<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${requireApiKey()}`);
  if (!(init.body instanceof FormData) && init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(apiUrl(path), { ...init, headers });
  const body = await parseResponse(response);
  if (!response.ok) {
    throw new ZhaodanCliError("照胆 API 请求失败", response.status, body);
  }
  return body as T;
}

function usage(): string {
  return `Goulong Zhaodan CLI

用法:
  zhaodan me
  zhaodan records:list
  zhaodan records:get --record-id <id>
  zhaodan knowledge:search --query <关键词> [--application-scenario bidding|contract] [--limit 10]
  zhaodan inspect:text --document-name <name> --text <正文> [--application-scenario bidding|contract] [--taboo-words <词>] [--project-id default]
  zhaodan parse:file --file-path <path> [--project-id default]
  zhaodan inspect:record --record-id <id> [--application-scenario bidding|contract] [--taboo-words <词>] [--project-id default]
  zhaodan jobs:inspect --document-name <name> --text <正文> [--application-scenario bidding|contract] [--taboo-words <词>] [--project-id default]
  zhaodan jobs:parse --file-path <path> [--project-id default]
  zhaodan jobs:status --job-id <id>

环境变量:
  ZHAODAN_API_KEY       必需，建议使用 cli_review 模板
  ZHAODAN_API_BASE_URL  可选，默认 http://localhost:8000
`;
}

function parseArgs(argv: string[]): { command: string; options: CliOptions } {
  const [command = "help", ...rest] = argv;
  const options: CliOptions = {};

  for (let i = 0; i < rest.length; i += 1) {
    const token = rest[i];
    if (!token.startsWith("--")) {
      throw new ZhaodanCliError(`无法识别的参数：${token}`);
    }
    const key = token.slice(2).replace(/-([a-z])/g, (_, letter: string) => letter.toUpperCase());
    const next = rest[i + 1];
    if (next === undefined || next.startsWith("--")) {
      options[key] = true;
      continue;
    }
    options[key] = next;
    i += 1;
  }

  return { command, options };
}

function getString(options: CliOptions, key: string, fallback?: string): string {
  const value = options[key];
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  if (fallback !== undefined) {
    return fallback;
  }
  throw new ZhaodanCliError(`缺少必需参数 --${key.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`);
}

function getNumber(options: CliOptions, key: string, fallback?: number): number {
  const raw = options[key];
  if (raw === undefined || raw === true) {
    if (fallback !== undefined) return fallback;
    throw new ZhaodanCliError(`缺少必需参数 --${key.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}`);
  }
  const value = Number(raw);
  if (!Number.isInteger(value) || value <= 0) {
    throw new ZhaodanCliError(`参数 --${key} 必须是正整数`);
  }
  return value;
}

function scenario(options: CliOptions): string {
  const value = getString(options, "applicationScenario", "bidding");
  if (!["bidding", "contract"].includes(value)) {
    throw new ZhaodanCliError("--application-scenario 仅支持 bidding 或 contract");
  }
  return value;
}

async function readLocalFile(filePath: string, maxBytes: number): Promise<{ filename: string; bytes: Uint8Array }> {
  const info = await stat(filePath);
  if (!info.isFile()) {
    throw new ZhaodanCliError(`文件不存在或不是普通文件：${filePath}`);
  }
  if (info.size > maxBytes) {
    throw new ZhaodanCliError(`文件超过 ${Math.floor(maxBytes / 1024 / 1024)}MB 限制：${filePath}`);
  }
  return { filename: basename(filePath), bytes: await readFile(filePath) };
}

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

async function run(command: string, options: CliOptions): Promise<unknown> {
  switch (command) {
    case "help":
    case "--help":
    case "-h":
      return usage();
    case "me":
      return requestJson("/api/v1/agent/me");
    case "records:list":
      return requestJson("/api/v1/agent/records");
    case "records:get":
      return requestJson(`/api/v1/agent/records/${getNumber(options, "recordId")}`);
    case "knowledge:search":
      return requestJson("/api/v1/agent/knowledge/search", {
        method: "POST",
        body: JSON.stringify({
          query: getString(options, "query"),
          application_scenario: scenario(options),
          limit: getNumber(options, "limit", 10),
        }),
      });
    case "inspect:text":
      return requestJson("/api/v1/agent/inspect", {
        method: "POST",
        body: JSON.stringify({
          document_name: getString(options, "documentName"),
          text: getString(options, "text"),
          application_scenario: scenario(options),
          taboo_words: getString(options, "tabooWords", ""),
          project_id: getString(options, "projectId", "default"),
        }),
      });
    case "parse:file": {
      const { filename, bytes } = await readLocalFile(getString(options, "filePath"), 20 * 1024 * 1024);
      const form = new FormData();
      form.set("file", new Blob([toArrayBuffer(bytes)]), filename);
      form.set("project_id", getString(options, "projectId", "default"));
      return requestJson("/api/v1/agent/parse", { method: "POST", body: form });
    }
    case "inspect:record":
      return requestJson("/api/v1/agent/inspect", {
        method: "POST",
        body: JSON.stringify({
          record_id: getNumber(options, "recordId"),
          application_scenario: scenario(options),
          taboo_words: getString(options, "tabooWords", ""),
          project_id: getString(options, "projectId", "default"),
        }),
      });
    case "jobs:inspect":
      return requestJson("/api/v1/agent/jobs/inspect", {
        method: "POST",
        body: JSON.stringify({
          input_payload: {
            document_name: getString(options, "documentName", "未命名文档"),
            text: getString(options, "text"),
            application_scenario: scenario(options),
            taboo_words: getString(options, "tabooWords", ""),
            project_id: getString(options, "projectId", "default"),
          },
        }),
      });
    case "jobs:parse": {
      const { filename, bytes } = await readLocalFile(getString(options, "filePath"), 20 * 1024 * 1024);
      const payload: Record<string, JsonValue> = {
        document_name: filename,
        content_base64: Buffer.from(bytes).toString("base64"),
        project_id: getString(options, "projectId", "default"),
      };
      return requestJson("/api/v1/agent/jobs/parse", {
        method: "POST",
        body: JSON.stringify({ input_payload: payload }),
      });
    }
    case "jobs:status":
      return requestJson(`/api/v1/agent/jobs/${encodeURIComponent(getString(options, "jobId"))}`);
    default:
      throw new ZhaodanCliError(`未知命令：${command}\n\n${usage()}`);
  }
}

function printResult(result: unknown, raw: boolean): void {
  if (typeof result === "string") {
    console.log(result);
    return;
  }
  console.log(JSON.stringify(result, null, raw ? 0 : 2));
}

function formatError(error: unknown): string {
  if (error instanceof ZhaodanCliError) {
    if (error.status) {
      const detail = typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail);
      return `照胆 API 请求失败：HTTP ${error.status}\n原因：${detail}`;
    }
    return error.message;
  }
  return error instanceof Error ? error.message : String(error);
}

async function main(): Promise<void> {
  const { command, options } = parseArgs(process.argv.slice(2));
  const raw = options.raw === true;
  const result = await run(command, options);
  printResult(result, raw);
}

main().catch((error) => {
  console.error(formatError(error));
  process.exit(1);
});

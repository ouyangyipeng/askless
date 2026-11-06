export type ExportKey = "format" | "separator" | "header";
export type SessionStatus =
  "ready" | "chosen" | "completed" | "stale" | "failed";
export type Artifact = {
  name: string;
  media_type: string;
  text: string;
  bytes: number;
};
export type ExportTrial = {
  id: string;
  policy: Record<ExportKey, string>;
  output: { rows: number; columns: string[]; artifact: Artifact };
  output_hash: string;
  elapsed_ms: number;
};
export type ExportDecision = {
  key: ExportKey;
  prompt: string;
  options: string[];
  status: "pending" | "answered" | "auto";
  selected: string | null;
  witnesses: string[];
  comparisons_checked: number;
};
export type SessionSummary = {
  id: string;
  title: string;
  status: SessionStatus;
  created_at: string;
  owner: "workbench" | "mcp";
};
export type ExportSession = SessionSummary & {
  revision: number;
  source_name: string;
  inputs: Record<string, string | number | boolean | null>[];
  answers: Partial<Record<ExportKey, string>>;
  decisions: ExportDecision[];
  pending: ExportKey[];
  trials: ExportTrial[];
  partial_trials: ExportTrial[];
  result: ExportTrial | null;
  scope: string | null;
  error: string | null;
  events: { at: string; label: string; detail: string }[];
  agent_steps: {
    id: string;
    tool: string;
    model: string;
    summary: string;
    requests: number;
    input_tokens: number;
    output_tokens: number;
    elapsed_ms: number;
  }[];
};
export const exportLabels: Record<string, string> = {
  format: "文件格式",
  separator: "分隔符",
  header: "列名",
  json: "JSON",
  csv: "CSV",
  comma: "逗号",
  semicolon: "分号",
  include: "保留列名",
  omit: "省略列名",
};
export const sessionLabels: Record<SessionStatus, string> = {
  ready: "等待选择",
  chosen: "选择已就绪",
  completed: "已验证",
  stale: "输入已变化",
  failed: "执行已停止",
};

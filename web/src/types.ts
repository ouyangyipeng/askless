export type Key = "duplicates" | "invalid" | "email_case";
export type Policy = Record<Key, string>;
export interface Evidence {
  id: string;
  scope: string;
  policy: Policy;
  rows: Record<string, string>[];
  quarantined: { line: number; reason: string; row: Record<string, string> }[];
  blocked: boolean;
  duplicate_count: number;
  elapsed_ms: number;
  output_hash: string;
}
export interface Group {
  key: Key;
  spec: {
    title: string;
    context: string;
    options: { value: string; label: string; description: string }[];
  };
  question_ids: string[];
  agent_ids: string[];
  status: "auto" | "pending" | "answered";
  selected: string | null;
  reason: string;
  witnesses: string[];
  comparisons_checked: number;
}
export interface Run {
  id: string;
  title: string;
  mode: "live" | "offline";
  model: string;
  created_at: string;
  status: string;
  revision: number;
  dataset: { scope: string; columns: string[]; rows: Record<string, string>[] };
  agents: {
    id: string;
    name: string;
    role: string;
    status: string;
    summary: string;
  }[];
  questions: {
    id: string;
    agent_id: string;
    decision_key: Key;
    prompt: string;
  }[];
  trials: Evidence[];
  groups: Group[];
  events: { at: string; label: string; detail: string }[];
  receipts: {
    agent_id: string;
    summary: string;
    policy: Policy;
    output_hash: string;
    consumed_question_ids: string[];
  }[];
  result: Evidence | null;
  error: string | null;
  llm_calls: number;
  input_tokens: number;
  output_tokens: number;
}
export interface Config {
  token: string;
  model: string;
  configured: boolean;
  sample_csv: string;
  version: string;
}
export interface History {
  id: string;
  title: string;
  status: string;
  mode: string;
  created_at: string;
  rows: number;
}

export const isActive = (status: string) =>
  ["planning", "exploring", "applying"].includes(status);
export const statusLabel: Record<string, string> = {
  planning: "Agent 正在分析",
  exploring: "正在运行试验",
  ready: "等待你的决定",
  applying: "正在传播答案",
  completed: "已完成",
  failed: "运行失败",
  interrupted: "运行中断",
};

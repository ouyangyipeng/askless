<p align="center">
  <a href="https://oyyp.nexa-lang.com/askless/"><img src="docs/images/cover.svg" alt="AskLess — 让 Agent 先试跑，再把有意义的决定交给你。" width="100%" /></a>
</p>

<p align="center">
  <a href="https://oyyp.nexa-lang.com/askless/"><strong>官网与交互示例 ↗</strong></a>
  &nbsp; · &nbsp; <a href="#五分钟体验">快速开始</a>
  &nbsp; · &nbsp; <a href="docs/architecture.md">架构说明</a>
  &nbsp; · &nbsp; <a href="README.md">English</a>
</p>

<p align="center"><sub>本地优先 &nbsp; / &nbsp; MIT 开源 &nbsp; / &nbsp; 实验版本 v0.1</sub></p>

<br />

## 把注意力留给真正重要的决定。

**Run the alternatives. Ask only what matters.**

让协作 Agent 先执行备选方案，把需要人回答的问题收敛成带真实结果预览的决定。

AskLess 0.1 是本地可运行的实验版本。首个适配器处理联系人 CSV：三个角色各自提出重复记录、无效邮箱、大小写三项策略问题；执行器完整试跑八种组合；编译器按同一数据作用域和固定策略合同合并问题，仅在所有对照结果相同时自动解决选择。你确认剩余决定后，三个角色接收同一份策略，执行器重新计算并校验交付结果。

![AskLess 本地工作台](docs/images/workbench.jpg)

## 五分钟体验

需要 Python 3.12+、[uv](https://docs.astral.sh/uv/getting-started/installation/)、Node.js 24.15+（或 22.22.2+）、pnpm 12。本机验收使用 Node.js 24。

```bash
git clone https://github.com/ouyangyipeng/askless.git
cd askless
./run.sh
```

打开 [本地工作台](http://127.0.0.1:8765)。脚本安装锁定依赖、构建界面，然后启动仅监听 `127.0.0.1` 的服务。已有依赖会复用；停止服务用 `Ctrl+C`。可用 `./run.sh --port 8766` 改端口。

如果只想启动已经构建好的版本：

```bash
.venv/bin/python -m askless --port 8765
```

界面默认载入八行合成示例数据。选择“保留末次记录”和“隔离异常，继续导入”，会得到四条联系人和两条隔离记录。展开问题卡能查看分支产物与三个角色的原始问题；完成后可下载 CSV 和完整 JSON 证据包。

## 真实 LLM 与离线运行

服务从启动进程的环境读取凭据，支持阿里云的 OpenAI 兼容接口：

| 环境变量 | 用途 |
| --- | --- |
| `ALIYUN_API_KEY` | API 凭据；缺省时读取 `DASHSCOPE_API_KEY` |
| `ALIYUN_BASE_URL` | HTTPS 兼容接口地址，默认 `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `ASKLESS_MODEL` | 模型名，默认 `qwen3.8-flash`；按账户实际权限设置 |

从已导出这些变量的终端启动即可。程序只读取环境变量，不自动加载 `.env` 或 shell 配置文件。模型需支持 Chat Completions、JSON 输出与 `enable_thinking: false` 参数。

真实模式通常调用六次模型：三次提问、三次确认策略。每次请求最多重试一次，连接与读写超时各为 45 秒。模型错误会显示失败状态并保留已完成证据。界面的请求和 token 数来自成功解析并记录的阶段；失败请求的用量及供应商账单需要在供应商侧查询。

无凭据时可使用“离线演示”。该模式采用固定角色问题，不调用模型；八种分支执行、问题编译、回答校验与 CSV 导出仍在本机运行。

## 工作机制

```text
CSV + 任务描述
  ├─ 数据工程师 ─┐
  ├─ 质量审核员 ─┼─ 9 个带合同键的问题
  └─ 交付负责人 ─┘
          ↓
  8 个完整策略组合的本地执行
          ↓
  按合同与数据哈希合并 → 检查全部策略交互
          ↓
  有差异：保留问题 + 两份真实分支产物
  无差异：自动选择等价项 + 保留比较证据
          ↓
  人工确认 → 3 份显式策略回执 → 重新执行并比对哈希 → 下载
```

样例中的九个问题由三个角色按协议各提出三项，编译后有两项待定、一项结果等价。这个样例用于展示机制；人类处理时间、实际协作任务的自然提问分布和验收质量尚待独立实验测量。

**结果等价的范围是当前整批输入与适配器定义的可观察结果。** 比较包含导出记录、隔离记录及阻断状态；完整枚举其他选择，避免在某一个分支里看起来相同就跳过问题。每项选择绑定输入的 SHA-256，回答不会跨数据集自动复用。

当前三个角色共用一个可信的 CSV 策略执行器。原型尚未接入 Codex / Claude Code 等通用编码 Agent，也未提供任意生成代码的沙箱执行、跨任务偏好学习或自动归纳上层产品决定。扩展到其他场景时，需要为该场景实现操作合同、受控执行和可观察结果定义。

## 数据与资源边界

- 原始 CSV、所有分支结果、回答和回执保存于本地 `.askless/runs.sqlite3`。
- 发送给模型的内容为任务描述、角色、聚合统计、策略合同与确认后的行数/阻断状态。任务描述中输入的信息会发送给配置的模型服务。
- UTF-8 CSV 最大 256 KiB、2,000 行、30 列；必须有唯一的 `email` 列。每个列名最多 128 UTF-8 字节，展开数据最多 512 KiB，防止重复字段名放大存储。
- 单次持久化运行最多 8 MiB，最多保留 50 次运行；最多两次运行同时执行模型或分支任务。单份运行记录的理论数据上限合计为 400 MiB，SQLite 文件还会包含索引、页与可复用空闲空间。
- 历史记录可手动删除。SQLite 通常复用删除后释放的页，文件不会立刻缩小。
- 邮箱执行语法检查，不查询 DNS 或验证投递能力。重复识别按去首尾空白、忽略大小写后的 email；末次记录按文件顺序定义。
- CSV 下载会中和电子表格公式前缀；JSON 证据包保留原始输入，适合核对与复现实验。
- 运行中停止服务会将未完成任务标记为“已中断”；已完成和待决定的运行在重启后保留。可通过 `--data-dir` 指定数据目录。

运行不下载本地模型，不需要 Docker 或独立数据库。实际占用和验收记录见 [本地验证记录](docs/validation-2026-10-23.md)。

## 开发与验证

```bash
uv sync --frozen
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run isort --check-only src tests scripts
uv run ty check src tests scripts
pnpm --dir web install --frozen-lockfile
pnpm --dir web exec prettier --check src site
pnpm --dir web test
pnpm --dir web build
pnpm --dir web site:build
```

前端开发可另开终端运行 `pnpm --dir web dev`，Vite 将 `/api` 代理到 8765 端口的后端。正常使用时只需要一个 Python 服务，直接提供构建后的页面。

| 位置 | 职责 |
| --- | --- |
| `src/askless/engine.py` | CSV 验证、真实分支执行、证据比较与问题编译 |
| `src/askless/agents.py` / `llm.py` | 角色协议、模型调用、显式策略回执 |
| `src/askless/service.py` / `store.py` | 生命周期、事务、作用域、并发与存储边界 |
| `src/askless/api.py` | 本地同源 API、导出、静态页面 |
| `web/src/` | React 工作台、问题卡、证据预览、历史记录 |
| `tests/` | 核心行为、错误路径与 HTTP 回归验证 |

接口与状态机见 [架构说明](docs/architecture.md)。官网源文件位于 `web/site/`，复用工作台依赖；`pnpm --dir web site:dev` 可本地预览。GitHub Pages 发布方式与示例更新方法见 [官网维护说明](docs/website.md)。

欢迎贡献有明确执行语义的新适配器、策略交互测试，以及人类决策时间与任务质量的评估方案。参见 [贡献指南](CONTRIBUTING.md)。本项目采用 [MIT License](LICENSE)。

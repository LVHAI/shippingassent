# 06: LangGraph 费率查询 Agent（CLI 可运行）

**What to build:** 构建第一个可运行的对话式 Agent，用户输入自然语言问题，系统返回格式化的运费报价。CLI 模式下可交互对话。

**Blocked by:** 03 SQLite 入库 + 费率计算引擎, 05 LLM 意图提取

**Status:** complete

## Acceptance criteria

- [x] `agent/graph.py` 定义 LangGraph 工作流：parse_intent → check_params → calculate_rate → generate_response
- [x] `agent/nodes.py` 实现 `check_params_node`：检查 missing_params，参数完整时返回 "ready"，否则返回 "ask_followup"
- [x] `agent/nodes.py` 实现 `calculate_rate_node`：调用 `calculate_rate` 工具，将结果写入 state.rate_results
- [x] `agent/nodes.py` 实现 `generate_response_node`：LLM 将 rate_results 格式化为用户友好的自然语言回复；失败时使用确定性报价文本
- [x] `agent/nodes.py` 实现 `ask_followup_node`：生成追问消息（如"请告诉我货物重量和类型"）
- [x] CLI 入口 `main.py`：启动对话循环，支持多轮交互
- [x] 端到端测试：
  - 输入"美国5kg普货多少钱" → 输出至少1个渠道的报价（渠道名 + 价格 + 时效）
  - 输入"寄到日本多少钱" → 追问重量和货物类型
  - 回答"2kg衣服" → 输出日本渠道的报价
- [x] 无匹配时输出"抱歉，未找到符合条件的渠道"，不编造价格

## Technical notes

- LangGraph 使用 `StateGraph` 构建有向图
- 条件路由：check_params 根据 missing_params 决定走 calculate_rate 还是 ask_followup
- generate_response 使用 LLM 格式化输出，但价格数据来自确定性计算；LLM 输出必须包含原始渠道、价格和时效，否则自动回退到确定性格式
- 多轮对话通过简单的 state dict 管理；仅在上一轮明确处于 ask_followup 状态时继承国家、重量和货物类型

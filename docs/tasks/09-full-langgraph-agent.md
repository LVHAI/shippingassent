# 09: LangGraph 完整 Agent（费率 + 规则 + 追问）

**What to build:** 将费率查询和规则检索整合为完整的 LangGraph 工作流，支持5种意图类型的全覆盖，多轮对话状态管理，CLI 可交互。

**Blocked by:** 06 LangGraph 费率查询 Agent, 08 Embedding 管道 + Milvus 向量库

**Status:** ready-for-agent

## Acceptance criteria

- [ ] `agent/graph.py` 扩展工作流，添加 `search_rules` 节点和完整路由
- [ ] 路由支持5种意图类型：
  - `rate_query` → calculate_rate → generate_response
  - `rule_query` → search_rules → generate_response
  - `mixed` → (calculate_rate ∥ search_rules) → generate_response
  - `followup` → ask_followup
  - `chitchat` → generate_response（直接生成）
- [ ] `search_rules_node`：调用向量检索，将结果写入 state.rule_results
- [ ] `generate_response_node` 扩展：同时处理 rate_results 和 rule_results，组合为完整回复
- [ ] 多轮对话状态管理：追问后的回答能正确合并到已有参数（ADR-011）
- [ ] CLI 端到端测试：
  - "美国5kg普货多少钱" → 输出报价
  - "赔偿标准是什么" → 输出规则说明
  - "美国5kg普货，包括时效和尺寸限制" → 输出报价 + 规则
  - "寄到日本多少钱" → 追问 → "2kg衣服" → 输出报价
  - "你好" → 闲聊回复
- [ ] 回复质量：格式清晰、引用数据来源、无幻觉

## Technical notes

- 混合查询可使用 `Send` API 或并行节点执行 calculate_rate 和 search_rules
- 多轮对话使用 LangGraph 的 `checkpointer` 持久化状态
- 追问节点需要记住缺失的参数列表，回答后重新检查
- 参考 PRD 第7.3节路由逻辑
- 参考 ADR-002：LangGraph 条件路由

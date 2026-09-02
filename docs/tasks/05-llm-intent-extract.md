# 05: LLM 意图提取

**What to build:** 使用通义千问 LLM 从用户自然语言输入中提取结构化参数（国家、重量、货物类型、意图类型），支持参数不完整时的缺失标记。

**Blocked by:** 01 项目脚手架与依赖配置, 04 货物类型同义词映射

**Status:** ready-for-agent

## Acceptance criteria

- [ ] `agent/nodes.py` 实现 `parse_intent_node(state: ShippingState) -> dict`
- [ ] LLM 调用使用通义千问 qwen3.7-max（通过 DashScope SDK）
- [ ] 输出结构化参数：`intent_type`（rate_query/rule_query/mixed/chitchat）、`country`、`weight`（float，单位KG）、`cargo_type`、`missing_params`（缺失参数列表）
- [ ] 正确解析示例：
  - "美国5kg普货多少钱" → {intent_type: "rate_query", country: "美国", weight: 5.0, cargo_type: "普货", missing_params: []}
  - "寄到巴西要多少钱" → {intent_type: "rate_query", country: "巴西", weight: null, cargo_type: null, missing_params: ["weight", "cargo_type"]}
  - "赔偿标准是什么" → {intent_type: "rule_query", country: null, weight: null, cargo_type: null, missing_params: []}
  - "你好" → {intent_type: "chitchat", ...}
- [ ] 货物类型提取先经过同义词映射（ADR-008）
- [ ] LLM 调用失败时有合理的 fallback（返回 chitchat）
- [ ] CLI 测试：手动输入3种不同类型的查询，验证意图提取结果

## Technical notes

- 使用 DashScope SDK 调用通义千问，API Key 从环境变量 `DASHSCOPE_API_KEY` 读取
- 使用 few-shot prompting 提高意图提取准确率
- 输出格式使用 JSON，便于解析
- 重量单位统一为 KG（用户输入可能是"克"、"g"、"斤"等，需要转换）
- 参考 PRD 第7.1节 State 定义

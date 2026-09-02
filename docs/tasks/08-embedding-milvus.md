# 08: Embedding 管道 + Milvus 向量库

**What to build:** 将提取的规则文本向量化并存入 Milvus Lite，实现语义检索能力。输入自然语言问题，返回最相关的规则文本。

**Blocked by:** 07 XLS 规则文本提取器

**Status:** ready-for-agent

## Acceptance criteria

- [ ] `data_pipeline/milvus_loader.py` 实现 Milvus 数据加载器
- [ ] 按 PRD 第6.2节创建 `shipping_rules` collection，字段：id, embedding (FLOAT_VECTOR 1024维), text, sheet_name, channel_name, rule_category, metadata
- [ ] 使用通义千问 text-embedding-v4 进行文本向量化（通过 DashScope SDK）
- [ ] `init_data.py` 扩展：支持 XLS → Milvus 全量导入（清空旧数据后重建）
- [ ] `agent/tools.py` 实现 `search_rules(query: str, top_k: int = 3) -> list` 向量检索函数
- [ ] 检索支持 metadata 过滤（按 sheet_name 或 rule_category 缩小范围）
- [ ] CLI 测试验证检索效果：
  - "赔偿标准" → 返回易德赔付标准相关内容
  - "什么东西不能寄" → 返回航空禁运物品相关内容
  - "美国尺寸限制" → 返回美国相关渠道的尺寸要求
- [ ] 向量化和检索延迟 < 500ms

## Technical notes

- Milvus Lite 数据库路径：`vectordb/milvus_data.db`
- text-embedding-v4 输出 1024 维向量
- 调用 DashScope API：`dashscope.TextEmbedding.call(model="text-embedding-v4", input=texts)`
- 检索使用 L2 距离（越小越相似）
- 参考 ADR-003：Milvus Lite 选型
- 全量更新时先 drop collection 再 create，确保无残留

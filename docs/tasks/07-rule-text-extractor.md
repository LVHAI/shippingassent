# 07: XLS 规则文本提取器

**What to build:** 从 XLS 文件中提取所有非结构化规则文本，包括费率表下方的规则说明和独立的规则工作表。输出格式化的规则数据，为后续向量化做准备。

**Blocked by:** 02 XLS 费率表解析器

**Status:** ready-for-agent

## Acceptance criteria

- [ ] `data_pipeline/xls_parser.py` 扩展 `XLSPipeline` 类，添加规则文本提取方法
- [ ] 实现 `extract_rules_from_rate_sheet(sheet_name)`：从费率工作表下方的规则区域提取文本（通常在费率表之后的行）
- [ ] 实现 `extract_rules_from_standalone_sheet(sheet_name)`：从独立规则工作表提取（易德赔付标准、航空禁运物品等）
- [ ] 输出 `ChannelRule` 数据模型，包含：sheet_name, channel_name（可为 null 表示通用规则）, rule_category, content
- [ ] 规则类别自动识别：赔偿、禁运、尺寸、退件、申报、安检、时效、其他
- [ ] 成功提取以下工作表的规则：
  - 费率表规则：美国专线小包、日本专线小包（各自下方的规则说明）
  - 独立规则：易德赔付标准、退费额外费要求、航空禁运物品
- [ ] 过滤空规则和无意义内容（如纯表头行）
- [ ] 单元测试验证规则提取的完整性和类别标注

## Technical notes

- 费率表规则通常在最后一个费率行之后，识别策略：搜索包含"申报"、"赔偿"、"安检"、"退件"等关键词的区域
- 独立规则工作表的结构各异，需要针对每个工作表编写适配逻辑
- 规则文本可能包含换行符，需要保留原始格式或合理拼接
- channel_name 字段：如果规则明确关联某个渠道则填写，否则为 null（通用规则）

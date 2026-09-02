# 03: SQLite 入库 + 费率计算引擎

**What to build:** 将解析后的费率数据存入 SQLite，并提供确定性的费率计算函数。这是第一个可端到端验证的切片——输入国家+重量+货物类型，输出精确报价。

**Blocked by:** 02 XLS 费率表解析器

**Status:** ready-for-agent

## Acceptance criteria

- [ ] `data_pipeline/sqlite_loader.py` 实现 SQLite 数据加载器
- [ ] 按 PRD 第6.1节创建 `channels` 表，包含所有费率字段
- [ ] `init_data.py` 可一键执行 XLS → SQLite 全量导入
- [ ] `agent/tools.py` 实现 `calculate_rate(country, weight, cargo_type)` 函数
- [ ] 费率计算支持两种模式：单价模式（`weight × price_per_kg + handling_fee`）和首重续重模式
- [ ] 查询条件支持国家模糊匹配（"美国" 匹配 "美国"，也匹配包含美国的渠道）
- [ ] 查询条件支持货物类型匹配（普货渠道不返回带电渠道的结果）
- [ ] 查询条件支持重量区间匹配（weight_min ≤ 查询重量 ≤ weight_max）
- [ ] 返回结果按价格升序排列
- [ ] 无匹配时返回空列表，不编造数据
- [ ] CLI 测试：`calculate_rate("美国", 5.0, "普货")` 返回至少1个渠道的报价，金额计算正确

## Technical notes

- SQLite 数据库文件路径：`data/shipping.db`
- 计算函数是纯确定性的，不调用 LLM
- 参考 ADR-010：统一费率计算模型
- 首重续重公式：`first_weight_price + ceil((weight - first_weight) / additional_weight) * additional_weight_price`
- 重量低于起重时按起重计费

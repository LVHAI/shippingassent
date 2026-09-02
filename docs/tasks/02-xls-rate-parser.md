# 02: XLS 费率表解析器

**What to build:** 构建一个 XLS 解析器，能从多个格式各异的费率工作表中提取结构化数据。解析器需要处理合并单元格、不统一表头、多种计费表达等数据脏问题。

**Blocked by:** 01 项目脚手架与依赖配置

**Status:** ready-for-agent

## Acceptance criteria

- [ ] `data_pipeline/xls_parser.py` 实现 `XLSPipeline` 类
- [ ] 成功解析至少5个代表性工作表：美国专线小包、日本专线小包、欧美标准专线、巴西专线小包DDU、香港DHL代理价
- [ ] 输出归一化的 `ChannelRate` 数据模型，包含：sheet_name, channel_name, countries, cargo_type, weight_min, weight_max, price_per_kg, handling_fee, first_weight, first_weight_price, additional_weight, additional_weight_price, size_requirements, transit_time, carrier
- [ ] 正确处理合并单元格（NaN 值向下填充渠道名和国家名）
- [ ] 自动识别表头行位置（搜索包含"渠道"、"重量"、"运费"等关键词的行）
- [ ] 正确解析两种计费模式：单价模式（运费/KG + 处理费）和首重续重模式
- [ ] 处理特殊标记（`*` 表示不提供服务）
- [ ] 提供 `parse_sheet(sheet_name)` 和 `parse_all()` 两个入口
- [ ] 单元测试覆盖5个代表性工作表，断言解析结果的字段值

## Technical notes

- 使用 pandas + xlrd 读取 .xls 文件
- 表头识别策略：搜索包含 "渠道", "重量", "运费/KG", "处理费" 的行
- 合并单元格在 pandas 中显示为 NaN，使用 `ffill()` 向下填充
- 重量区间格式如 "0.050-0.1KG"，需用正则提取 min/max
- 部分工作表一个 sheet 包含多个国家（如欧美标准专线），部分一个国家一个 sheet
- 参考 CONTEXT.md 中的术语表和费率表结构定义

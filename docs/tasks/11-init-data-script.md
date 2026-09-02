# 11: 一键数据初始化脚本

**What to build:** 提供一条命令完成 XLS → SQLite + Milvus 的全量数据重建。支持指定 XLS 文件路径，输出导入摘要。

**Blocked by:** 03 SQLite 入库 + 费率计算引擎, 08 Embedding 管道 + Milvus 向量库

**Status:** ready-for-agent

## Acceptance criteria

- [ ] `init_data.py` 实现完整的初始化流程
- [ ] 支持命令行参数指定 XLS 文件路径：`python init_data.py --xls ./20260713.xls`
- [ ] 默认 XLS 路径为项目根目录的 `20260713.xls`
- [ ] 执行流程：
  1. 清空 SQLite 数据库（`data/shipping.db`）
  2. 解析所有费率工作表，写入 SQLite
  3. 清空 Milvus collection（`vectordb/milvus_data.db`）
  4. 提取所有规则文本，向量化，写入 Milvus
- [ ] 输出导入摘要：
  - 费率渠道数量（如 "已导入 120 个渠道费率"）
  - 规则文本数量（如 "已导入 250 条规则"）
  - 总耗时
- [ ] 导入失败时有清晰的错误提示（文件不存在、格式错误等）
- [ ] 支持 `--dry-run` 模式：解析但不写入，预览将要导入的数据
- [ ] CLI 测试：执行 `python init_data.py`，验证 SQLite 和 Milvus 数据完整性

## Technical notes

- 使用 `argparse` 处理命令行参数
- 导入流程复用 `data_pipeline/` 中的模块（xls_parser, sqlite_loader, milvus_loader）
- 全量更新策略：先删除再重建（参考 ADR-011 全量更新时清空重建）
- 错误处理：任一步骤失败时回滚已完成的部分（SQLite 用事务，Milvus drop collection）
- 添加 `--verbose` 参数输出详细日志

# 01: 项目脚手架与依赖配置

**What to build:** 从零搭建可运行的项目骨架，确保 `pip install` 一条命令搞定所有依赖，开发者 clone 后能立即开始编码。

**Blocked by:** None (can start immediately)

**Status:** in-progress (implementation complete; dependency installation verification pending due restricted network)

## Acceptance criteria

- [x] 项目目录结构按 PRD 第9节创建（docs/, data/, vectordb/, agent/, data_pipeline/）
- [x] `requirements.txt` 包含 PRD 第10节所有依赖（langgraph, dashscope, pymilvus[lite], pandas, streamlit 等）
- [x] `.gitignore` 排除 data/, vectordb/, .env, __pycache__, .venv 等
- [x] `.env.example` 提供 `DASHSCOPE_API_KEY` 模板
- [x] 创建空的 `__init__.py` 文件（agent/, data_pipeline/）
- [ ] `pip install -r requirements.txt` 成功完成，无报错
- [x] 所有目录和文件已提交到 Git

## Technical notes

- Python 版本要求 >= 3.11（pymilvus[lite] 需要）
- 建议添加 `pyproject.toml` 或使用虚拟环境说明
- `data/` 和 `vectordb/` 目录需要在 .gitignore 中排除，但保留目录结构（添加 `.gitkeep`）

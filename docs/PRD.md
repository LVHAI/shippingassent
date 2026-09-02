# 运费助手 RAG 系统 — 产品需求文档

## 1. 项目概述

### 1.1 背景

易德供应链使用一份大型 Excel 文件（`20260713.xls`，58 个工作表）管理 300+ 国家的运费数据，涵盖专线小包、邮政系列、国际快递三大类产品。业务员需要频繁在 Excel 中查找对应国家和渠道的运费报价，效率低下。

### 1.2 目标

构建一个基于 RAG（检索增强生成）的智能运费查询系统，用户以自然语言提问，系统自动返回精确的运费报价和相关规则说明。

### 1.3 用户

- 内部业务员（1人自用），用于快速给客户报运费
- 可容忍少量不准确，可人工复核

### 1.4 核心价值

- **减少查表时间**：从"打开Excel → 找sheet → 找行 → 算价格"简化为"输入一句话"
- **自动比较**：同一国家/货物类型可能有多个渠道，自动列出对比
- **规则提醒**：自动附带尺寸限制、时效、特殊规则等说明

---

## 2. 数据源

### 2.1 数据文件

| 属性 | 值 |
|------|-----|
| 文件名 | `20260713.xls` |
| 格式 | Excel 97-2003 (.xls) |
| 工作表数 | 58 个 |
| 产品类别 | 专线小包、邮政系列、国际快递 |
| 更新方式 | 整份 Excel 替换，全量更新 |

### 2.2 工作表分类

| 类型 | 示例工作表 | 数据特点 |
|------|-----------|---------|
| 目录索引 | 目录 | 产品类别、路向、渠道概览 |
| 费率表 | 美国专线小包、巴西专线小包DDU、日本专线小包 | 渠道名、重量区间、运费/KG、处理费、货物类型、尺寸要求、时效 |
| 规则说明 | 易德赔付标准、退费额外费要求、航空禁运物品 | 赔偿规则、禁运品列表、退费条件 |
| 邮编分区 | 美国专线偏远邮编、澳洲邮编分区 | 偏远邮编列表、附加费 |
| 通讯录 | 国外邮政通讯录 | 各国邮政客服电话、海关电话 |
| 通用表格 | 理赔申请函、开户表 | 表单模板，不参与查询 |

### 2.3 费率表结构

每个费率工作表通常包含以下信息（表头行不固定，需从数据行推断）：

**表头区域**（前 2-5 行）：
- 渠道名称和备注说明
- 通用提示（如"我司不做库内清关状态筛选拦截服务..."）

**费率数据区域**：

| 字段 | 说明 | 示例 |
|------|------|------|
| 渠道 | 渠道名称，可能合并单元格 | 美国专线小包-普货 |
| 重量 | 重量区间 | 0.050-0.1KG, 1.001-2KG |
| 运费/KG | 每公斤运费 | 96 |
| 处理费 | 每票处理费 | 25 |
| 首重/续重 | 部分渠道使用首重+续重计费 | 首0.5KG 77元，续0.5KG 21元 |
| 产品ID | 系统产品编号 | 42757 |
| 接货类型 | 可接受货物类型 | 可接普货 |
| 计费方式 | 起重、限重、体积重计算方式 | 起重50g，限重10kg；体积重量=长*宽*高cm/8000 |
| 尺寸要求 | 最大/最小尺寸限制 | 最大55*40*35CM；最小15*10CM |
| 参考时效 | 预计送达天数 | 7-15天 |
| 承运商 | 末端承运商 | USPS, DHL, 佐川 |

**规则说明区域**（费率表下方）：
- 申报及税费说明
- 安检要求
- 赔偿标准
- 退件及重派
- 特别提示

### 2.4 数据挑战

1. **表头不统一**：每个工作表的表头行位置不同，列名不同
2. **合并单元格**：渠道名、国家名使用合并单元格，在 pandas 中显示为 NaN
3. **多种计费方式**：有"运费/KG + 处理费"和"首重 + 续重"两种主要模式
4. **混合内容**：同一工作表中混合了费率数据和规则文本
5. **特殊标记**：部分价格显示 `*` 表示不提供服务

---

## 3. 系统架构

### 3.1 整体架构

```
用户输入
   │
   ▼
┌──────────────────────────────────────┐
│         Streamlit Web UI             │
│    (聊天界面，历史对话展示)            │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│         LangGraph 工作流              │
│                                      │
│  ┌─────────┐    ┌──────────────┐     │
│  │ 意图识别 │───▶│  条件路由     │     │
│  │ (LLM)   │    │              │     │
│  └─────────┘    └──────┬───────┘     │
│                        │             │
│           ┌────────────┼──────────┐  │
│           ▼            ▼          ▼  │
│     ┌──────────┐ ┌──────────┐ ┌────┐│
│     │ 费率计算  │ │ 规则检索  │ │追问││
│     │ (Tool)   │ │ (RAG)    │ │    ││
│     └────┬─────┘ └────┬─────┘ └─┬──┘│
│          │             │         │   │
│          └──────┬──────┘         │   │
│                 ▼                │   │
│          ┌────────────┐          │   │
│          │  结果生成   │◀─────────┘   │
│          │  (LLM)     │              │
│          └────────────┘              │
└──────────────────────────────────────┘
               │
     ┌─────────┼─────────┐
     ▼         ▼         ▼
  ┌──────┐  ┌──────┐  ┌──────┐
  │SQLite│  │Milvus│  │ XLS  │
  │费率库│  │规则库│  │解析器│
  └──────┘  └──────┘  └──────┘
```

### 3.2 数据管道

```
XLS 文件
   │
   ▼
┌──────────┐     ┌─────────────────┐
│ XLS 解析  │────▶│  费率表 → SQLite │
│  & 拆分   │     │  结构化存储      │
│          │     └─────────────────┘
│          │     ┌─────────────────┐
│          │────▶│  规则 → Embedding │
│          │     │  → Milvus 向量库  │
│          │     └─────────────────┘
└──────────┘
```

### 3.3 查询流程

```
"美国5kg普货要多少钱"
        │
        ▼
   ┌─────────┐
   │ 意图识别  │  LLM 提取结构化参数
   └────┬────┘
        │
        ├── 国家：美国
        ├── 重量：5kg
        ├── 货物类型：普货
        │
        ▼
   ┌──────────┐
   │ 信息完整性 │  检查：国家✓ 重量✓ 货物类型✓
   │  检查     │
   └────┬─────┘
        │
   ┌────┴────┐
   │ 条件路由  │
   └────┬────┘
        │
   ┌────┴────┐
   ▼         ▼
┌────────┐ ┌────────┐
│费率计算 │ │规则检索 │
│(Tool)  │ │(RAG)   │
└───┬────┘ └───┬────┘
    │          │
    │  SQLite  │  Milvus
    │  查询    │  检索
    │          │
    ▼          ▼
┌─────────────────┐
│  结果组合 (LLM)  │
│  报价 + 规则说明  │
└─────────────────┘
```

---

## 4. 功能需求

### 4.1 核心查询

#### FR-1: 精确运费查询

**输入示例**：
- "美国5kg普货要多少钱"
- "寄到巴西1.5kg带电怎么处理"
- "日本2kg衣服什么价格"

**输出要求**：
- 列出所有匹配渠道的报价（渠道名 + 运费 + 处理费 + 总价）
- 如果有多个渠道，按价格排序展示
- 附带时效信息

#### FR-2: 规则说明查询

**输入示例**：
- "寄到美国有什么尺寸限制"
- "赔偿标准是什么"
- "哪些东西不能寄"

**输出要求**：
- 返回相关规则的自然语言说明
- 引用原始数据来源（哪个工作表、哪个渠道）

#### FR-3: 混合查询

**输入示例**：
- "美国5kg普货，包括时效和尺寸限制"

**输出要求**：
- 报价 + 规则说明一并返回

#### FR-4: 多渠道对比

**输入示例**：
- "美国2kg普货有哪些渠道"

**输出要求**：
- 列出所有可用渠道，对比价格、时效、承运商

#### FR-5: 信息不完整时追问

**输入示例**：
- "寄到美国多少钱"（缺少重量和货物类型）

**输出要求**：
- 追问缺少的参数（重量、货物类型）
- 列出可接受的货物类型供用户选择

### 4.2 数据管理

#### FR-6: 数据导入

- 支持上传新的 XLS 文件
- 自动解析并重建 SQLite 和 Milvus 索引
- 显示导入进度和结果摘要

#### FR-7: 数据浏览

- 可查看所有已导入的渠道列表
- 可查看单个渠道的详细信息

---

## 5. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 工作流框架 | LangGraph | 支持条件路由、多步骤编排 |
| LLM | 通义千问 qwen3.7-max | 中文理解好，工具调用能力强 |
| Embedding | 通义千问 text-embedding-v4 | 与 LLM 同一供应商，中文优化 |
| 向量数据库 | Milvus Lite (pymilvus) | 零部署，数据量小够用 |
| 结构化存储 | SQLite | 轻量单文件，支持 SQL 查询 |
| Web UI | Streamlit | 社区生态好，聊天组件现成 |
| XLS 解析 | pandas + xlrd | 支持 .xls 格式 |

### 5.1 API Key 配置

系统需要以下 API Key，通过环境变量或 `.env` 文件配置：

| 变量名 | 用途 |
|--------|------|
| `DASHSCOPE_API_KEY` | 通义千问 LLM + Embedding 调用 |

---

## 6. 数据模型

### 6.1 SQLite 费率表

```sql
CREATE TABLE channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_name TEXT NOT NULL,          -- 工作表名
    channel_name TEXT NOT NULL,        -- 渠道名
    product_category TEXT,             -- 产品类别（专线小包/邮政系列/国际快递）
    region TEXT,                       -- 路向/大区（欧洲/美洲/亚洲等）
    countries TEXT,                    -- 适用国家（JSON数组）
    cargo_type TEXT,                   -- 货物类型（普货/带电/P货等）
    weight_min REAL,                   -- 重量下限(KG)
    weight_max REAL,                   -- 重量上限(KG)
    price_per_kg REAL,                 -- 运费/KG（NULL表示使用首重续重）
    handling_fee REAL,                 -- 处理费
    first_weight REAL,                 -- 首重重量(KG)
    first_weight_price REAL,           -- 首重价格
    additional_weight REAL,            -- 续重重量(KG)
    additional_weight_price REAL,      -- 续重价格
    product_id INTEGER,                -- 产品ID
    billing_rules TEXT,                -- 计费方式说明
    size_requirements TEXT,            -- 尺寸要求
    transit_time TEXT,                 -- 参考时效
    carrier TEXT,                      -- 承运商
    service_type TEXT,                 -- 服务类型（双清包税等）
    notes TEXT                         -- 备注
);

CREATE TABLE channel_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_name TEXT NOT NULL,
    channel_name TEXT,                 -- 关联渠道（NULL表示通用规则）
    rule_category TEXT,                -- 规则类别（赔偿/禁运/尺寸/退件等）
    rule_content TEXT NOT NULL         -- 规则内容
);

CREATE TABLE post_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country TEXT NOT NULL,
    customer_service TEXT,             -- 客服电话
    service_hours TEXT,                -- 客服作息时间
    customs_phone TEXT                 -- 海关电话
);
```

### 6.2 Milvus 向量库

**Collection: `shipping_rules`**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT64 (主键) | 自增ID |
| embedding | FLOAT_VECTOR(1024) | text-embedding-v4 向量 |
| text | VARCHAR | 原始文本 |
| sheet_name | VARCHAR | 来源工作表 |
| channel_name | VARCHAR | 关联渠道 |
| rule_category | VARCHAR | 规则类别 |
| metadata | JSON | 额外元数据 |

---

## 7. LangGraph 工作流设计

### 7.1 State 定义

```python
class ShippingState(TypedDict):
    user_input: str                    # 用户原始输入
    chat_history: list                 # 对话历史
    
    # 意图识别结果
    intent_type: str                   # rate_query / rule_query / mixed / chitchat
    country: str                       # 目标国家
    weight: float                      # 重量(KG)
    cargo_type: str                    # 货物类型
    missing_params: list               # 缺少的参数
    
    # 查询结果
    rate_results: list                 # 费率查询结果
    rule_results: list                 # 规则检索结果
    
    # 生成结果
    response: str                      # 最终回复
    ask_followup: str                  # 追问内容
```

### 7.2 节点定义

| 节点 | 职责 | 输入 | 输出 |
|------|------|------|------|
| `parse_intent` | 识别用户意图，提取参数 | user_input | intent_type, country, weight, cargo_type, missing_params |
| `check_params` | 检查参数完整性 | intent_type, missing_params | 路由决策 |
| `calculate_rate` | 查询 SQLite，计算运费 | country, weight, cargo_type | rate_results |
| `search_rules` | 向量检索 Milvus | user_input + 上下文 | rule_results |
| `generate_response` | LLM 组合结果生成回复 | rate_results, rule_results | response |
| `ask_followup` | 生成追问 | missing_params | ask_followup |

### 7.3 路由逻辑

```
parse_intent
    │
    ├── missing_params 非空 → ask_followup → END
    │
    ├── intent_type == "rate_query" → calculate_rate → generate_response → END
    │
    ├── intent_type == "rule_query" → search_rules → generate_response → END
    │
    ├── intent_type == "mixed" → calculate_rate + search_rules → generate_response → END
    │
    └── intent_type == "chitchat" → generate_response → END
```

---

## 8. 非功能需求

### 8.1 性能

- 单次查询响应时间 < 10 秒（含 LLM 调用）
- 费率计算本身 < 100ms
- 向量检索 < 500ms

### 8.2 准确性

- 运费计算必须精确（SQLite 确定性查询，不允许 LLM 估算）
- 规则说明允许 LLM 润色，但必须引用原始数据
- 无匹配渠道时明确告知，不编造价格

### 8.3 可维护性

- 数据更新只需替换 XLS 文件并重新运行导入脚本
- API Key 通过环境变量配置，不硬编码
- 日志记录每次查询的完整链路（意图 → 查询 → 结果）

---

## 9. 项目结构

```
运费助手/
├── docs/
│   └── PRD.md                 # 本文档
├── data/
│   └── shipping.db            # SQLite 数据库（自动生成）
├── vectordb/
│   └── milvus_data.db         # Milvus Lite 数据（自动生成）
├── agent/
│   ├── __init__.py
│   ├── state.py               # LangGraph State 定义
│   ├── nodes.py               # 工作流节点实现
│   ├── graph.py               # LangGraph 图定义
│   └── tools.py               # 费率计算工具、向量检索工具
├── data_pipeline/
│   ├── __init__.py
│   ├── xls_parser.py          # XLS 解析器
│   ├── sqlite_loader.py       # SQLite 数据导入
│   └── milvus_loader.py       # Milvus 向量导入
├── app.py                     # Streamlit Web UI 入口
├── init_data.py               # 数据初始化脚本
├── requirements.txt           # Python 依赖
└── .env                       # API Key 配置（不提交到 Git）
```

---

## 10. 依赖清单

```
# 核心框架
langgraph>=0.2
langchain>=0.3
langchain-community>=0.3

# LLM & Embedding
dashscope>=1.20              # 通义千问 SDK
openai>=1.0                  # OpenAI 兼容接口

# 向量数据库
pymilvus[lite]>=2.4          # Milvus Lite

# 数据处理
pandas>=2.0
xlrd>=2.0                    # .xls 格式支持
python-dotenv>=1.0

# Web UI
streamlit>=1.30
streamlit-chat>=0.1          # 聊天组件
```

---

## 11. 里程碑

| 阶段 | 内容 | 预期产出 |
|------|------|---------|
| M1 | 数据管道 | XLS → SQLite + Milvus 导入完成，数据可查询 |
| M2 | 核心 Agent | LangGraph 工作流跑通，CLI 可对话查询运费 |
| M3 | Web UI | Streamlit 界面可用，支持对话和数据导入 |
| M4 | 优化 | 准确率调优、边界情况处理、UI 美化 |

---

## 12. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| XLS 格式不统一，解析困难 | 数据不完整 | 针对每个工作表编写解析规则，覆盖主要渠道 |
| LLM 幻觉导致报价错误 | 客户投诉 | 运费走确定性计算，LLM 只负责格式化和解释 |
| Embedding 中文语义理解不足 | 规则检索不准 | 增加 metadata 过滤，缩小检索范围 |
| 数据更新后旧索引残留 | 查询结果不一致 | 全量更新时清空重建 |

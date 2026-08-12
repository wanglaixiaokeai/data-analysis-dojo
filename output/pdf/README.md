# 实战公考-酷酷刷-资料分析 OCR 数据

来源：`实战公考-酷酷刷-资料分析11302850(OCR).pdf`（184 页）。

## 文件

- `实战公考-酷酷刷-资料分析11302850_ocr.json`：完整页级 JSON。`pages[]` 每项含 `page`、`type`、`section_hint`、`raw_text`、`text`、`char_count`。
- `实战公考-酷酷刷-资料分析11302850_chunks.jsonl`：检索友好的 JSONL，当前按页切块（每块最多约 1200 字，含页码和字符偏移）。
- `实战公考-酷酷刷-资料分析11302850.sqlite`：SQLite 数据库，包含 `pages`、`chunks` 和 FTS5 全文索引 `pages_fts`、`chunks_fts`。
- `实战公考-酷酷刷-资料分析11302850_manifest.json`：页数、字符数、空页和处理说明。

## SQLite 示例

```sql
-- 搜索包含关键词的页
SELECT p.page, p.section_hint, p.text
FROM pages_fts f JOIN pages p ON p.page = f.rowid
WHERE pages_fts MATCH '增长';

-- 搜索检索片段
SELECT c.id, c.page, c.text
FROM chunks_fts f JOIN chunks c ON c.rowid = f.rowid
WHERE chunks_fts MATCH '比重';
```

## 质量说明

OCR 文本可直接检索，但数字、字母、表格和公式存在识别误差（例如 `0/O`、百分号、表格列顺序）。`raw_text` 保留原始提取结果，`text` 只做了 Unicode 与空白字符的保守规范化。第 2、4 页未提取到文字，保留为空页记录。

当前未生成向量 embedding。若要做语义检索/问答，需要另行选择并运行中文 embedding 模型；SQLite FTS5 已可满足关键词检索和本地调用。

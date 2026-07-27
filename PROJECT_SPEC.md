# 项目规范 | Project Specification

> Version: 1.0
>
> Last Updated: July 2026

---

# 1. 项目目标 | Project Goal

本项目旨在建立一套长期维护的个人日语学习知识库。

This project aims to build a long-term, well-organised Japanese learning knowledge base.

本手册不是教材，也不是聊天记录，而是一份不断完善的参考手册（Reference Handbook）。

---

# 2. 核心原则 | Core Principles

## 2.1 Markdown First

Markdown 是整个项目唯一的源文件（Single Source of Truth）。

所有其它格式，包括：

- PDF
- Word
- EPUB
- HTML

均应由 Markdown 自动生成。

---

## 2.2 Long-term Maintenance

所有内容都应具有长期维护价值。

不要记录：

- 今天和 AI 的聊天内容
- 临时笔记
- 无法复用的信息

应记录：

- 可长期参考的知识
- 常见错误
- 学习经验
- 易混淆内容

---

## 2.3 Quality over Quantity

宁可少写，也不要降低质量。

每个知识点都应做到教材级别，而不是聊天记录的整理。

---

# 3. 手册结构 | Handbook Structure

```text
README.md

PROJECT_SPEC.md

SUMMARY.md

CHANGELOG.md

handbook/

01-Grammar.md

02-Verbs.md

03-Particles.md

04-Expressions.md

05-Vocabulary.md

06-Mistakes.md

07-Listening.md

08-Reviews.md

99-Index.md
```

---

# 4. 编号规则 | ID System

所有知识点使用按章节分类的连续编号。

| 类型 | 前缀 | 示例 |
|------|------|------|
| Grammar | G | G-001 |
| Verb | V | V-001 |
| Particle | P | P-001 |
| Expression | E | E-001 |
| Vocabulary | W | W-001 |
| Common Mistake | M | M-001 |
| Listening | L | L-001 |
| Review | R | R-001 |

编号规则：

1. 每个章节从 001 开始连续编号，不预留空号。
2. 相近或容易混淆的知识点应尽量相邻。
3. 为改善结构，可以在版本更新时重新编号。
4. 发生重编号时，更新包必须提供完整的旧编号到新编号映射。
5. 所有交叉引用和索引必须同步更新。

---

# 5. 语言规范 | Language Rules

正文说明使用中文。

Japanese explanations should be written in Chinese.

README 可以使用中英双语。

所有日语例句必须保留原文。

---

# 6. 日语书写规范 | Japanese Writing Rules

## 6.1 Furigana

原则上：

所有例句中的汉字均应标注平假名。

例如：

> 雨（あめ）が降（ふ）ります。

---

## 6.2 Translation

所有例句必须提供自然中文翻译。

不要逐字翻译。

优先保证符合中文表达习惯。

---

## 6.3 Example Sentences

优先使用：

- DuoRadio
- 阅读材料
- 实际学习内容

必要时可以增加原创例句。

---

# 7. Grammar 章节模板

每一个 Grammar 条目使用统一模板。

```markdown
## G-001 ～ようになる

### 含义

### 用法

### 构成

### 注意事项

### 例句

### 常见错误

### 易混淆表达

### Related

- G-...
- P-...
- V-...
```

每个 Grammar 知识点至少提供两个自然例句。
例句应尽量覆盖不同语境，而不是只替换个别词语。

---

# 8. Verb 模板

```markdown
## V-001 食べる

### 基本含义

### 活用

### 常见搭配

### 常见错误

### Related
```

---

# 9. Vocabulary 模板

```markdown
## W-001 工房（こうぼう）

### 词性

### 含义

### 固定搭配

### 常见表达

### 例句

### Related
```

---

# 10. 交叉引用 | Cross References

不同章节之间应建立引用。

例如：

Grammar：

```
See also:

V-004

P-007
```

避免重复解释。

---

# 11. 更新规则 | Update Rules

每次学习完成后：

1. 更新对应章节。
2. 更新 CHANGELOG。
3. 更新 SUMMARY（如有新增章节）。
4. 保持编号连续，不预留空号。
5. 如有必要，可以按主题重新编号；必须同步更新交叉引用、索引和 CHANGELOG。

---

# 12. AI Editing Rules

任何 AI 修改仓库前，应：

1. 阅读 README。
2. 阅读 PROJECT_SPEC。
3. 阅读 SUMMARY。
4. 阅读目标章节。
5. 在原有基础上修改，不覆盖已有内容。

AI 不应：

- 删除已有知识点
- 在没有编号映射和交叉引用检查的情况下随意修改已有编号
- 重复添加相同内容

---

# 13. Versioning

采用语义化版本：

- v0.x：项目建设阶段
- v1.x：正式版本
- v2.x：重大结构调整

例如：

```
v0.1.0

Repository initialized

v0.2.0

Grammar chapter created

v1.0.0

First complete handbook
```

---

# 14. Future Plans

未来计划包括：

- 自动生成 PDF
- 自动生成 EPUB
- 自动生成网站
- 自动生成 Anki 卡片
- 自动生成索引
- GitHub 自动维护（如工具支持）

---

# 15. Philosophy

这不是一本教材。

也不是聊天记录。

而是一份能够随着学习不断成长的日语参考手册。

Every study session should improve the handbook.

The handbook should become more valuable over time.

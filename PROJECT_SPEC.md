# 项目规范 | Project Specification

> Version: 1.1
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

RELEASE_WORKFLOW.md

AI_CONTENT_EXTRACTION_GUIDE.md

KNOWLEDGE_CLASSIFICATION.md

SUMMARY.md

CHANGELOG.md

handbook/

01-Grammar.md

02-Verbs.md

03-Particles.md

04-Expressions.md

05-Vocabulary.md

06-Mistakes.md

07-Reviews.md

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
| Vocabulary — 名词 | W-N | W-N001 |
| Vocabulary — 动词 | W-V | W-V001 |
| Vocabulary — い形容词 | W-I | W-I001 |
| Vocabulary — な形容词 | W-NA | W-NA001 |
| Vocabulary — 副词 | W-ADV | W-ADV001 |
| Vocabulary — 接续词 | W-CON | W-CON001 |
| Common Mistake | M | M-001 |
| Review | R | R-001 |

编号规则：

1. Grammar、Verb、Particle、Expression、Common Mistake、Review 各自使用连续编号。
2. Vocabulary 按词性子前缀分别独立连续编号：`W-N`、`W-V`、`W-I`、`W-NA`、`W-ADV`、`W-CON`。
3. 已发布编号是永久 ID，不得为了重新排序而修改或重新分配。
4. 每个知识点必须建立只由编号组成的固定 HTML 锚点，例如 `<a id="G-023"></a>`。
5. Index、Related、Reviews 和 Common Mistakes 中的引用必须链接到固定编号锚点，不依赖标题自动生成的锚点。
6. 标题、解释、例句和显示顺序可以修改，但永久 ID 必须保持稳定。
7. 默认禁止重编号。只有发生不可避免的结构迁移时才允许重编号；必须保留旧锚点、提供完整映射、更新全部引用，并在 CHANGELOG 中记录。

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

# 8. Verb 章节规范

Verb 章节用于系统讲解动词分类和各种活用，不作为单词词典。

每一种动词形式使用统一结构：

```markdown
## V-001 动词形式名称

### 含义与用途

### 变化规则

### 特殊变化

### 例句

### 常见错误

### Related
```

学习新的动词形式后，可以在常用动词活用索引中增加相应列。
单个动词的含义、搭配和词义区别应收录在 Vocabulary。

---

# 9. Vocabulary 章节规范

Vocabulary 使用表格，并按词性分组：

- 名词：W-N001
- 动词：W-V001
- い形容词：W-I001
- な形容词：W-NA001
- 副词：W-ADV001
- 接续词：W-CON001

名词建议列：

```markdown
| 编号 | 单词 | 假名 | 中文 | 常见搭配／区别 | 例句 |
```

动词建议列：

```markdown
| 编号 | 单词 | 假名 | 类型 | 中文 | 常见搭配 | 例句 |
```

Vocabulary 记录词义、搭配和词义区别；系统活用规则统一放在 Verbs。
不使用 JLPT 等级标签。

---

# 10. Reviews 与 Common Mistakes 章节规范

Reviews 用于比较、复习、阶段总结和综合练习。

Reviews：

- 不引入新的知识定义；
- 应使用可点击的永久 ID 链接引用已有条目；
- 可提供对比表、自测题、改错题和综合练习；
- 每一道涉及日语的答案必须包含完整日语句子、适当假名、自然中文翻译和简短解析；
- 不得只给句型名称、助词或单个选项作为最终答案；
- 不重复维护其他章节的完整解释。

Common Mistakes：

- 每个条目必须包含完整错误例句和完整正确例句；
- 必须提供自然中文翻译和清楚的错误原因；
- 如存在多个可能意图，应分别提供对应的完整正确句子；
- Related 必须使用可点击的永久 ID 链接。

听力和阅读材料是知识来源，不再作为独立章节。相关知识应按内容归入现有分类。

---

# 11. 交叉引用 | Cross References

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

# 12. 更新规则 | Update Rules

正式更新包必须先按照仓库根目录的 `RELEASE_WORKFLOW.md` 执行。该文件是发布流程的唯一权威来源；未完成仓库检查和验证时，只能生成 Draft，不能标记为 Release。

每次学习完成后：

1. 更新对应章节。
2. 更新 CHANGELOG。
3. 更新 SUMMARY（如有新增章节）。
4. 保持编号连续，不预留空号。
5. 如有必要，可以按主题重新编号；必须同步更新交叉引用、索引和 CHANGELOG。

---

# 13. AI Knowledge Extraction and Editing Rules

聊天记录只是知识来源，不是可直接复制进手册的内容。

任何 AI 从聊天维护 Handbook 时，必须：

1. 阅读 README。
2. 阅读 PROJECT_SPEC。
3. 阅读 RELEASE_WORKFLOW。
4. 阅读 AI_CONTENT_EXTRACTION_GUIDE。
5. 阅读 KNOWLEDGE_CLASSIFICATION。
6. 阅读 SUMMARY 和目标章节。
7. 按提取指南拆分、筛选、搜索、去重和改写候选知识。
8. 按分类指南确定每个知识点的主要归属。
9. 在原有基础上增量修改，不覆盖无关内容。

具体聊天提取流程以 `AI_CONTENT_EXTRACTION_GUIDE.md` 为准。
章节归属的快速判定以 `KNOWLEDGE_CLASSIFICATION.md` 为准。

AI 不应：

- 删除已有知识点
- 在没有编号映射和交叉引用检查的情况下随意修改已有编号
- 重复添加相同内容

---

# 14. Versioning

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

# 15. Future Plans

未来计划包括：

- 自动生成 PDF
- 自动生成 EPUB
- 自动生成网站
- 自动生成 Anki 卡片
- 自动生成索引
- GitHub 自动维护（如工具支持）

---

# 16. Philosophy

这不是一本教材。

也不是聊天记录。

而是一份能够随着学习不断成长的日语参考手册。

Every study session should improve the handbook.

The handbook should become more valuable over time.

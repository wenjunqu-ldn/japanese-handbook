# 日本语学习手册 | Japanese Handbook

> 一个长期维护的个人日语学习知识库。
>
> A long-term Japanese learning knowledge base built from real study sessions.

---

## 📖 项目简介 | About

本仓库用于记录和整理我的日语学习内容。

不同于传统教材，本项目不是按照 JLPT 或课本章节编写，而是基于真实学习过程持续整理和完善，最终形成一本结构清晰、便于复习和长期维护的日语学习手册。

This repository contains my personal Japanese learning handbook.

Instead of following a textbook or JLPT syllabus, the handbook is continuously built from real learning sessions and organised into a structured knowledge base for long-term study and review.

---

## 🎯 项目目标 | Goals

- 建立一套长期维护的日语学习知识库
- 系统整理语法、词汇、动词、助词和固定表达
- 记录学习过程中的易错点和经验
- 支持导出 PDF、Word、EPUB 等格式
- 让任何 AI 都可以持续维护本项目

- Build a long-term Japanese learning knowledge base.
- Organise grammar, vocabulary, verbs, particles and common expressions.
- Record common mistakes and learning notes.
- Support PDF, Word and EPUB generation.
- Keep the project AI-friendly and easy to maintain.

---

## 📂 项目结构 | Repository Structure

```text
README.md                项目介绍 / Project overview

PROJECT_SPEC.md                  项目规范
RELEASE_WORKFLOW.md              强制发布流程
AI_CONTENT_EXTRACTION_GUIDE.md  AI聊天知识提取流程
KNOWLEDGE_CLASSIFICATION.md     知识分类快速指南
SUMMARY.md                       手册目录
CHANGELOG.md             更新日志

handbook/
│
├── 01-Grammar.md
├── 02-Verbs.md
├── 03-Particles.md
├── 04-Expressions.md
├── 05-Vocabulary.md
├── 06-Mistakes.md
├── 07-Reviews.md
├── 08-Duolingo.md
└── 99-Index.md

scripts/                 每日练习生成脚本
docs/                    每日练习网页应用
```

---

## 📚 手册内容 | Contents

本手册主要包括：

- Grammar（语法）
- Verbs（动词）
- Particles（助词）
- Expressions（固定表达）
- Vocabulary（词汇）
- Common Mistakes（易错点）
- Reviews（比较、复习与综合练习）
- Duolingo Vocabulary（Duolingo Sections 1–4 词汇）
- Index（索引）

---

## 🎯 每日练习 | Daily Exercises

本仓库附带一个每日练习应用：每天自动生成 5 道小练习（选择题、填空题、中译日各占一部分），题目全部取自上面的手册内容。

做错的题会回流到仓库，生成器每天预留名额优先复习没掌握的知识点；连续答对后该知识点自动退出复习队列。

详见 [docs/README.md](docs/README.md)。

---

## ✨ 编写原则 | Design Principles

### Markdown First

Markdown 是整个项目唯一的源文件（Single Source of Truth）。

所有 PDF、Word、HTML 或其他格式都应从 Markdown 自动生成。

Markdown is the single source of truth.

All PDFs, Word documents, websites and other formats should be generated directly from the Markdown files.

---

### Stable IDs

所有知识点使用永久编号，例如：

- G-001 Grammar
- V-001 Verb
- P-001 Particle
- E-001 Expression
- W-N001 Vocabulary — 名词
- W-V001 Vocabulary — 动词
- W-I001 Vocabulary — い形容词
- W-NA001 Vocabulary — な形容词
- W-ADV001 Vocabulary — 副词
- W-CON001 Vocabulary — 接续词
- M-001 Common Mistake
- R-001 Review

编号一经使用，不再修改。

Every knowledge point has a permanent ID and should never be renumbered.

---

### Furigana

原则上，所有日语例句中的汉字都标注平假名。

例如：

> 雨（あめ）が降（ふ）ります。

Japanese examples should include furigana whenever appropriate.

---

## 🔄 更新方式 | Workflow

每次学习完成后：

1. 更新对应章节
2. 更新 CHANGELOG
3. 保持编号连续
4. 避免重复内容

After each study session:

1. Update the corresponding chapter.
2. Update the changelog.
3. Keep numbering consistent.
4. Avoid duplicate content.

---

## 🤖 AI Maintenance

本项目设计为 AI 可长期维护的知识库。

任何 AI 在修改内容前，应首先阅读：

- README.md
- PROJECT_SPEC.md
- RELEASE_WORKFLOW.md
- AI_CONTENT_EXTRACTION_GUIDE.md
- KNOWLEDGE_CLASSIFICATION.md
- SUMMARY.md

并遵循项目规范进行更新。

This project is designed to be maintained by AI assistants.

Before making any changes, an AI should read:

- README.md
- PROJECT_SPEC.md
- RELEASE_WORKFLOW.md
- AI_CONTENT_EXTRACTION_GUIDE.md
- KNOWLEDGE_CLASSIFICATION.md
- SUMMARY.md

and follow the project specification.

---

## 📄 License

This repository is maintained as a personal learning project.

Unless otherwise specified, all original notes and explanations are © Wenjun Qu.

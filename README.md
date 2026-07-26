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

PROJECT_SPEC.md          项目规范（AI维护指南）
SUMMARY.md               手册目录
CHANGELOG.md             更新日志

handbook/
│
├── 01-Grammar.md
├── 02-Verbs.md
├── 03-Particles.md
├── 04-Expressions.md
├── 05-Vocabulary.md
├── 06-Mistakes.md
├── 07-Listening.md
├── 08-Reviews.md
└── 99-Index.md
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
- Listening Tips（听力技巧）
- Reviews（复习）
- Index（索引）

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
- W-001 Vocabulary
- M-001 Common Mistake
- L-001 Listening
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

- PROJECT_SPEC.md
- SUMMARY.md

并遵循项目规范进行更新。

This project is designed to be maintained by AI assistants.

Before making any changes, an AI should read:

- PROJECT_SPEC.md
- SUMMARY.md

and follow the project specification.

---

## 📄 License

This repository is maintained as a personal learning project.

Unless otherwise specified, all original notes and explanations are © Wenjun Qu.

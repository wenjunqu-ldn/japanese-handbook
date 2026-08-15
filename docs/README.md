# 每日日语练习 | Daily Japanese Exercises

一个每天自动生成 5 道日语小练习的应用。题目全部来自本仓库的手册内容，做错的题会回流到仓库，用来调整后续练习的出题重点。

> **本文档只覆盖练习应用**（`exercise-generator/`、`docs/`、`.github/workflows/exercise-*.yml`）。
>
> 手册内容的维护规范见 [PROJECT_SPEC.md](../PROJECT_SPEC.md)，发布流程见 [RELEASE_WORKFLOW.md](../RELEASE_WORKFLOW.md)。
>
> 练习应用**只读**手册内容，不会修改 `handbook/` 下的任何文件。

---

## 1. 工作方式 | How it works

```text
handbook/*.md
    │   题库来源：语法、助词、固定表达、词汇、Duolingo 词汇
    │
    │   exercise-generator/itembank.py
    │       解析 Markdown → 结构化题库
    ▼
exercise-generator/generate_exercises.py
    │   每天挑 5 个知识点并生成题目
    ▼
docs/data/exercises/YYYY-MM-DD.json
    │
    ▼
docs/index.html （网页应用）
    │   答题 → 判分 → 生成结果 JSON
    │   提交 GitHub Issue（标签 exercise-result）
    ▼
exercise-generator/ingest_mistakes.py
    │   记录错题 → docs/data/mistakes.jsonl
    │
    └──────► 影响明天的出题权重（错题优先复习）
```

---

## 2. 题型 | Exercise formats

| 题型 | 说明 |
|------|------|
| 选择题 MCQ | 给出单词或句型，从四个选项中选出正确的中文含义；汉字词也可能考读音 |
| 填空题 Fill in the blank | 从例句中挖掉目标词或句型，需要填回去；答案接受汉字或假名 |
| 翻译题 Translation | 给出中文句子，写出对应的日语句子；判分时忽略假名标注、空格和标点 |

每天固定 5 题，且至少包含选择题、填空题和翻译题各一道。

---

## 3. 复习机制 | Review logic

- 答错的知识点会写入 `docs/data/mistakes.jsonl`。
- 生成器每天**预留 2 个名额**给「还没掌握」的知识点，因此错题一定会很快再出现，而不是靠概率碰运气。
- 答对会记入 `docs/data/attempts.jsonl`；当某个知识点的答对次数追平答错次数，它就退出复习队列，回到普通题库。
- 最近 10 天出过的知识点会降低权重，避免天天重复。

---

## 4. 日常使用 | Daily use

1. 打开网页应用（见下方部署说明），默认显示当天的练习。
2. 做完 5 题后点击「提交答案」查看判分与解析。
3. 点击「把错题记录到 GitHub」——会打开一个预填好的 Issue，直接提交即可。
4. GitHub Actions 会自动记录结果、关闭 Issue，并让错题进入明天的复习队列。

翻译题和填空题的判分是机械比对，同一句话常常有多种正确写法。如果你的答案其实也对，可以勾选「我的答案其实也对，按答对记录」，结果会按答对提交。

---

## 5. 部署 | Deployment

网页应用是纯静态的，可以直接用 GitHub Pages 托管：

1. 仓库 **Settings → Pages**。
2. Source 选择 **Deploy from a branch**。
3. Branch 选择默认分支，目录选择 **/docs**。
4. 保存后访问 `https://<用户名>.github.io/japanese-handbook/`。

本地预览：

```bash
cd docs
python3 -m http.server 8000
# 打开 http://localhost:8000
```

---

## 6. 自动化 | Automation

| 工作流 | 触发条件 | 作用 |
|--------|----------|------|
| `.github/workflows/exercise-daily.yml` | 每天英国时间早上 8 点，也可手动触发 | 生成当天练习并提交到仓库 |
| `.github/workflows/exercise-ingest-results.yml` | 带 `exercise-result` 标签的 Issue | 记录答题结果、更新错题统计、关闭 Issue |

首次使用前，请在仓库里创建 `exercise-result` 标签（网页应用生成的 Issue 链接会自动带上该标签，但标签本身需要存在）。

结果 Issue 只接受**仓库所有者**提交，避免他人污染学习记录。

### 关于每日生成的时间 | About the daily schedule

GitHub Actions 的 cron 按 UTC 计算，且**不跟随夏令时**，所以单个 cron 表达式无法全年固定在英国时间早上 8 点。

因此工作流配置了两个 cron，并在第一步判断伦敦当地时间，只保留正好是 8 点的那次：

| Cron (UTC) | 夏令时 BST | 冬令时 GMT | 结果 |
|-----------|-----------|-----------|------|
| `0 7 * * *` | 08:00 ✅ | 07:00 ✗ | 夏季执行 |
| `0 8 * * *` | 09:00 ✗ | 08:00 ✅ | 冬季执行 |

每天实际只会有一次真正执行；另一次会在第一步跳过，日志中会写明原因。手动触发（workflow_dispatch）不受此限制，任何时间都会执行。

练习日期同样使用英国时区（`TZ=Europe/London`）。

---

## 7. 手动运行 | Manual commands

```bash
# 生成今天的练习
python3 exercise-generator/generate_exercises.py

# 生成指定日期，并覆盖已有文件
python3 exercise-generator/generate_exercises.py --date 2026-08-20 --force

# 查看解析出的题库（调试用）
python3 exercise-generator/itembank.py > /tmp/bank.json

# 手动录入一次答题结果
python3 exercise-generator/ingest_mistakes.py --body-file result.txt
```

---

## 8. 数据文件 | Data files

| 文件 | 内容 |
|------|------|
| `docs/data/exercises/YYYY-MM-DD.json` | 每天的 5 道题（含答案与解析） |
| `docs/data/index.json` | 已生成的日期列表 |
| `docs/data/history.jsonl` | 每天出过哪些知识点 |
| `docs/data/mistakes.jsonl` | 错题记录 |
| `docs/data/attempts.jsonl` | 全部答题记录（对与错） |
| `docs/data/stats.json` | 错题统计汇总 |

---

## 9. 扩充题库 | Extending the item bank

题库直接来自手册，因此**给手册增加内容就等于给练习增加题目**，不需要改代码：

- 语法、助词、固定表达：新增带固定锚点的条目，并至少写一个「> 日语例句 / > 中文翻译」形式的例句。
- 词汇：在 `05-Vocabulary.md` 的对应词性表格中增加一行。
- Duolingo 词汇：在 `08-Duolingo.md` 中增加一行；表格按 Duolingo Section 分组。

只有带例句的条目才会进入题库——填空题和翻译题都需要例句。

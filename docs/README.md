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
    │   语法、动词、助词、固定表达、词汇、易错点
    │
    │   exercise-generator/itembank.py
    │       解析 Markdown → 结构化题库（含易混淆关系）
    ▼
exercise-generator/generate_exercises.py
    │   按掌握度挑 5 个知识点，再决定题型并生成题目
    │   生成后做质量检查，不合格则整天作废
    ▼
docs/data/exercises/YYYY-MM-DD.json
    │
    ▼
docs/index.html （网页应用）
    │   答题 → 判分 → 生成结果 JSON
    │   提交 GitHub Issue（标签 exercise-result）
    ▼
exercise-generator/ingest_mistakes.py
    │   记录对错 → docs/data/mistakes.jsonl + attempts.jsonl
    │
    └──────► 更新掌握度 → 决定明天出哪些知识点
```

---

## 2. 题型 | Exercise formats

| 题型 | 来源 | 说明 |
|------|------|------|
| 选择题 MCQ | 语法／助词／表达／词汇 | 选出正确的中文含义或读音 |
| 填空题 Fill in the blank | 例句 | 从例句中挖掉目标词或句型；答案接受汉字或假名 |
| 翻译题 Translation | 例句 | 给出中文，写出日语；判分忽略假名标注、空格和标点 |
| 改错题 Correction | `06-Mistakes.md` ／ 你自己的错题 | 给出错误句子，改写成正确说法 |
| 变形题 Conjugation | `02-Verbs.md` V-004 | 写出或选出动词的ます形／て形 |

每天 5 题，题型由「哪些题型对该知识点可行」和「今天已经出过哪些题型」共同决定，因此不会出现 5 题全是选择题的情况。

### 干扰项从哪来 | Where distractors come from

选择题的错误选项按以下优先级挑选，越靠前越有迷惑性：

1. **手册自己记录的易混淆项**——解析 `易混淆表达` 和 `Related` 小节，既认编号（`G-030`）也认名称（`～ように`）。因此 `ために` 的干扰项会是 `ように`，而不是随便一个无关语法。
2. 同词性
3. 同类别

变形题的干扰项是**同一个动词的错误变形**，按错用动词类型的规则生成，例如 `遊ぶ` 的て形会给出 `遊びて`（误用一段规则）、`開ける` 会给出 `開けって`（误用五段规则）。这样考的是活用规则，而不是「哪个词眼熟」。

### 严重程度区分 | Error vs unnatural

`06-Mistakes.md` 用 `❌` 表示真正的错误，用 `△` 表示语法正确但不够自然。两者不会混为一谈：

- `❌` 条目 → 改错题（「请改成正确的说法」）
- `△` 条目 → 「下面哪种说法更自然？」

把 `△` 的句子判成「错误」会教错东西，因此生成器不这样做。

---

## 3. 复习机制 | Review logic

每个知识点维护一份学习状态（`docs/data/mastery.json`）：

```json
{
  "item_id": "G-020",
  "correct_count": 3,
  "wrong_count": 1,
  "streak": 2,
  "last_seen": "2026-08-17",
  "last_wrong": "2026-08-15",
  "mastery": 0.867
}
```

`mastery` 是平滑后的正确率，再按当前连续答对次数上调，因此**最近连续答对**比**很久以前答错**更有分量。选题规则：

- `mastery < 0.75` 视为尚未掌握；生成器每天**预留 2 个名额**给掌握度最低的知识点，保证错题一定会回来，而不是靠权重碰运气。
- 掌握度越低，普通名额里的权重越高。
- 最近 10 天出过的知识点降权；但**尚未掌握的降权很轻**，否则刚做错的题反而会被压下去。
- 已掌握的知识点隔 14 天后重新提权，进入间隔复习，不会永远消失。

同一个知识点再次出现时，会尽量换一个例句或换一种题型，考的是同一个知识而不是同一道题的记忆。

### 用你自己写错的句子出题 | Replaying your own errors

自由作答题（翻译、填空、改错、变形）答错时，网页应用会把**你实际写的那句话**一起上报。之后该知识点再出现时，会优先出成这样一道改错题：

```
这是你在 2026-08-15 写过的答案，请改成正确的说法：
❌ 話しすぎてください
想表达：请注意不要说得太多。
```

两条保护规则：

- **判为「接近」的答案不会被这样回放。** 自由作答判分是机械比对，接近参考答案的写法往往本身就是对的；把它当成错误回放，等于教错东西。这类知识点仍然会回来复习，但用普通题型。
- **只接受该句的参考答案**，不接受该知识点的其他例句——那些例句语法相同但意思不同。

选择题答错不会记录你选了哪个（错误选项本来就在题目里）。

> **注意**：如果仓库是公开的，`docs/data/mistakes.jsonl` 里会包含你写错的句子原文，任何人都能看到。介意的话可以把仓库设为私有（此时 GitHub Pages 需要付费方案，可改为本地运行）。

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
| `.github/workflows/exercise-daily.yml` | 每天 UTC 午夜（`0 0 * * *`），也可手动触发 | 生成当天练习并提交到仓库 |
| `.github/workflows/exercise-ingest-results.yml` | 带 `exercise-result` 标签的 Issue | 记录答题结果、更新错题统计、关闭 Issue |

首次使用前，请在仓库里创建 `exercise-result` 标签（网页应用生成的 Issue 链接会自动带上该标签，但标签本身需要存在）。

结果 Issue 只接受**仓库所有者**提交，避免他人污染学习记录。

### 关于每日生成的时间 | About the daily schedule

练习在**每天 UTC 午夜**生成，对应英国时间冬令时 00:00、夏令时 01:00。

GitHub Actions 的 cron 按 UTC 计算且**不跟随夏令时**，所以锚定在 UTC 反而最简单：全年只需要一个表达式 `0 0 * * *`，不需要任何季节性修正。

练习日期直接用运行机的 UTC 日期（`date -u +%F`）。在 UTC 午夜这一刻，英国的日历日期与 UTC 相同（冬令时 00:00、夏令时 01:00，都还在同一天），因此不需要做时区换算。

手动触发（workflow_dispatch）可以指定任意日期，任何时间都会执行。

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
| `docs/data/mastery.json` | 每个知识点的掌握度状态 |

---

## 9. 扩充题库 | Extending the item bank

题库直接来自手册，因此**给手册增加内容就等于给练习增加题目**，不需要改代码：

- 语法、助词、固定表达：新增带固定锚点的条目，并至少写一个「> 日语例句 / > 中文翻译」形式的例句。
- 词汇：在 `05-Vocabulary.md` 的对应词性表格中增加一行。
- 易错点：在 `06-Mistakes.md` 中增加条目，用 `❌` 标注错误句、`✅` 标注正确句，会自动变成改错题。
- 动词：在 `02-Verbs.md` 的 V-004 速查表中增加一行，会自动进入变形题。

写 `易混淆表达` 或 `Related` 小节同样有用——生成器用它来挑选有迷惑性的干扰项。

带例句的条目才能出填空题和翻译题；改错题和变形题使用各自章节的结构化数据，不需要例句。

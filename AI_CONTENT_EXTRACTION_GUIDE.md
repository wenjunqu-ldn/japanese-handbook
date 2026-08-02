# AI Content Extraction Guide

> Status: Mandatory for AI-maintained content updates  
> Purpose: Define how an AI converts Japanese-learning conversations into durable Handbook content.

## 1. Scope

This guide defines the extraction process. It does not redefine chapter templates, ID formats, furigana rules, or release packaging. Those remain authoritative in:

- `PROJECT_SPEC.md`
- `KNOWLEDGE_CLASSIFICATION.md`
- `RELEASE_WORKFLOW.md`

A conversation is source material, not Handbook content.

## 2. End-to-end workflow

1. Read the repository rules and affected chapters.
2. Scan the relevant Japanese-learning conversation.
3. Extract candidate knowledge points.
4. Split sentences into independently reusable concepts.
5. Reject temporary, contextual, or low-value material.
6. Search the Handbook for existing or related entries.
7. Classify each remaining candidate.
8. Decide whether to add, merge, cross-reference, or discard it.
9. Rewrite accepted content in reference-handbook style.
10. Update affected chapters, Index, and Changelog as required.
11. Validate the complete incremental change.

## 3. Extract candidate knowledge

Look for:

- reusable grammar patterns;
- verb-conjugation rules;
- particle functions and contrasts;
- fixed or highly conventional expressions;
- useful vocabulary, readings, collocations, and nuance;
- representative learner errors;
- comparisons or practice based on existing entries.

Do not automatically preserve:

- complete chat transcripts;
- course plots, character details, or temporary context;
- repeated explanations of the same point;
- one-off typing mistakes with no review value;
- material unrelated to Japanese learning.
- common English-derived loanwords, unless they have a specifically Japanese meaning, formation, contrast, or usage worth explaining.

## 4. Split before classifying

One sentence may contain several knowledge points.

Example sentence:

> エディは静（しず）かに笑（わら）っています。
>
> Eddie is smiling quietly.

Possible knowledge candidates:

- **Vocabulary:** `静（しず）か` — a な-adjective meaning “quiet” or “calm”.
- **Grammar:** a な-adjective changes to `～に` when it modifies a verb: `静（しず）かだ → 静（しず）かに笑（わら）う`.
- **Grammar:** `～ている` describes an ongoing action or state.
- **Example use:** the complete sentence may support one or more existing entries.

Do not create one oversized entry merely because these concepts appeared in the same sentence.

## 5. Test long-term value

A candidate should normally pass at least one test:

- It explains other sentences beyond the original example.
- It represents a recurring learner question.
- It prevents a likely future error.
- It clarifies an important contrast or usage restriction.
- It provides a useful natural example for an existing entry.

Reject or defer candidates that are too contextual, rare, uncertain, or duplicative.

## 6. Search before adding

For every candidate:

1. Search the exact wording.
2. Search the base form and common variants.
3. Search related IDs and nearby topics.
4. Check whether a broader rule already covers it.
5. Check whether only an example, note, or cross-reference is missing.

Possible outcomes:

- **Covered:** make no change.
- **Covered but incomplete:** improve the existing entry.
- **Related but distinct:** add a new entry and cross-reference it.
- **Duplicate:** merge; do not create another definition.
- **Conflict:** resolve against reliable Japanese usage before editing.

Different questions can point to the same entry. Questions about `思（おも）って`, the て-form of `思（おも）う`, and `思（おも）っても` should be decomposed into the existing conjugation rule and, where needed, the separate grammar pattern `～ても`.

## 7. Choose the maintenance action

### Add

Use when the knowledge is reusable, absent, and independently useful.

### Merge or expand

Use when an existing entry needs a clearer explanation, a natural example, a restriction, a common mistake, or a comparison.

### Cross-reference

Use when one sentence supports several chapters but only one chapter should contain the full definition.

### Discard

Use when the material is temporary, redundant, unsupported, or not valuable enough for permanent maintenance.

## 8. Rewrite as Handbook content

Accepted content must:

- stand alone without the original chat;
- use clear reference-style Chinese;
- distinguish rule, meaning, usage, and example;
- preserve natural Japanese;
- avoid conversational filler;
- follow `PROJECT_SPEC.md`.

An incorrect learner sentence may appear only in Common Mistakes, with an explanation and corrected alternatives. It must not be reused as a normal example.

## 9. Multi-category sentences

A sentence may support several entries, but each concept has one primary definition.

Example sentence:

> これはエディからもらったものです。
>
> This is something I received from Eddie.

Possible uses:

- **Grammar or expression:** the pattern `～からもらったものです`.
- **Vocabulary:** an example sentence for `もらう`.
- **Particles:** supporting material for source marker `から`.

Do not duplicate the same full explanation in all three locations.

## 10. Temporary extraction table

An AI may create a working table before editing:

| Source text | Reusable concept | Existing entry | Category | Action |
|---|---|---|---|---|
| 進（すす）む为什么是進（すす）んで | む-ending verbs form the て-form with んで | V-003 | Verbs | Merge or no change |
| わくわくする | Meaning and collocation of わくわく | Search required | Vocabulary | Add if absent |
| 大人（おとな）の人（ひと） | Redundancy and contextual exceptions | Search required | Mistake / Vocabulary | Add or merge |

This is analysis material and should not be committed unless explicitly required.

## 11. Completion checklist

- [ ] Repository rules and affected chapters were read.
- [ ] Candidates were split into reusable concepts.
- [ ] Temporary chat material was excluded.
- [ ] Existing entries and variants were searched.
- [ ] Each new definition has one primary location.
- [ ] Duplicate definitions were not introduced.
- [ ] Accepted content was rewritten in Handbook style.
- [ ] Index, cross-references, and Changelog were updated where required.
- [ ] Release validation was completed under `RELEASE_WORKFLOW.md`.
- [ ] Every new knowledge ID has a stable ID-only anchor.
- [ ] Index and cross-references use clickable permanent-ID links.
- [ ] Published IDs were not changed merely to improve ordering.

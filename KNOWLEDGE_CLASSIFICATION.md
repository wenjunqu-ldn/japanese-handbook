# Knowledge Classification Guide

> Status: Mandatory quick-reference  
> Purpose: Decide where an extracted Japanese-learning knowledge point belongs.

## 1. Decision tree

```text
Reusable sentence pattern, construction, or grammatical function?
├─ Yes → Grammar
└─ No
   Systematic verb classification or conjugation?
   ├─ Yes → Verbs
   └─ No
      Is the central question a particle's function or contrast?
      ├─ Yes → Particles
      └─ No
         Best learned as a conventional or fixed expression?
         ├─ Yes → Expressions
         └─ No
            Word reading, meaning, part of speech, nuance, or collocation?
            ├─ Yes → Vocabulary
            └─ No
               Representative learner error with reusable correction value?
               ├─ Yes → Common Mistakes
               └─ No
                  Comparison or practice based on existing entries?
                  ├─ Yes → Reviews
                  └─ No → Reassess or discard.
```

## 2. Grammar

Use for reusable constructions with a grammatical function and a describable connection rule.

Examples: `～ようになる`, `～たことがある`, `～たら`, `～すぎる`.

## 3. Verbs

Use for systematic verb categories and conjugation.

Examples:

- why `進（すす）む` becomes `進（すす）んで`;
- how 五段（ごだん） verbs form the ない-form;
- exceptions to a conjugation rule.

Individual verb meanings and collocations belong in Vocabulary.

## 4. Particles

Use when the central issue is a particle's function or contrast.

Examples:

- `は` versus `が`;
- embedded-question `か`;
- quotation `と`;
- destination `に` versus `へ`.

If a particle is only one part of a larger construction, keep the full construction in Grammar and cross-reference the particle.

## 5. Expressions

Use for conventional wording best learned as a unit and not requiring a full grammatical system.

Examples: `もう一回（いっかい）`, `何度（なんど）も`, `それとも`, `～ましょうか`.

Do not use Expressions as a catch-all for every sentence pattern.

## 6. Vocabulary

Use for readings, meanings, parts of speech, nuance, collocations, word formation, and lexical contrasts.

Examples:

- `大人（おとな）`;
- `気持（きも）ち悪（わる）い`;
- `静（しず）か`;
- `わくわく`;
- `用意（ようい）` versus `準備（じゅんび）`.

Subcategories and ID rules remain defined in `PROJECT_SPEC.md`.

## 7. Common Mistakes

Use only for representative errors worth reviewing later.

A Mistake entry should identify:

- the learner form;
- why it is wrong or unnatural;
- corrected alternatives;
- any context in which the original form could be acceptable.

Do not create permanent entries for isolated typos or uncertain audio transcriptions.

## 8. Reviews

Use for comparison, recap, self-testing, and integrated practice based on existing IDs.

Reviews must not contain the only complete definition of a new concept. Create or update the primary entry first.

## 9. Tie-break rules

1. Identify the actual learning question, not merely the surface form.
2. Put the full definition where it will be most reusable.
3. Use examples and cross-references elsewhere.
4. Prefer merging into a broader existing rule over creating a narrow duplicate.
5. A sentence itself is not a category; classify the concepts inside it.

## 10. Common misclassifications

- Single verbs placed in Verbs instead of Vocabulary.
- Full grammar patterns placed in Expressions.
- Every unnatural sentence turned into a Mistake entry.
- New definitions introduced only in Reviews.
- Listening or reading material preserved as a permanent source-based chapter.
- The same explanation copied into several chapters.

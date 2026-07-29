# Release Workflow

> Status: Mandatory
>
> This document is the authoritative workflow for creating Japanese Handbook releases.

## 1. Trigger

Any request containing “生成更新包”, “生成下一个更新包”, “发布 Release”, or an explicit version-release request enters **Release Mode**.

A release package must not be created before the repository inspection step is complete.

## 2. Required sequence

1. Inspect the current GitHub repository.
2. Confirm the default branch and current handbook version.
3. Read `README.md`, `PROJECT_SPEC.md`, `SUMMARY.md`, `CHANGELOG.md`, and every file that may be changed.
4. Review the relevant Japanese-learning conversations supplied in the project context.
5. Compare the conversations with the repository and identify:
   - already covered knowledge;
   - missing knowledge;
   - duplicate or conflicting material;
   - structural changes required.
6. Generate incremental changes only.
7. Update `CHANGELOG.md`.
8. Update `SUMMARY.md` and `handbook/99-Index.md` whenever structure or IDs change.
9. Validate IDs, cross-references, file paths, examples, and translations.
10. Generate the release package, manifest, coverage report, scan report, and validation report.

## 3. Release gate

A package may be labelled **Release** only when all of the following are true:

- repository inspected;
- base version confirmed;
- affected files read;
- incremental changes generated;
- changelog updated;
- index and cross-references checked;
- validation passed.

If any requirement fails, the output must be labelled **Draft — Not for Release**.

## 4. Repository as source of truth

The current GitHub repository is the only valid baseline.

Conversation memory, summaries, earlier ZIP files, and previously generated drafts must never be treated as the repository baseline.

## 5. Draft versus Release

### Draft

A draft may contain proposals, outlines, or incomplete changes.

Its file name must clearly contain `draft`, and it must include:

> NOT FOR RELEASE

### Release

A release must be based on the current GitHub repository and pass the release gate.

Recommended file name:

`japanese-handbook-update-vX.Y.Z.zip`

## 6. Package requirements

Every release package must contain:

- `README.md` with application instructions;
- `manifest.json`;
- `CHANGELOG.md` or release notes;
- `COVERAGE_REPORT.md`;
- `SCAN_REPORT.md`;
- `VALIDATION_REPORT.md`;
- the actual incremental update mechanism or changed files.

No placeholder files are permitted.

## 7. Safe application rules

- Never overwrite an unknown repository state blindly.
- The update mechanism must check the expected base version or expected source text.
- Stop with a clear error if the repository does not match the expected baseline.
- Never silently skip a failed replacement.
- Keep a backup or rely on Git before applying the update.

## 8. Content quality rules

- Grammar entries must contain at least two natural example sentences.
- Examples should include appropriate furigana and natural Chinese translations.
- Listening and reading materials are sources of knowledge, not permanent handbook sections.
- Reviews contain comparison, recap, and integrated practice; they do not introduce new definitions.
- Vocabulary remains grouped by part of speech.

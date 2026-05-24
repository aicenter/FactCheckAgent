This is a dataset collected during the AI fact checking project in collaboration with demagog.cz.

The filenames always include the 6 digit demagog claim ID. The dataset includes the following:

### `claims.json`

A JSON file with the full list of all claims that appear in the dataset with their ID, speaker, source debate, claim date, AI fact cehck date, version of the AI agent used for the fact check, etc. Human fact checks released after the AI fact check was performed are stored under `assessment.explanation` (full) and `assessment.shortExplanation` (short).

## Missing human fact checks

For four claim IDs (`24347`, `24521`, `24532`, `24633`), a final published human fact check is missing in Demagog API outputs.

Project context:
- The editor first identified claims for verification.
- The AI agent and human fact-checkers then worked on those claims in parallel.
- Some claims were later not published by Demagog, so no final human fact check is available for these IDs.

### `checklist.csv`

A table where the first column is the claim ID and the other columns correspond questions form the checklist. Each row is a record filled by an annotator. If multiple annotators evaluated the fact check, a row with the same ID appears multiple times.

### `annotations.json`

Textual annotations for the fact checks. They include factcheck filename, span (for docx comments) or question (for xlsx comments) commented on, and the text of the comment.

Annotator identities are anonymised. The `annotator` (and `comment_author`, where it carried a real name) fields use stable opaque labels (`Annotator 1`, `Annotator 2`, …) so that ratings can still be paired across rows for inter-annotator-agreement analysis. The same labelling is used in `checklist.csv`.

### `v1_annotations_analysis.md`

Qualitative cluster analysis of v1 annotation comments (moved from the previous `analysis/report.md` location).

### `AIv1/ai<id>.md`

The main set of the AI fact checks with a fixed version of the v1 fact checking agent. Unlike the other folders, all these were produced with the exact same implementation and gpt-5.1 model.

### `AIv1/ai<id>.log`

The log of the agent behavior created during constructing the fact check.


### `AIv2/ai<id>.md`

The dataset of fact checks by the v2 agent. The agent has been slightly modified during its collection.

### `AIv2/ai<id>.log`

The log of the agent behavior created during constructing the fact check.


### `AIdev/ai<id>.md`

The fact checks from gradualy modified version of AI agent often evaluated by both annotators, mainly to study the inter-annotator match.

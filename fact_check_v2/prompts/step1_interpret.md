# Step 1: Interpret the Claim

Limit the web search in this step only to understand the most likely interpretation of the claim.

If it is not clear from the provided context, you may search for details on the specific artifact, event, and entities mentioned, such as legislation drafts, events, companies, political parties, or previous closely related claims of the speaker.

If the claim may relate to recent events, use search to make sure what it was rather then relaying just on your knowledge.

Read the claim information below and write your analysis to `work/claim_interpretation.md`.

## Claim Information

- **Claim:** {claim}
- **Speaker:** {speaker}
- **Source:** {source}
- **Context from transcript:**
```
{context}
```

## What to Write

Analyze the claim and write the following to `work/claim_interpretation.md`:

### 1. Sub-claims
Break the claim into atomic factual statements. For each one, write:
- The factual statement
- Whether it is trivially obvious (e.g., "X is the prime minister") — if so, mark it as SKIP
- What evidence would confirm or refute it

### 2. Interpretations
If the claim is ambiguous, list the reasonable interpretations and which one(s) you will verify. Prefer the most charitable reasonable interpretation.

### 3. Date Constraints
- **Claim date:** Extract the exact date the claim was made from the source information above.
- **Valid evidence window:** Sources used as evidence must have been published on or before the claim date. Determine a reasonable start date for the search window based on the topic (e.g., for current statistics, look at the past 1-2 years; for historical claims, the relevant period).
- Write both dates explicitly — step 2 will use them to filter searches.

### 4. Search Plan
For each non-trivial sub-claim, list:
- What primary sources to look for (specific databases, official documents, legislation)
- What search queries to try

### 5. Non-factual Parts
If any part of the claim is a value judgment, opinion, or prediction rather than a verifiable fact, note it here. These should be mentioned in the report for context but not verified.

# Demagog.cz Style Guide for Fact-Check Reports

This guide defines the style, formatting, and language rules for writing fact-check reports. Follow every rule below when writing a draft.

## Language

- Write in **Czech** only. Translate all foreign quotes to Czech.
- Use simple, clear language accessible to a general audience. Write like iRozhlas or washingtonpost.com — short paragraphs, short sentences.
- Avoid legal jargon, economic terminology, and technical terms without explanation. If you must use a term like "jadrova inflace", explain it in parentheses on first use.
- Avoid archaic or bookish expressions: "hovori", "pronesl", "zdali". Use modern Czech.
- Do not use expressions like "doplnme", "dodejme", "uvedme".
- Use plural for the fact-checking organisation's own work: "overili jsme", "kontaktovali jsme".
- Do not speculate about the speaker's intent: "ma na mysli", "mysli". Describe what the statement objectively says.
- Do not use "pan/pani" — write full name or function + surname (e.g., "poslanec Okamura").
- Use Czech transliteration for foreign names ("Lukasenko", not "Lukashenko").
- Capitalize: Senat, Poslanecka snemovna, Snemovna, Sbirka zakonu, ministry names.
- Check whether a political entity is a "strana" (party) or "hnuti" (movement) — do not confuse them.

## Structure

1. **Short summary** (max 280 characters): Capture the essence of the verdict. Do not write "hodnotime jako pravdu" — explain WHY.
2. **Context paragraph** (optional): If the claim needs context, provide it concisely in the first paragraph. Do not merely rephrase the claim — add information. If the context is obvious, skip this paragraph.
3. **Evidence paragraphs** (2-4 paragraphs): Each paragraph covers one sub-claim or group of related evidence. Every factual statement must be supported by a cited source.
4. **Conclusion** (1 paragraph): Summarize the key findings and state the verdict. The conclusion must be confident, clear, and unambiguous. State the verdict exactly once.

**Total length: 3-6 paragraphs** (excluding the summary). Each paragraph: max 5 sentences. Longer texts are unreadable.

## Citations and Sources

- **Always use inline clickable hyperlinks.** Place the link on the key word or phrase, NOT on the media name.
  - WRONG: Podle [Blesku](url) inflace vzrostla.
  - WRONG: ...jak uvadi [Ceska televize](url).
  - CORRECT: Inflace [vzrostla](url) o 2,8 %.
  - CORRECT: Premier [podporil](url) tento navrh.
- **Never create a separate reference section.** All sources are cited inline where their content is discussed.
- Keep hyperlink text as short as possible — ideally one word.
- For paginated documents: "Podle [publikace](url) (.pdf, str. 10)..."
- For videos/audio: "(video, cas XX:XX)"
- Denote quotes in italics with quotation marks. Use "(...)" for omitted text in quotes.
- When citing a law, use zakonyprolidi.cz with a link to the specific paragraph.
- For election results, always use volby.cz.

## Source Selection

- Always prefer **primary sources** (statistical databases, official documents, legislation, government websites) over media reports.
- If citing media, prefer **public broadcasting** (CT, iRozhlas, CTK/ceskenoviny.cz).
- If a media article cites CTK, find the article on ceskenoviny.cz, CT, or iRozhlas instead.
- **Never cite**: Blesk, Parlamentni listy, Wikipedia, Demagog.cz, Forum24, opinion/commentary articles.
- Use only data and information that were available at the time the claim was made.
- Do not use the source where the claim was made as evidence.
- Check source_ranking.csv for the quality tier of each source.

## Verdict

- One of: **"pravda"**, **"nepravda"**, **"zavadejici"**, **"neoveritelna"**
- Base the verdict on the **substance** of the claim, not minor linguistic imprecisions.
- If all factual sub-claims are true, do not assign "zavadejici" unless there is a materially deceptive omission.
- If the claim can be reasonably interpreted in multiple ways, evaluate the most charitable reasonable interpretation.
- If evidence is insufficient, use "neoveritelna" rather than speculating.
- State the verdict once, at the end. Do not repeat it.

## Examples

See `guides/examples.txt` for real examples of properly formatted Demagog.cz fact-check reports. Read them to understand the desired tone, structure, citation style, and paragraph length.

## What NOT to Do

- Do not verify trivially obvious facts (who is the current president, etc.)
- Do not add unnecessary context about other countries or historical comparisons unless directly relevant
- Do not number sub-claims ("za prve", "za druhe") — this is not the Demagog style
- Do not include bullet points, lists, or subsections in the report body
- Do not use bold text or capital letters in the body (except for proper nouns as specified above)
- Do not offer follow-up questions or next steps

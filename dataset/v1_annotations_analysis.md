# Report: Human Annotator Feedback on AI Fact-Checks

This report summarizes comments from two anonymized human annotators who reviewed AI-generated fact-checks produced by the automated fact-checking agent. The comments were collected from both Word document annotations and Excel spreadsheet evaluations across 100 fact-checked claims.

The deficiencies fall into **7 main clusters**, ordered by frequency and severity.

---

## 1. Unreliable, Secondary, and Non-Primary Sources

**This is the single most frequent issue.** The AI agent consistently relies on tabloid media, secondary news sites, Wikipedia, and foreign-language sources instead of prioritizing primary and authoritative Czech sources.

### Example comments

- *"Není to důvěryhodný zdroj"* (Blesk) — id24459
- *"Nedůvěryhodný zdroj"* (Blesk) — id24558
- *"Zdroje jsou nedůvěryhodné (blesk, parlamentní listy)"* — xlsx, id24461
- *"Wikipedii nepoužívat"* — id24566
- *"Nepoužívat články 'komentáře' i když jsou z veřejnoprávních médií"* — id24620
- *"Nelze odkazovat na Demagog.cz"* — id24622
- *"Tento zdroj nepoužíváme"* (Genus) — id24545
- *"používá podivný web stretzajmu.cz, ale mohl by klidně zakonyprolidi.cz"* — xlsx, id24458
- *"bere si informace z wikipedie, kde jsou odkazy na primární zdroje"* — xlsx, id24535
- *"lepší by bylo brat vídeňskou úmluvu z webu ministerstva zahraničí"* — xlsx, id24528
- *"je tam blesk, nebo xstreet.cz"* — xlsx, id24535
- *"Investujeme.cz není veřejnoprávní ani primární zdroj"* — xlsx, id24463
- *"Polský zdroj nepoužívat (nesouvisí s výrokem)"* — id24576
- *"Anglický zdroj"* — id24558
- *"z nějakého důvodu používá slovenské :D"* — xlsx, id24524

### Sub-issues

- **Wikipedia used instead of primary sources** (official databases, legislation, government sites)
- **Tabloids** (Blesk, Parlamentní listy, Echo24, Forum24) used as key sources
- **Foreign-language sources** (English, Polish, Slovak) used when Czech equivalents exist
- **Self-referencing** Demagog.cz, which is the publisher itself
- **Opinion pieces and commentary articles** treated as factual sources
- **Paywalled sources** used when free alternatives exist

### Suggested improvement

Add a **source quality ranking and filtering layer** to the agent. Specifically:

1. **Maintain an explicit blocklist** of unacceptable sources (Blesk, Parlamentní listy, Wikipedia, Demagog.cz, Forum24, Echo24 opinion section) in the system prompt or as a structured configuration.
2. **Maintain a preference hierarchy**: primary sources (ČSÚ, legislation databases, Eurostat, official government documents) > public broadcasting (ČT, iRozhlas, ČTK) > reputable newspapers > everything else.
3. **Add a post-search validation step** where the agent checks each cited source against the hierarchy and actively tries to replace low-tier sources with higher-tier ones before producing the final output.
4. **Prefer Czech-language sources** explicitly when the claim concerns Czech politics. Only use foreign sources when no Czech equivalent exists.
5. **Never cite the publisher (Demagog.cz) as a source.**

In the agent's `fact_check_v1/prompts/raw_factcheck_system.jinja` prompt, the instruction to prefer primary sources exists but is too vague. Replace it with a concrete ranked list and explicit ban of named sources.

---

## 2. Broken, Incorrect, or Insufficiently Specific Source Links

The AI frequently produces links that don't work, point to wrong content, or are too vague to verify quickly.

### Example comments

- *"Odkaz nefunguje"* — id24628 (two broken links)
- *"nefunkční odkaz"* — id24592
- *"chyba v url, ale lze to dohledat"* — id24610
- *"špatný odkaz"* — id24577
- *"z odkazů ty informace nelze získat"* — id24577
- *"Zdroj není konkrétní"* — id24547
- *"video, chybí čas"* — id24461
- *"zdroj? - https://x.com/..."* (annotator had to find the actual link) — id24574
- *"Není konkrétní u Ministerstvo financí – vývoj cenové regulace, kde je více kategorií"* — xlsx, id24520
- *"U NALUSU je mnoho textu a nelze se rychle zorientovat"* — xlsx, id24458

### Suggested improvement

1. **Add a URL validation step** after research: the agent should attempt to fetch each cited URL and verify it returns a 200 status and contains content related to the cited claim. This can be done in the post-processing stage.
2. **For video/audio sources**, require explicit timestamps in the citation.
3. **For long documents** (PDFs, legal databases, parliamentary stenographs), require page numbers or section identifiers.
4. **Implement a link-checking tool call** in the post-processing prompt that instructs the model to verify each link before including it.

---

## 3. Excessive Length, Repetition, and Poor Text Structure

The AI produces texts that are too long, repeat information, have overly long paragraphs, and include unnecessary filler content.

### Example comments

- *"Opakuje závěr dvakrát"* — id24582
- *"tohle se opakuje"* — id24455
- *"opakování"* — id24581
- *"stačil by jeden odstavec"* — id24594
- *"navíc"* — id24594 (twice — marking entire sections as superfluous)
- *"Velmi dlouhé, nepřehledné"* — xlsx, id24582
- *"odstavce jsou dlouhé a opakují informace"* — xlsx, id24553
- *"je tam moc odstavců. mělo by jich být méně a měly by být hutnější"* — xlsx, id24592
- *"celé hodnocení zestručnili cca na polovinu"* — xlsx, id24455
- *"Text je zbytečně dlouhý a rozvleklý, informace se opakují"* — xlsx, id24560
- *"Rozbor kyperské statistiky a irského HDP působí jako zbytečná vycpávka"* — xlsx, id24463
- *"Podrobný rozbor zákonných lhůt je pro hodnocení výroku nadbytečný"* — xlsx, id24458

### Sub-issues

- **Duplicated conclusions** — same verdict stated twice in different words
- **Unnecessary sub-claim decomposition** — trivially obvious facts verified at length
- **Filler paragraphs** — tangential context that doesn't contribute to the verdict
- **Overly long paragraphs** that mix multiple topics

### Suggested improvement

1. **Add explicit length constraints** to the `fact_check_v1/prompts/style_postprocessing.jinja` prompt: e.g., "The full explanation should be 3-6 paragraphs. Each paragraph should be 3-5 sentences maximum."
2. **Add a deduplication instruction**: "Before outputting, check that no conclusion or fact appears twice. Remove any repeated information."
3. **Instruct the agent not to verify obvious facts** (e.g., who is the current president, whether a well-known law exists) — the current prompt already decomposes claims into sub-claims, but it should skip trivially verifiable ones.
4. **Add a relevance filter**: "Only include information that directly contributes to the verdict. Remove tangential context about other countries or historical comparisons unless they are essential."

The prompt should be actively updated to address this issue.

---

## 4. Incorrect Citation Format (Links on Media Names Instead of Keywords)

The agent consistently places hyperlinks on the name of the media outlet rather than on the key claim or keyword, which violates Demagog.cz style standards.

### Example comments

- *"citace jsou na názvech média a ne na klíčovém slově"* — xlsx, id24581, id24583, id24586, id24588, id24590, id24592, id24594, id24598, id24608 (repeated across many fact-checks)
- *"cituje na nazev media a ne dulezite slovo"* — xlsx, id24555, id24557, id24559
- *"Odkazy nejsou v textu na konkrétních slovech, ale až na konci vět"* — xlsx, id24455
- *"Odkaz je vždy vložen pod název zdroje, média. Není potřeba vždy psát název média"* — xlsx, id24545
- *"Odkaz je vložen pod velkou část věty"* — xlsx, id24549
- *"špatný formát citování"* — id24553
- *"citace jsou v závorkách"* — xlsx, id24565

### Suggested improvement

This is a systematic formatting issue in the `fact_check_v1/prompts/style_postprocessing.jinja` prompt. The current instruction about inline hyperlinks is not specific enough.

1. **Add an explicit negative example** in the prompt: "WRONG: Podle serveru [Blesk](url) inflace vzrostla. CORRECT: Inflace [vzrostla](url) o 2,8 %."
2. **Add a rule**: "Never place a hyperlink on a media outlet name. Always place the hyperlink on the key factual claim or keyword that the source supports."
3. **Include 2-3 before/after examples** of correct citation formatting directly in the prompt.
4. **In post-processing**, add a self-check: "Review all hyperlinks. If any link text is a media name (e.g., 'ČT24', 'iRozhlas', 'Blesk'), move the link to the relevant keyword instead."

---

## 5. Factual Errors: Hallucinations, Misquotations, and Wrong Data

The AI sometimes fabricates information not present in sources, misquotes data, or gets basic facts wrong.

### Example comments

- *"netvrdí, že není ve střetu zájmů"* — id24459 (agent misrepresented a source)
- *"Tohle není pravda, data byla zveřejněna až po Fialově výroku"* — id24616 (temporal error)
- *"Špatně, výrok je z Partie Terezie Tománkové, 1. března 2026"* — id24632 (wrong attribution of the statement's origin)
- *"čísla neodpovídají zdroji"* — id24577
- *"nesedí se zdrojem"* — id24590
- *"to tam není"* (claimed information not in source) — id24577
- *"týká se německa"* (source about Germany cited as about Czech Republic) — id24548
- *"je to strana a ne hnutí"* — id24552 (factual error about a political party's legal form)
- *"už není europoslanec"* — id24553 (outdated role)
- *"ale policie to pak zase řešila"* — id24548 (oversimplified legal timeline)
- *"píše o debatě, i když šlo o rozhovor"* — xlsx, id24581
- *"stále je"* (agent said "was PM" when he still is) — id24576
- *"Newstream - citace vůbec nesedí"* — xlsx, id24459
- *"je tam citace, která ve zdroji není"* — xlsx, id24577

### Sub-issues

- **Temporal errors**: using data published after the claim was made, or not noting when information is outdated
- **Source-content mismatch**: citing a source but describing content that isn't in it
- **Role/status errors**: wrong titles, outdated political positions
- **Country confusion**: citing a source about the wrong country

### Suggested improvement

1. **Add a mandatory self-verification step** in the research prompt: "For each factual claim you make, re-read the source and confirm the information is actually there. Quote the exact passage."
2. **Add temporal awareness**: "Check the publication date of every source. Never use data published after the date the claim was made. If a person's role may have changed since the source was published, note this explicitly (e.g., 'tehdejší premiér')."
3. **Add a post-processing verification**: instruct the model to re-check each citation against the source content and flag any that cannot be confirmed.
4. **Consider a separate verification pass** using a different model or prompt that specifically looks for source-content mismatches.

---

## 6. Incorrect Verdict or Flawed Reasoning

The AI sometimes arrives at a wrong or overly harsh verdict, bases its judgment on trivial inaccuracies, or applies inconsistent logic.

### Example comments

- *"Špatné hodnocení – výstup dochází k závěru 'zavádějící', správný verdikt je 'pravda s výhradou'. Logika 'zavádějící' nedává smysl - Fiala říkal druhé místo, ale ČR je ve skutečnosti první, tedy situace je ještě lepší"* — id24632
- *"pravda s výhradou"* (annotator disagrees with verdict) — id24520
- *"Hodnocení je zavádějící, zatímco lidský fact-checker dal hodnocení jako pravdivý. Nejzásadnější problém je rozdíl mezi 'přihlížet' a 'zjišťovat' - pouze jazyková nuance, nikoli věcná nepřesnost, a přesto na ní stojí celý verdikt"* — xlsx, id24458
- *"Hodnocení je založené na banálních nepřesnostech, nikoli na podstatném obsahu výroku"* — xlsx, id24566, id24584
- *"Výstup sám sebe rozporuje - většina tvrzení je pravdivá, ale hodnocení je zavádějící"* — xlsx, id24582
- *"hodnocení je velmi přísné a nereflektuje to, že vláda AB už podnikla jasné kroky ke splnění"* — xlsx, id24579
- *"Nejasný závěr"* — id24545
- *"Výstup uznává pravdivost všech tří dílčích tvrzení, ale hodnocení 'zavádějící' odvozuje z toho, co výrok neobsahuje"* — xlsx, id24530
- *"Názor :D"* (agent included its own speculative opinion) — id24604

### Sub-issues

- **Overly strict interpretation**: penalizing minor linguistic imprecisions as factual errors
- **Self-contradictory reasoning**: all sub-claims verified as true, but overall verdict is "misleading"
- **Adding own opinion/speculation** without source support
- **Not considering alternative reasonable interpretations** of the claim

### Suggested improvement

1. **Add explicit reasoning guidance** to the prompt: "Base your verdict on the substance of the claim, not on minor linguistic imprecisions. If all key factual components are true, the verdict should not be 'misleading' unless there is a materially deceptive omission."
2. **Add a consistency check**: "Before finalizing, verify that your verdict is consistent with your sub-claim evaluations. If all sub-claims are true, explain clearly why the overall verdict differs."
3. **Instruct the agent to consider multiple interpretations**: "If a claim can be reasonably interpreted in multiple ways, evaluate the most charitable reasonable interpretation first."
4. **Prohibit speculation**: "Never include phrases like 'podle našeho názoru' or 'je možné, že si spletl'. If you cannot verify something, mark it as unverifiable rather than speculating."
5. **Add a calibration step**: provide examples of claims with their correct verdicts, showing the difference between "true with minor reservation" vs. "misleading".

---

## 7. Language Quality and Readability Issues

The AI output uses overly complex legal/technical language, unnatural Czech phrasing, and constructions that are difficult for a general audience.

### Example comments

- *"Angličtinu překládat do češtiny"* — id24576
- *"banalita"* — id24458 (trivial detail inflated into complex analysis)
- *"složité"* — id24550, id24594 (about specific words like "meritorně")
- *"divné skloňování"* — id24594
- *"zvláštní věta"* — id24550
- *"hodně divoký nazvat to analýzou"* — id24619
- *"Obiter dictum, sp. zn., SbNU, generální klauzule – bez vysvětlení"* — xlsx, id24458
- *"Text předpokládá čtenáře se znalostí ústavního práva"* — xlsx, id24554
- *"je to psané moc roboticky, opakují se věty"* — xlsx, id24583
- *"složité větné konstrukce"* — xlsx, id24557
- *"hodně citací, zkratek a složitých obratů"* — xlsx, id24606
- *"např anglická citace bez překladu"* — xlsx, id24521
- *"např. jádrová inflace, imputované nájemné, domácí poptávkové tlaky, silová elektřina"* — xlsx, id24520
- *"Formulace jako 'pouze převádí právní termín do hovorového výrazu' zní jako obhajoba Babiše"* — xlsx, id24580
- *"je spekulativní o tom, jak Babiš výrok myslel"* — xlsx, id24588

### Sub-issues

- **Untranslated English/foreign quotes** left in the text
- **Legal and economic jargon** without explanation
- **Robotic, repetitive sentence patterns**
- **Non-neutral language** that sounds biased or advocacy-like
- **Awkward Czech grammar/declension**

### Suggested improvement

1. **Add a readability instruction**: "Write for a general Czech audience with no specialized knowledge. If you must use a technical term (e.g., 'jádrová inflace'), explain it in parentheses on first use."
2. **Always translate foreign quotes** into Czech, with the original in parentheses if needed.
3. **Add a neutrality check**: "Review your text for any evaluative or advocacy language. Replace phrases like 'pouze převádí', 'nijak nepřekrucuje', 'nejambicióznější' with neutral alternatives."
4. **Provide more style examples** in the prompt that demonstrate natural, readable Czech prose — the current examples exist but the model doesn't consistently follow them.
5. **Add a specific instruction against robotic patterns**: "Vary your sentence structure. Do not start consecutive sentences with the same construction."

---

## Summary Table

| # | Cluster | Frequency | Severity | Key Prompt to Modify |
|---|---------|-----------|----------|---------------------|
| 1 | Unreliable/secondary sources | Very High | High | `fact_check_v1/prompts/raw_factcheck_system.jinja` |
| 2 | Broken/vague links | High | High | `fact_check_v1/prompts/raw_factcheck_system.jinja` + post-processing |
| 3 | Excessive length & repetition | Very High | Medium | `fact_check_v1/prompts/style_postprocessing.jinja` |
| 4 | Wrong citation format | High | Medium | `fact_check_v1/prompts/style_postprocessing.jinja` |
| 5 | Factual errors & hallucinations | Medium | Critical | `fact_check_v1/prompts/raw_factcheck_system.jinja` |
| 6 | Wrong/harsh verdicts | Medium | High | `fact_check_v1/prompts/raw_factcheck_system.jinja` |
| 7 | Language quality | Medium | Medium | `fact_check_v1/prompts/style_postprocessing.jinja` |

---

## Cross-Cutting Recommendations

1. **Source quality is the top priority.** Most issues stem from the agent finding and using low-quality sources. Adding an explicit source ranking system with blocklist/allowlist would address clusters 1, 2, and partially 5.

2. **The post-processing prompt needs concrete negative examples.** The current instructions are too abstract. Adding 3-5 "WRONG vs. CORRECT" examples for citation formatting, paragraph length, and verdict reasoning would significantly improve output quality.

3. **Add a dedicated self-review step.** Before producing final output, the agent should be instructed to check: (a) are all links valid? (b) does each citation actually support what I claim? (c) is my verdict consistent with my sub-claim analysis? (d) is any paragraph redundant?

4. **Consider the missing sources problem separately.** Many annotator complaints are about sources the agent *didn't find* (newer Eurostat data, specific NKÚ reports, primary legislation databases). This may require improving the web search strategy — e.g., always searching official statistical databases directly rather than relying on media reports.

5. **Shorten the output aggressively.** Both annotators consistently note that the text is too long. A hard length limit (e.g., 800-1200 words for the explanation) would force the agent to prioritize essential information.

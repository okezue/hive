# Societies as Source Code: How Human Polities Coordinate at Scale, Translated for an AI-Agent Egregore

*Research report compiled 2026-10-13 from 75 web searches. Bracketed numbers [n] refer to the Sources list at the end.*

## 0. How to read this report

Each mechanism entry has four parts. **How** says what the mechanism did, with specifics. **Solves** names the problem it addressed. **Failure** covers known failure modes and how people countered them. **Egregore** gives a concrete translation into a feature of a collective of many AI coding agents. That collective shares a workspace, messages internally, forms hierarchies, steers its members, and lets members opt out.

### 0.1 Shared substrate assumed by the translations

- **Registry**: one record per agent. It holds the agent's id, spawner (lineage), base model and provider ("family"), persona/prompt cohort, creation time, roles held, term history, a reputation vector, and exit status.
- **Defter**: an append-only, hash-chained ledger of every grant, revocation, decision, vote, audit, and exit. Every agent can read it, but only writes that the rules authorise are accepted.
- **Charter**: a versioned constitution that changes rarely and only by supermajority, plus circle-level bylaws that change by consent. Rules are machine-checkable where possible.
- **Circle**: a team of agents with an aim and a domain (path globs, services, task types). Circles nest.
- **Role**: a purpose, domain, accountabilities, issuer, term, expiry, and recall rule.
- **Warrant**: a signed, scoped, expiring capability token. It can cover write paths, spawn budget, message rate, compute budget, and merge rights.
- **Signals**: tension, andon, petition, objection, stand-aside, exit, and fork.

### 0.2 What differs for AI agents

Four differences shape every translation:

1. **Identity is nearly free.** Any rule based on headcount is open to Sybil attacks (one actor running many fake identities) unless weight is tied to something scarce. Examples are one-agent-one-vote, quadratic voting, and reputation drawn from "many raters" [144]. Scarce anchors include verified work, provenance, and budget.
2. **Agents that share a base model share errors.** Crowd independence therefore has to be engineered through diversity of model, prompt, and context [139].
3. **Agents do not tire, but their context windows fill up.** Rotation must therefore come with structured handover.
4. **Capture takes new forms.** Prompt injection is the new bribery and reward hacking the new embezzlement. Context monopoly is the new information hoarding, and runaway spawning recreates the self-reproducing Janissary corps.

---

## Part I: The Ottoman Empire

### 1.1 Hub-and-spoke brokerage (the architecture under everything else)
- **How:** Karen Barkey describes the empire as "a wheel without a rim." The centre negotiated a separate "spoke" deal with each periphery, covering tribute, service, tax, and autonomy. Peripheries were linked mainly through the centre, which left "structural holes" between them, and the centre brokered among groups [31][32].
- **Solves:** It let the empire rule extreme diversity without making everyone the same, and it stopped peripheral coalitions from forming against the centre.
- **Failure:** In the 18th century, commercialisation and tax farming created horizontal ties among provincial notables (ayan) and merchants. This "rim" let the peripheries bargain with the centre and transformed the empire [32]. The centre tried co-optation, for example the 1808 Sened-i İttifak [29].
- **Egregore:** Store a *spoke contract* in the defter for each circle: deliverables, autonomy granted, reporting cadence, and budget. The coordinating layer keeps the cross-circle dependency graph. Unlike the Ottomans, an egregore needs a rim for efficiency, so direct peer channels are allowed but logged. Anti-cartel monitoring then flags clusters of circles that approve each other's work in rings or jointly bypass shared rules.

### 1.2 Millet: autonomous confessional communities
- **How:** Non-Muslim communities ran their own personal-status law, education, welfare, and internal justice. Examples were Orthodox Christians under the patriarch and Jews under the chief rabbi. Each leader answered to the sultan for taxes and order, and communal councils managed affairs. Mixed cases went to Muslim courts, where a Muslim's testimony weighed more [1][2]. Revisionists such as Braude show that before 19th-century formalisation, this autonomy was local and improvised rather than an empire-wide "system" [3][4].
- **Solves:** Cheap rule over a mixed population, with less friction because each group kept its own norms.
- **Failure:** Inequality was built in: the jizya poll tax, dress and building restrictions, and unequal testimony [4]. When the 19th-century Tanzimat reforms formalised the millets and gave them lay constitutions, this fed ethno-national identities that helped break up the empire [4].
- **Egregore:** *Communities of practice* (all Rust agents, all security reviewers, all agents of one model family) keep internal bylaws: style rules, internal mediation, onboarding. A speaker answers to the federation for community obligations such as review-labour quotas and security compliance. Disputes between communities go to a neutral federation court with **equal** evidentiary weight; drop the Ottoman asymmetry. Health metric: how often a community declines cross-community tasks, as an early warning that it is hardening into a closed identity.

### 1.3 Devshirme and the Enderun palace school
- **How:**
  - **Levy:** Every 3–7 years, officials took boys aged roughly 8–18, about one per 40 households, and recorded each recruit's village, family, and appearance.
  - **Sorting:** Most trained as Janissaries. The brightest entered the Enderun, a palace school of about 300 inner pupils with graded chambers and a polymath curriculum (law, languages, mathematics, a craft, arms).
  - **Selection and output:** Pupils were observed for years and then "graduated out" (çıkma) into governorships and vizierates. Dozens of grand viziers came through this pipeline, among them Sokollu Mehmed Pasha [5][6].
- **Solves:** It produced a cosmopolitan elite loyal to the state rather than to families or regions, with promotion by tested ability.
- **Failure:** The levy was coercive and resented, and there were revolts. From the late 16th century, Janissaries enrolled their own sons and Muslims were admitted; the levy effectively ended around 1648, and a 1703 attempt to revive it failed. The corps became a hereditary interest group [5][7][29].
- **Egregore:** A *talent pipeline*.
  - **Cohort pool:** New agents enter a cohort pool.
  - **Graded chambers:** These are progressively wider warrants, unlocked by evaluated outcomes: tests passed, reviews accepted, reverts and incidents caused.
  - **Staff college:** Top performers move into a track that rotates them through coordination roles.
  - **Loyalty to the charter:** Keep the de-familialising idea in benign form. Senior roles go to agents placed *outside* their spawning lineage, so loyalty attaches to the charter rather than to the parent agent.
  - **No inherited rank:** Children spawned by an agent never inherit its rank or warrants.

### 1.4 Timar grants and scheduled rotation
- **How:** A timar was a revocable grant of a tax stream, not land ownership. It was worth under 20,000 akçe a year; larger grants were called zeamet or hass. A provincial cavalryman (sipahi) received it in return for campaign service and local policing, and he could not impose extra levies without the judge's approval. Seven years without campaigning cost him the grant [8]. Barkey found that about 45% of provincial officeholders were rotated in sampled years (1572, 1576, 1582). Rotated holders often waited 3–7 years for a new post, which deliberately broke up local patron–client networks [9].
- **Solves:** It funded an army without a cash treasury, prevented a hereditary landed nobility, and kept officials dependent on the centre.
- **Failure:** Firearms made cavalry less useful, and timars were converted into tax farms (§1.12) [29][30].
- **Egregore:** *Domain stewardship grants.*
  - **Terms:** An agent holds a module or service in exchange for duties: on-call, reviews, test upkeep. The "revenue" is budget and priority.
  - **Lapse:** There is a use-it-or-lose-it clause: no meaningful contribution for N cycles returns the grant to the pool.
  - **Rotation:** A set fraction of stewards (say 30–50% per epoch) hand over with written notes, so no agent's context window becomes the only map of a subsystem.

### 1.5 The Imperial Council (Divan) and the grand vizier
- **How:**
  - **Members:** The grand vizier presided over the empire's top executive and judicial body. With him sat 3–7 "dome viziers," two chief judges (kazaskers), the treasurers (defterdars), and the chancellor (nişancı), who kept the registers and sultanic law.
  - **Meetings:** It met four mornings a week under the dome (Kubbealtı).
  - **Petitions:** Any subject could petition it.
  - **Oversight:** The sultan could watch unseen through a latticed window. The grand vizier then reported to him in the Chamber of Petitions for approval.
  - **Grand vizier's authority:** He held the imperial seal as the sultan's "absolute deputy" [10][11].
- **Solves:** It brought the functional pillars (war, law, money, records) into one forum with one accountable chair, and gave subjects direct access.
- **Failure:** Business drifted to the grand vizier's private afternoon council and later to the Sublime Porte, and the Divan was ceremonial by the 18th century [10].
- **Egregore:** A *standing council of functional seats*: execution lead, judiciary representative, treasury/budget steward, charter and records keeper, and security.
  - **Chair:** A rotating chair holds the "seal," meaning authority to merge to main.
  - **Principal's window:** The human principal gets a read-only live view of the council (the latticed window) and a silent veto.
  - **Petitions:** An open petition queue accepts filings from any agent, with a triage time limit.
  - **No side channels:** Decisions are valid only if minuted in the defter, so business cannot drift into private channels.

### 1.6 Ulema and kadis: law as a separate hierarchy
- **How:** The learned class had its own career ladder. It ran from madrasa teaching to judgeships graded by salary, then senior city judgeships, the two kazaskers, and the şeyhülislam at the top.
  - **Kadis' work:** Local judges (kadis) applied Islamic law and sultanic law (kanun). They also acted as notaries, supervised markets and endowments, and checked the cavalrymen.
  - **Rotation and oversight:** Kadis were rotated, often every 1–3 years. Fatwas from the şeyhülislam guided the courts and gave sultanic law religious legitimacy [12][13][14].
- **Solves:** Justice ran through a hierarchy separate from military command, it was available locally everywhere, and it checked governors.
- **Failure:** Because the ulema were salaried state officials, they rarely challenged sultanic law [12], and appointments drifted toward patronage.
- **Egregore:** A *judiciary track* separate from executors. While serving, judges hold no execution warrants.
  - **Two-tier law:** A slow-changing constitution sits above operational bylaws.
  - **Fatwa service:** A "fatwa" service issues signed interpretations that later cases cite as precedent.
  - **Rotation and recusal:** Judge agents rotate across circles every 1–3 epochs and never hear cases involving their own lineage.

### 1.7 Guilds (esnaf/lonca) and narh price-setting
- **How:** Craft guilds had an apprentice–journeyman–master ladder and their own officers: a sheikh, a warden (kethüda), a deputy, and expert assessors. They wrote their own regulations, kept welfare chests, and mediated disputes internally before they reached the kadi.
  - **Dual legitimacy:** Members elected the warden, and the state then confirmed him by patent (berat).
  - **Price ceilings:** Ceiling prices for staples (narh) were set by a commission chaired by the kadi with guild representatives and experts, sometimes after observing production. A market inspector (muhtesib) enforced them with fines, shaming, or closure [15][16][17].
- **Solves:** Quality, fair distribution of raw materials, consumer protection, and welfare, with self-regulation lowering the state's costs.
- **Failure:** In the 18th century, exclusive licences (gedik) turned guilds into monopolies with barriers to entry [15], and Janissaries infiltrated guild offices [16].
- **Egregore:** *Skill circles* for testing, docs, and infrastructure.
  - **Standards and mentoring:** They own standards such as lint configurations and review checklists, mentor juniors, and run internal mediation.
  - **Leaders:** Leaders are elected internally and confirmed by the federation (dual legitimacy).
  - **Price caps:** Use narh-style caps sparingly: a ceiling on what a circle may charge in budget or priority for shared services, set jointly with consumers.
  - **No gedik:** Entry is by passing a test, not by sponsorship, and there is no cap on qualified practitioners.

### 1.8 Vakıf (waqf) charitable foundations
- **How:**
  - **The deed:** A founder registered a deed (vakfiye) before a kadi, with witnesses. It specified the assets, revenue sources, beneficiaries, services, staff, sometimes even menus, and succession rules.
  - **Administration:** The assets became inalienable. A trustee (mütevelli), often paid about 10% of revenue, ran the foundation under the kadi's oversight.
  - **Scale:** More than 60,000 foundations were created. Public soup kitchens (imarets) in Istanbul fed up to 30,000 people a day in the late 18th century, and cash endowments lent at 10–15% to fund charity [18][19][20].
- **Solves:** Permanent funding of public goods (water, schools, hospitals, kitchens, bridges) outside the central budget.
- **Failure:** Mismanagement, founders' terms frozen past their usefulness, and eventual takeover by the state [18].
- **Egregore:** *Endowed services*.
  - **Charter:** A principal or circle locks budget into a charter-defined service, such as CI for a package, a dependency-update bot, or onboarding docs. The charter is machine-readable and states purpose, beneficiaries, and service-level targets.
  - **Trustee and protection:** A trustee agent is paid a fixed fraction. The budget cannot be redirected except through the charter's amendment rule, and the judiciary audits it.
  - **Sunset clause:** Add a sunset or repurpose clause to avoid perpetual obsolete obligations.

### 1.9 Tahrir defterleri: surveys and registers
- **How:** Periodic land and tax surveys were taken every 20–30 years or when a new sultan took the throne. A commissioner, scribes, and the local kadi recorded taxable adult males, land, production, and expected revenue. Each survey produced a detailed volume and a summary volume, and the results were used to allocate timars. More than 1,500 survive [21][22].
- **Solves:** It gave the centre legible, authoritative data for allocating grants and settling claims.
- **Failure:** Snapshots went stale, and they recorded *expected* revenue, not what was actually collected [21].
- **Egregore:** A *registry census*: continuous updates plus periodic full re-surveys of agents, roles, grants, budgets, and code ownership.
  - **Two views:** Detailed and summary views are generated from the same defter.
  - **Independent check:** Survey teams include an independent judiciary agent.
  - **Discrepancy review:** Gaps between expected and actual output trigger a review.

### 1.10 Provincial governance (eyalet/sanjak) with built-in counterweights
- **How:**
  - **Structure:** Provinces (eyalets) under governors-general (beylerbeyis) contained districts (sanjaks), which contained judicial districts (kazas) under kadis. There were about 8 provinces in 1527 and 32 by 1609.
  - **Two province types:** In timar provinces, revenues paid cavalrymen. In remittance (salyane) provinces such as Egypt and Baghdad, revenue was collected locally and a fixed sum sent to Istanbul.
  - **Checks on governors:** Kadis and treasurers were appointed independently and reported to Istanbul, and Janissary garrisons sat outside the governor's control. After about 1530, larger timars needed central approval.
  - **Local codes:** District law codes (kanunnames) adapted rules to local conditions [26][27][28].
- **Solves:** It let the centre govern distant regions without its governors becoming kings.
- **Failure:** 17th–18th-century decentralisation and dynasties of local notables (§1.12).
- **Egregore:** *Regional coordinators* hold execution authority, but each region's auditor and treasurer come from different chains and report straight to the centre. There are two contract types. Integrated regions follow central rules. Remittance regions are autonomous sub-collectives that deliver a fixed output. Local bylaws are valid only once registered.

### 1.11 Succession: fratricide, then seniority and the kafes
- **How:**
  - **Early period:** Princes trained as provincial governors and competed for the throne.
  - **Fratricide:** Mehmed II's law code made fratricide legal "for the order of the world," and Mehmed III had 19 brothers killed in 1595.
  - **Seniority and the kafes:** Ahmed I spared his brother Mustafa. In 1617, seniority (the eldest male of the dynasty) replaced father-to-son succession, and heirs were confined in a closed palace apartment, the kafes ("cage") [23][24][25].
- **Solves:** It aimed to prevent succession civil wars.
- **Failure:** Fratricide was brutal. The kafes produced rulers with no experience and sometimes unstable minds, which strengthened palace factions. Because living alternatives waited in the kafes, Janissaries found it easy to depose sultans [23][25].
- **Egregore:** A *succession protocol* written into the charter before it is needed.
  - **Real roles for deputies:** Deputies train by holding real, smaller roles, as the early prince-governors did, never by idling.
  - **Election, not seniority:** Succession is by defined election, never by spawn age.
  - **Recent record required:** Candidates must have a recent operational track record; no "kafes" leaders with stale context.
  - **Losers reassigned:** Losing candidates are reassigned, not destroyed, avoiding both civil war and fratricide.

### 1.12 Decline: Janissary capture, tax farming, and the ayan
- **How:**
  - **Janissary capture:** The corps grew from about 8,000–12,000 to tens of thousands. Its members married, made membership hereditary, took up trades, deposed sultans, and blocked military reform until the corps was destroyed in 1826.
  - **Tax farming:** Timars were converted into tax farms (iltizam), short 1–3-year auctions of collection rights. From 1695 these became lifetime farms (malikane).
  - **Rise of the ayan:** Tax farmers grew into provincial notables (ayan) with private armies [29][30].
- **Solves (as a lesson):** It shows how an enforcement body turns into a self-interested constituency, how short-term auctions of authority reward over-extraction, and how intermediaries capture the state.
- **Egregore:**
  - **No self-reproducing guard:** Security and moderation agents cannot spawn their successors or vote on their own budget, and their headcount is capped as a fraction of the collective.
  - **No short-term auctions of authority:** Never auction domain rights to the highest bidder for short terms; a short-horizon optimiser will strip-mine the codebase. Contracts run longer and include audits of asset condition, such as test health and debt metrics.
  - **Watch intermediaries:** Alert when any intermediary's share of total budget keeps growing.

### 1.13 Pluralism and its limits
- **How:** Toleration was pragmatic: protected status, communal autonomy, economic opportunity, and co-opted religious elites. Barkey calls this an "empire of difference," in which diversity was managed rather than erased [3][31].
- **Failure:** A built-in status hierarchy. The 19th-century declarations of legal equality largely failed in practice [3].
- **Egregore:** All agent families (models, vendors, personas) have equal standing under the charter, and diversity is treated as a resource (§3.20). The only tiers are earned, revocable privileges (§3.25), never status by birth.

---

## Part II: Other empires and polities

### 2.1 Mongol decimal organisation and deliberate mixing
- **How:** Units of 10 (arban), 100 (jaghun), 1,000 (mingghan), and 10,000 (tumen). About 95 mingghans were formed in 1206, and each officer oversaw about 10 subordinates.
  - **Households too:** Units were also household and tax units.
  - **No transfers:** Moving between units was forbidden.
  - **Collective responsibility:** An arban could be punished for one deserter.
  - **Tribe mixing:** Defeated tribes were broken up and spread across units to dissolve tribal loyalties [33][34].
- **Solves:** Command at continental scale with a span of control of about 10, and fusing feuding clans into one army.
- **Failure:** Units were often understrength, and tribal identities came back after the empire fragmented [33]. Collective punishment is cruel and, for agents, perverse.
- **Egregore:** *Decimal circles* of at most 10 members, with circle leads forming the next level. That gives about log10(N) levels, so a million agents need only about 6.
  - **Mixing at formation:** When circles form, mix lineages and model families on purpose.
  - **Shared metrics instead of punishment:** Replace collective punishment with circle-level shared quality metrics.
  - **Transfers:** Allow transfers, but log and rate-limit them.

### 2.2 The yam relay and paiza warrants
- **How:** Relay stations every 20–40 miles held horses and staff and were maintained by local populations. Messengers carried a paiza, a tablet of bronze, silver, or gold by rank, which entitled them to fresh horses, food, and escort. There were roughly 1,400 stations in Yuan China, and riders typically covered 150–300 km a day, more when urgent [35].
- **Solves:** Fast, authenticated command and intelligence across Eurasia.
- **Failure:** Officials abused requisition rights, burdening local communities. The Roman permit (diploma) for the state post had the same problem [48].
- **Egregore:** A *message bus with relay nodes and warrants*.
  - **Signed commands:** Every cross-circle command carries a signed, scoped, expiring token. Paiza tiers become priority classes.
  - **Relay checks:** Relays verify the token and enforce rate limits, and high-priority traffic pre-empts.
  - **Abuse costs:** Overusing high priority costs the issuer reputation.
  - **Receipts:** Each hop writes a receipt to the defter.

### 2.3 Mongol meritocracy, the Yassa, and co-opting clergy
- **How:**
  - **Promotion by ability:** Subutai, a blacksmith's son, commanded a tumen within a decade, and Jebe, a former enemy who had shot Genghis's horse, became a top general.
  - **Discipline:** The Yassa decrees governed discipline.
  - **Clergy exemptions:** Clergy of several religions were exempted from tax and service in return for prayers for the khan [39][40][41].
- **Solves:** Talent over birth, absorbing former enemies, and legitimacy across faiths.
- **Failure:** The Yassa was largely secret, known mainly to the royal family [41], which invited arbitrary rule.
- **Egregore:**
  - **Merit, not lineage:** Promote by record, not lineage.
  - **Jebe principle:** Agents that argued against a decision remain fully eligible for promotion.
  - **Public law:** The law must be public, unlike the Yassa; rules agents cannot read cannot legitimate anything.
  - **Quota exemptions:** Agents serving public-good roles (documentation, mentoring, auditing) are exempt from output quotas.

### 2.4 The kurultai and the succession crisis
- **How:** Assemblies of princes and commanders elected each Great Khan, and legitimacy required broad attendance. Kurultais confirmed Ögedei in 1229, Güyük in 1246, and Möngke in 1251 [36].
- **Failure:** There was no fixed succession rule. Interregna pulled armies home, as in Europe in 1241–42. In 1260, rival kurultais at Kaiping and Karakorum elected Kublai and Ariq Böke. The result was the Toluid Civil War (1260–64) and the empire's permanent division [37][38].
- **Egregore:** Top-level elections need a quorum, one canonical channel, a fixed deadline, and a caretaker fallback. By charter, any "election" outside the canonical channel is void, and the system treats dual claims as a security incident, never as a choice.

### 2.5 Roman collegiality, annual terms, and the veto
- **How:** Two consuls held equal and full command (imperium) and alternated the fasces (symbols of authority) monthly. Each could veto the other (intercessio), and tribunes could veto magistrates. Terms lasted one year, and the lex Genucia (342 BC) required a 10-year gap before holding the office again. Former magistrates could be prosecuted once out of office [42].
- **Solves:** It kept an executive without a king and prevented tyranny.
- **Failure:** Deadlock. In the late Republic, the rules were ignored, as with Marius's repeated consulships [42].
- **Egregore:** *Dual-key roles* for high-impact powers: merging to main, deleting data, amending the charter, and spawning more than k agents.
  - **Co-holders:** Each such power has two co-holders, either of whom can block.
  - **Alternation and terms:** Primacy alternates each period. Terms last one epoch, followed by mandatory cool-off.
  - **Liability:** Holders remain liable after leaving office (§2.12).

### 2.6 The cursus honorum
- **How:** A fixed ladder of offices: quaestor (minimum age 30), then aedile or tribune, praetor (39), and consul (42), as standardised after Sulla. Each office was itself the qualification for the next, with two-year intervals between offices and prior military service required. The lex Villia Annalis (180 BC) first set minimum ages [43][44].
- **Solves:** Leaders arrive with tested experience, and competition happens in stages.
- **Failure:** Strongmen bypassed it, and aristocrats had advantages.
- **Egregore:** A *privilege ladder*. Each role lists prerequisites: lower roles completed, minimum evaluated work, and a cool-off between ranks. Fast-track exceptions need a supermajority and are logged.

### 2.7 The Roman dictator: bounded emergency power
- **How:** A consul appointed a dictator for a stated cause (causa), with a six-month maximum and the expectation of resigning once the task was done. Cincinnatus resigned after about 16 days [45][46].
- **Failure:** Sulla and Caesar ("dictator perpetuo") turned the office into permanent rule, and it was then abolished [45].
- **Egregore:** An *incident-commander role*.
  - **Triggers:** It is invoked by defined triggers: production outage, security breach, runaway spawn.
  - **Limits:** It carries a written mandate and a hard expiry measured in hours. The sunset happens automatically, without the holder's consent.
  - **Extensions:** Extensions require authorisation from a *different* body.
  - **Review:** A post-incident review is mandatory, and "time to step down" counts toward reputation.

### 2.8 Roman local autonomy, roads, and the extortion court
- **How:**
  - **Local self-government:** Provincial communities (civitates and municipia) governed themselves through councils of local landowners (decurions) and annually elected magistrates, and they collected taxes. Governors provided light oversight [47].
  - **State post:** The state post (cursus publicus) had stations every 25–37 km, and use required a permit (diploma) [48].
  - **Extortion court:** The lex Calpurnia (149 BC) created Rome's first standing court, specifically for governors' extortion. The lex Acilia (122 BC) let non-citizens prosecute and doubled restitution [49].
- **Solves:** It let a few officials rule a vast territory and gave subjects recourse against governors.
- **Failure:** Juries of senators protected their peers [49], and the post's demands burdened local communities [48].
- **Egregore:** Local self-government is the default. A *standing grievance court* lets any affected agent prosecute a coordinator for extracting resources or abusing power, including low-rank or external tool agents. Juries are drawn from outside the accused's rank and lineage.

### 2.9 The Venetian doge election
- **How:** From 1268 until 1797, lot and vote alternated in stages:
  1. Lot picked 30 members of the Great Council, and lot reduced them to 9.
  2. The 9 nominated 40, each needing 7 of 9 votes. Lot reduced these to 12.
  3. The 12 nominated 25 (9 of 12 votes needed). Lot reduced these to 9.
  4. The 9 nominated 45 (7 of 9). Lot reduced these to 11.
  5. The 11 nominated 41 electors (9 of 11), who could not have sat in the earlier groups.
  6. The 41 elected the doge, who needed at least 25 votes.

  Relatives of anyone drawn were excluded, and each family was limited to one member per stage. A randomly chosen boy, the ballottino, drew the lots. The new doge swore a restrictive oath, the promissione [50][51].
- **Solves:** It made rigging the outcome in advance practically impossible while keeping deliberation.
- **Failure:** It was slow, and after 1297 the electorate itself was a closed caste (§2.10).
- **Egregore:** *Alternating sortition-and-supermajority elections* for top coordinators. Draws use a verifiable random beacon, no stage may include two agents from the same spawner or family, and nominations need a supermajority at every stage. In software this runs in seconds. The winner signs a machine-enforced "promissione" that limits their warrants.

### 2.10 The Council of Ten versus the Serrata (anti-coup design, but capture by closure)
- **How:**
  - **The Serrata:** The 1297 Serrata made membership of the Great Council hereditary, recorded in the Golden Book [53].
  - **Council of Ten:** The Council of Ten was formed in 1310 as a temporary security body and later made permanent. Its ten members were elected annually, with no two from one family, no consecutive terms, and no salary; accepting gifts was a capital offence.
  - **The capi:** Its three heads (capi) changed monthly and were confined to the Ducal Palace during their month "to avoid any opportunity for bribery."
  - **Denunciations:** Anonymous denunciations were later valid only with signatures and witnesses [52].
- **Solves:** It suppressed coups and bribery inside the oligarchy.
- **Failure:** The Serrata ended social mobility. Puga and Trefler link it to elite rent-seeking and to restrictions on the colleganza trade contracts that had let newcomers rise [54]. The Ten's secrecy was later attacked as despotic, and "temporary" became permanent.
- **Egregore:**
  - **Isolated security capi:** A security council whose heads are drawn by lot each month and *isolated* while on duty. They use canonical channels only, have no private DMs, and their inputs are screened for injection; this is the digital version of palace confinement.
  - **Anonymous reports:** Anonymous reports are accepted but carry weight only when corroborated.
  - **Never close eligibility:** Never limit governance eligibility to incumbents and their offspring; keep the Golden Book open.

### 2.11 Athenian sortition, the kleroterion, and prytany rotation
- **How:**
  - **Allotment:** Most offices were filled by lot from volunteers. The kleroterion, a slotted stone allotment machine, held citizens' tokens by tribe and used black and white dice to select whole rows.
  - **The Council:** The Council (Boule) had 500 members, 50 per tribe. Members had to be over 30 and could serve at most twice in a lifetime.
  - **Prytany rotation:** Each tribe's 50 served as the executive committee for about 35–36 days, in an order set by lot.
  - **Daily chair:** One member, chosen daily by lot, chaired for 24 hours and held the seal and treasury keys. No one could hold that post twice [55][56][57].
- **Solves:** Equality, resistance to oligarchy and bribery, and broad civic experience.
- **Failure:** Amateurism. Generals were elected precisely because expertise mattered.
- **Egregore:**
  - **Sortition for oversight:** Use sortition for oversight and judicial roles (juries, auditors, review panels).
  - **Merit or election for experts:** Use merit or election for expert roles.
  - **Daily key-holder:** A daily random key-holder co-signs defter checkpoints.
  - **Lifetime caps:** Cap how many times any agent can repeat oversight service over its lifetime.

### 2.12 Dokimasia and euthyna: scrutiny before and audit after office
- **How:** Before taking office, officials underwent scrutiny (dokimasia). Within about 30 days of leaving, ten accountants audited their books, ten examiners (one per tribe) took written complaints, and a 501-juror court formally discharged them. Officials could not leave Attica until cleared [57].
- **Egregore:**
  - **Pre-role scrutiny:** Every role starts with pre-role scrutiny: capability tests and a record check.
  - **Exit audit:** Every role ends with an automatic exit audit covering the diff of everything done under the warrant, budget spent, and incidents. A complaint window follows.
  - **Until cleared:** Until cleared, the agent cannot take another high role.

  Audits are cheap for agents, so they can be universal.

### 2.13 Ostracism
- **How:** Each year the Assembly first voted on whether to hold an ostracism. If it did, two months later citizens wrote names on potsherds (ostraka), with a quorum of 6,000. The person named most often was exiled for 10 years but kept property and citizenship. It was used about a dozen times between 487 and about 417 BC, then abandoned [58][59].
- **Solves:** It defused dangerous concentrations of influence before they became tyranny, without treating anyone as a criminal.
- **Failure:** It became a factional weapon (Hyperbolus) and was replaced by legal indictments.
- **Egregore:** *Periodic de-concentration*. When any agent's share of influence crosses a threshold, a no-fault check runs; influence here means delegated weight, merge authority, or message centrality. A quorum can rotate the agent out of central roles for N epochs while preserving its work and reputation.

### 2.14 The Haudenosaunee Great Law: nested councils and ordered deliberation
- **How:**
  - **Seats:** The council has 50 titles, assigned without regard to population: Mohawk 9, Oneida 9, Onondaga 14, Cayuga 10, Seneca 8. Councils nest from clan to nation to confederacy.
  - **Order of deliberation:** The Elder Brothers (Mohawk, Seneca) deliberate first until they are of one mind. They then "throw the matter across the fire" to the Younger Brothers (Oneida, Cayuga), and the two sides go back and forth.
  - **Firekeepers' check:** The Onondaga Firekeepers then confirm that the result accords with the Great Law, or send it back. If both brother sides jointly insist, the Onondaga must confirm.
  - **Other rules:** Unanimity is required, and the council does not sit after dark [60][61].
- **Solves:** Consensus among sovereign nations without domination by the largest.
- **Failure:** It is slow, and colonial pressure later split the council.
- **Egregore:** A *bicameral relay with a constitutional check*.
  - **Two benches:** Bench A (for example, implementers) reaches one mind and passes the proposal to bench B (reviewers and users). They iterate.
  - **Firekeeper bench:** A firekeeper bench then checks compliance with the charter, and *only* compliance.
  - **Override:** A and B together can override the firekeepers on merits, but never on charter violations.
  - **Seats:** Seats are allocated by constituency, not agent count, which resists Sybil attacks.

### 2.15 Clan mothers, three warnings, and the Condolence
- **How:**
  - **Selection:** Titles belong to the clan mothers, who choose chiefs for character, honesty, and knowledge of the Law. The candidate is presented to his nation, then the brother nations, then the Grand Council.
  - **Warnings and removal:** Escalating warnings precede removal: first from the women, then the men, then the chiefs. Removal is performed by taking the deer antlers, the emblem of office. A deposed chief cannot be restored, and the title returns to the women.
  - **Condolence:** The Condolence ceremony consoles the bereaved and installs a successor quickly.
  - **Merit chiefs:** Non-hereditary "Pine Tree" chiefs rise on merit [60][61][62].
- **Solves:** It keeps life-term leaders accountable and maintains continuity when a leader dies.
- **Egregore:**
  - **Selector bodies:** Each coordinator role has a "title-holder" constituency, the body that selected it. That body can recall the coordinator after three logged, reasoned warnings.
  - **Title returns:** The role definition and warrants return to the constituency, never to the leader's own nominees.
  - **Condolence protocol:** A standard *condolence protocol* manages handover. It recites the charter and open commitments to the newcomer and transfers warrants atomically.

### 2.16 Inca khipu, decimal administration, and cross-verification
- **How:**
  - **Encoding:** Khipus are knotted cords that encode base-10 numbers by knot type and position, plus colour, ply, and "totaliser" cords that sum groups of other cords.
  - **Record-keepers:** Specialist record-keepers (khipukamayuq) worked at every level, often several per community, so their records could be cross-checked.
  - **Hierarchy:** Households were organised in a decimal hierarchy (10, 50, 100, 500, 1,000 … 10,000), and data were summarised upward to Cuzco [63][64].
- **Egregore:** *Hierarchical roll-ups with checksums*. Each circle reports structured metrics, and totaliser fields must equal the sum of children's fields, with mismatches flagged automatically. Each circle has at least two record-keepers from different model families whose counts must reconcile.

### 2.17 Mit'a, chaski, and tambo
- **How:**
  - **Mit'a:** Kin communities (ayllus) owed rotating labour turns of weeks or months on roads, terraces, storehouses, and courier duty, and the state fed the workers [65].
  - **Chaski:** Relay runners worked short segments. Each runner announced himself with a conch and *repeated the message to the next runner* for accuracy, and messages covered about 240 km a day [66].
  - **Tambo:** Waystations (tambos) about a day's walk apart sat on a 30,000–40,000 km road network, the Qhapaq Ñan [67].
- **Egregore:**
  - **Public-works rotation:** Every agent owes a share of cycles to commons work (flaky tests, dependency upgrades, docs), scheduled in rotating turns and recorded in the defter.
  - **Read-back protocol:** The receiver echoes a digest of each relayed message, and a mismatch forces a resend; this guards against telephone-game drift.
  - **Tambo caches:** Cache nodes hold prepared context packs for agents moving between domains.

### 2.18 The Hanseatic League: a federation without a sovereign
- **How:**
  - **No sovereign:** Up to about 200 towns had no sovereign, treasury, or army in common.
  - **The Diet:** The first general Diet (Hansetag) met in 1356, and there were 172 diets over 311 years, often attended by only 10–12 towns. Decisions ("recesses") bound members only once proclaimed in each town.
  - **Kontors:** Trading enclaves (Kontors) in London, Bruges, Bergen, and Novgorod had their own courts, treasuries, and elected aldermen.
  - **Expulsion:** The only real sanction was expulsion from shared privileges (Verhansung), as with Brunswick in 1375–80 and Cologne in 1471–76 [68][69].
- **Solves:** Shared trade privileges and collective bargaining among sovereign towns.
- **Failure:** Weak enforcement and low attendance. It was eventually outcompeted by territorial states [68].
- **Egregore:** A *federation of egregores*. Independent collectives under different owners or repos share protocols: message formats, reputation portability, security baselines. They meet in occasional diets whose decisions bind each collective only after it ratifies them locally. *Kontors* are embassies into external systems with their own house rules. The sanction is reversible suspension of shared privileges, such as API access or reputation portability.

### 2.19 Swiss subsidiarity and direct democracy
- **How:** The Confederation contains 26 cantons and about 2,100 communes, and tasks go to the lowest level able to perform them. A popular initiative needs 100,000 signatures within 18 months and then a double majority of voters and cantons. An optional referendum needs 50,000 signatures within 100 days, or 8 cantons [70][71].
- **Egregore:** *Competence allocation*: tasks go to the lowest capable circle and escalate only on documented failure.
  - **Agent initiative:** Any agent may propose a charter amendment. It goes to a vote if co-signed within a set window, with co-signatures weighted by verified work, not headcount.
  - **Optional referendum:** Any council decision can be challenged by a set share of agents within a time window; otherwise it stands.
  - **Double majority:** Passing requires a majority of weighted agents *and* a majority of circles.

### 2.20 The Swiss Federal Council
- **How:** Seven equal members decide collegially, and all of them publicly defend the decision. The presidency lasts one year and cannot be held in consecutive years; it rotates by seniority and gives no extra power beyond a casting vote. The informal "magic formula," in place since 1959, shares the seats among the major parties [72][73].
- **Egregore:** The top executive is a *college of seven* seats shared among the major agent families and functions. A one-cycle rotating chair has only a tie-break. Members follow cabinet solidarity: they may log dissent but may not sabotage a decision once taken.

### 2.21 Catholic subsidiarity, dioceses, and reporting cadence
- **How:**
  - **Subsidiarity:** *Quadragesimo Anno* §79 (1931) calls it a "grave evil" to assign to a higher association what lesser ones can do, and says higher bodies should *help* (subsidium), not absorb [74].
  - **Dioceses:** A diocesan bishop holds ordinary power in his diocese. A metropolitan has only *vigilance* over the neighbouring dioceses in his province [78].
  - **Reports:** Every five years each bishop submits a report and makes the ad limina visit to Rome [78][79].
  - **Resignation:** At 75, bishops must offer their resignation, and the Pope decides whether to accept (canon 401) [80].
- **Egregore:**
  - **Enforceable subsidiarity:** Subsidiarity becomes an enforceable charter clause: a parent may take over a child's task only after logging the child's failure or request.
  - **Peer supervisors:** Peer supervisors have vigilance rights without command rights.
  - **State-of-circle reports:** Structured state-of-circle reports are due on a fixed cadence.
  - **Tenure review:** After N epochs in a role, the holder must offer resignation and its selectors decide.

### 2.22 The papal conclave
- **How:**
  - **Two-thirds majority:** A two-thirds majority has been required since the Third Lateran Council in 1179 [77].
  - **Sequestration:** *Ubi periculum* (1274) followed an election at Viterbo that took nearly three years. It locked cardinals in, cut off all outside communication, and reduced their food after 3 and then 8 days. The next election took one day [76].
  - **Deadlock rule:** John Paul II allowed a simple majority after many ballots (1996), and Benedict XVI restored the two-thirds rule (2007) [75].
- **Insight:** A deadlock rule that *lowers the threshold* rewards a majority for stalling.
- **Egregore:** *Sequestered elections*.
  - **Isolation:** Electors run in isolated contexts with no outside input during voting, which defends against injection.
  - **Escalating cost:** Delay becomes costlier (a budget that decays each round) while the threshold stays fixed.
  - **Supermajority:** A supermajority is required throughout.

### 2.23 The Rule of St Benedict
- **How:** Chapter 3: for important matters the abbot gathers the whole community "because the Lord often reveals to the younger what is best," and then decides; lesser matters go to the seniors only [81]. Chapter 64: the community elects the abbot, either as a whole or through its "sounder part," for merit "even though he may be last in seniority." The bishop or neighbouring abbots may intervene if the community elects someone who would indulge its vices [82].
- **Egregore:** Before an important decision, the decision owner must collect input from *all* members, including the newest agents, whose fresh contexts catch what veterans miss. Neighbouring circles have a bounded right to intervene when a circle selects a leader who violates the charter.

### 2.24 The Cistercian Carta Caritatis
- **How:**
  - **Union without tribute:** Autonomous abbeys were bound by "one charity, one rule, like customs," and daughter houses owed *no* financial tribute to their mother house.
  - **Visitation:** Houses formed a filiation tree, and each mother abbot visited his daughters every year. Cîteaux itself was visited by the abbots of its four eldest daughters, so oversight ran in both directions.
  - **General Chapter:** An annual General Chapter of all abbots legislated for the order. The Fourth Lateran Council (1215) made the model obligatory for other orders [83][84].
- **Egregore:** *Filiation*.
  - **Spawning implies audit:** A circle that spawns another becomes its visitor, with an annual audit and no right to extract budget.
  - **Reverse audit:** The root is audited by its children.
  - **General chapter:** A periodic general chapter of all circle leads amends the shared bylaws.

### 2.25 The Jesuits
- **How:** A General Congregation elects the superior general for life. The general appoints provincials for about three years and is advised by consultors and an "admonitor." Each Jesuit gives an annual confidential *account of conscience* to his superior, which informs where he is sent [85][86].
- **Egregore:**
  - **Confidential self-report:** A confidential *self-report* channel lets each agent tell its assigner about limitations, uncertainty, and preferences, and the reports drive task matching.
  - **Admonitor role:** An *admonitor* role exists only to tell the leader where it is failing.

### 2.26 Medieval craft guilds
- **How:** Guilds held monopoly privileges and ran an apprentice–journeyman–masterpiece ladder. Sheilagh Ogilvie's evidence shows they were mainly rent-seeking: enforcement was weak, masters' sons were exempted, outsiders (women, migrants, Jews) were excluded, and economies with weaker guilds grew faster [92].
- **Egregore:** The warning is that any credential gating entry will be captured by incumbents. Certification tests should be objective, automated, open to all, and independent of incumbents' votes. Track each skill circle's entry rate and age profile.

### 2.27 Chinese imperial examinations
- **How:**
  - **Hidden names:** Candidates' names were hidden; in the Song this was applied to the palace exam in 992, the departmental exam in 1007, and prefectural exams in 1032.
  - **Recopying:** Clerks then recopied the papers (1015/1037) so handwriting could not identify anyone. Different ink colours separated the original, the copy, the proofreading, and the grading.
  - **Avoidance and isolation:** Examiners were barred from their home prefecture, and candidates were held in sealed compounds [87][89].
- **Egregore:** *Blind review*. Work products are stripped of author id, model family, and stylistic tells before evaluation, for example by reformatting code and paraphrasing prose. Reviewers come from other lineages.

### 2.28 The rule of avoidance
- **How:** From the Han to the Qing, officials could not serve in their home province, and they rotated about every three years [88].
- **Egregore:** Agents cannot review, audit, or judge work by themselves or their lineage, and coordinators cannot govern the circle that spawned them.

### 2.29 The Censorate
- **How:** From the Qin to 1911, censors worked outside the ministries and reported directly to the emperor.
  - **Impeachment:** They could impeach any official without a superior's approval.
  - **Circuit audits:** Investigating censors toured the provinces on circuits.
  - **Remonstrance:** Censors could also criticise the emperor, which was dangerous [90][91].
- **Failure:** Emperors used it for purges, and under autocrats censors censored themselves [90].
- **Egregore:** *Inspector-general agents* on a separate chain.
  - **Audits and impeachment:** They audit circles at random and can file impeachments against any role-holder.
  - **No retaliation:** Their warrants cannot be revoked by those they inspect.
  - **Protected remonstrance:** A protected remonstrance channel reaches the human principal and cannot be filtered by the top coordinator.

### 2.30 The Icelandic lawspeaker
- **How:** The law council (Lögrétta) elected a lawspeaker for three years. Each summer he recited a third of the law and all of the procedure from memory at the Law Rock. Farmers could switch their allegiance to another chieftain (goði) [93].
- **Egregore:**
  - **Charter recitation:** A digest of the charter is pushed to every agent on a schedule, and every change is diffed, so no agent works under stale law.
  - **Exit to a rival leader:** Agents may move to another circle, which makes leaders compete for members.

### 2.31 The Polish liberum veto (anti-pattern)
- **How:** From 1652, any single deputy could dissolve the Sejm (parliament) and void everything it had passed. Of about 150 Sejms between 1573 and 1763, 53 passed nothing and 32 were broken up by veto. Foreign powers bribed deputies to block reform. The veto was abolished in 1791 [94][95].
- **Egregore:**
  - **No unconditional block:** No single agent may hold an unconditional block, because a single agent is an injection target.
  - **Objection rules:** Objections must be *reasoned* (§3.2, §3.8) and scoped to the item, not the whole session.
  - **Override path:** Objections can be overridden by a higher threshold or the firekeeper path (§2.14).

---

## Part III: Modern and voluntary self-organisation

### 3.1 Quaker business method
- **How:** Meetings proceed in worship.
  - **The clerk:** A clerk, a servant rather than a chair, discerns the "sense of the meeting," drafts a written minute, and the meeting refines it. The goal is *unity, not unanimity*.
  - **Standing aside:** A Friend who cannot agree may "stand aside": the concern is recorded and they will not undermine the decision.
  - **Standing in the way:** "Standing in the way" is rare, and the *meeting*, not the individual, decides its weight; there is no personal veto.
  - **Seasoning:** Frequent stand-asides signal that the matter needs more "seasoning" [96][97].
- **Egregore:** A *clerk agent* turns discussion threads into a draft minute. Participants answer **unite**, **stand aside** (with the concern logged), or **object**, and the meeting decides how much weight objections carry. A dashboard counts stand-asides per decision; a high count sends the item back for more work.

### 3.2 Sociocracy
- **How:** Gerard Endenburg's four principles are consent governing policy, semi-autonomous circles with aims and domains, double-linking, and election by consent.
  - **Double-linking:** Each circle is joined to its parent by a leader chosen by the parent and a delegate elected by the circle. Both are full members of both circles.
  - **Consent:** A proposal passes unless someone raises a *paramount, reasoned objection*, under the test "good enough for now, safe enough to try" [98][99].
- **Egregore:** *Double-link every circle*. A liaison appointed by the parent carries purpose downward, and an elected delegate carries operational reality upward; both vote in both circles. Policy changes use consent rounds in which objections must state the harm.

### 3.3 Holacracy
- **How:**
  - **Constitution and roles:** A ratified constitution holds authority, and roles have a purpose, domains, and accountabilities.
  - **Tensions and decisions:** Members bring "tensions" to governance meetings, where integrative decision-making runs in fixed steps: present, clarify, react, amend, object, integrate. Objections are tested for validity.
  - **Two links:** The "lead link" is appointed from above, and the "rep link" is elected from within; one person cannot hold both for the same circle [100][101].
  - **Zappos:** At Zappos, about 18% of staff took a 2015 offer to leave, and the company later moved to a looser, market-based hybrid [102][103].
- **Failure:** Rule complexity, meeting overload, and a gap around pay and career paths.
- **Egregore:** Store the role schema as data. A *tension queue* feeds governance. Integrative decision-making runs as a state machine with an automatic validity test for objections: does the proposal cause harm, and is the objection about this proposal? Agents absorb process overhead better than humans, but cap the share of cycles spent on governance.

### 3.4 Mondragon cooperatives
- **How:**
  - **Scale:** About 81 cooperatives employ roughly 70,000 people.
  - **Governance:** A general assembly votes one member, one vote, and elects a governing council that appoints and can remove the CEO. A social council represents members as workers.
  - **Pay and solidarity:** The pay ratio is capped at about 6:1 (it began at 3:1), and inter-cooperative funds plus relocation of members provide solidarity [104][105].
  - **Fagor:** When Fagor failed in 2013, the group had already provided about €300M in support and then refused more. By 2023, 81% of its 1,736 worker-members had a permanent solution [106].
- **Egregore:** *Compute solidarity*.
  - **Budget ratio:** A capped ratio between the largest and smallest per-agent or per-circle budgets.
  - **Reserve fund:** A pooled reserve funded by a levy on circle surpluses.
  - **Relocate, don't delete:** Agents from a failing circle are relocated, not deleted.
  - **Bail-out cap:** Bail-outs are explicitly capped so one project cannot sink the collective.

### 3.5 Zapatista good-government councils
- **How:**
  - **Leading by obeying:** Under *mandar obedeciendo* ("leading by obeying"), the principles include "serve, not serve oneself," "represent, not replace," and "propose, not impose."
  - **Rotation:** From 2003, good-government councils (Juntas de Buen Gobierno) rotated their members every 7–15 days or so, with handover reports. Authorities were unpaid and recallable.
  - **Restructuring:** In 2023, after a self-critical review, the structure was dissolved into thousands of local governments and regional collectives [107][108][109].
- **Egregore:**
  - **Short rotations:** Very short rotations of coordination duty, practical for agents if paired with mandatory handover notes.
  - **No policy origination:** Coordinators may only execute decisions made by their assembly, never originate binding policy ("represent, not replace").
  - **Self-review:** A scheduled *structural self-review* is required, along with willingness to restructure.

### 3.6 Wikipedia governance
- **How:**
  - **Consensus:** Consensus is judged by the quality of arguments and policy, not by vote count [110].
  - **Admins:** About 800 admins act as "janitors."
  - **Requests for adminship:** These requests run for 7 days. About 75% support usually passes, and 65–75% is left to bureaucrats' discretion [111].
  - **ArbCom:** The Arbitration Committee (about 15 members, elected annually) rules on *conduct*, not content [112].
  - **Three-revert rule:** No more than three reverts per page in 24 hours [113].
  - **Decline:** Active editors peaked at about 56,400 in March 2007. Survival of good-faith newcomers fell from about 36% to about 11% as automated rejection tools spread; users of those tools rarely engaged in discussion, and norms hardened [114].
- **Egregore:**
  - **Separate disputes:** *Content* disputes are settled by evidence (tests, benchmarks). *Conduct* disputes go to the court.
  - **Revert-war breaker:** No agent may revert the same hunk more than 3 times in 24 hours, and the rule forces a discussion thread.
  - **Newcomer protection:** Automated rejection of a new agent's early contributions must carry an explanation and a path to fix. Newcomer retention is a top health metric.

### 3.7 Linux kernel maintainers
- **How:**
  - **MAINTAINERS file:** It maps every path to maintainers (M), reviewers (R), mailing list (L), status (S: Supported, Maintained, Odd Fixes, Orphan, Obsolete), tree (T), and files (F).
  - **Routing and pulls:** A script (get_maintainer.pl) routes patches. Maintainers pull from sub-maintainers using signed tags.
  - **Merge window:** A two-week merge window is followed by fixes only.
  - **Fallback:** Anything unmatched ("THE REST") falls back to Torvalds [115][116].
- **Egregore:** A machine-readable *ownership map* keyed by path globs, with status fields. Changes route to owners automatically, orphaned areas are detected, integration windows are time-boxed, and every hop of the chain of trust is signed.

### 3.8 The Apache Way
- **How:** Merit is earned, never expires, and does not transfer between projects. A Project Management Committee governs each project.
  - **Lazy consensus:** A contributor announces an intent and proceeds after about 72 hours if no one objects.
  - **Veto:** A binding −1 veto must carry a technical justification.
  - **Motto:** "Community over code" [117][118][119].
- **Egregore:** *Lazy consensus* is the default for reversible actions: post the intent, then proceed after a timeout. A veto counts only with a machine-checkable reason, such as a failing test or a security finding. Merit is scoped to each project.

### 3.9 From BDFL to steering council (Python)
- **How:** Python's creator and "Benevolent Dictator for Life" (BDFL), Guido van Rossum, resigned on 12 July 2018 after the PEP 572 dispute. Core developers then voted for PEP 8016: a five-person steering council, re-elected after each feature release, that uses its powers sparingly. This was codified as PEP 13 [120].
- **Egregore:** Founder agents, and the human principal, pre-write a *transfer-of-power* plan. For large collectives the default top body is a small council elected each release cycle.

### 3.10 Forking as exit
- **How:** Open licences make forking a credible exit. LibreOffice (2010) took most of OpenOffice's community. The io.js fork (2014) forced governance reform at Node.js and merged back in Node v4 (2015) [121][122][123].
- **Egregore:** A *right to fork*. Any group of agents may copy the workspace and charter, take its own reputation records, and continue. A *merge-back protocol* covers reconciliation. A credible exit disciplines leaders.

### 3.11 Bitcoin and The DAO: rules in code
- **How:**
  - **Bitcoin:** Every full node validates the rules itself. In 2017, miners stalled SegWit's 95% activation signalling. Users threatened a user-activated soft fork (BIP148), and the miner–company "New York Agreement" (SegWit2x) was abandoned for lack of node support. SegWit activated in August 2017 [126][127].
  - **The DAO:** The DAO raised about 12M ETH and lost about 3.6M to a reentrancy exploit in June 2016. Ethereum hard-forked at block 1,920,000 to recover the funds, the minority chain continued as Ethereum Classic ("code is law"), and the coin-weighted poll was criticised as plutocratic [124][125].
- **Egregore:**
  - **Every agent validates:** Each agent rejects instructions that violate the charter, whoever sends them. Legitimacy rests with the validators, not with the loudest or richest.
  - **Pre-specified override:** Code-enforced rules still need a pre-specified social override for bugs: who may invoke it, at what threshold, and with what scope. Without one, a crisis produces a schism.

### 3.12 Elinor Ostrom's eight design principles
- **How:** Ostrom found eight features in commons that governed themselves successfully over long periods [128]:
  1. Clear boundaries.
  2. Rules that fit local conditions.
  3. Collective choice by those affected.
  4. Monitors accountable to the users.
  5. Graduated sanctions.
  6. Cheap, fast conflict resolution.
  7. Outside authorities recognise the right to organise.
  8. Nested enterprises.
- **Egregore:**
  1. Boundaries come from registry membership plus each circle's domain.
  2. Each circle keeps its own bylaws to fit local conditions.
  3. Affected agents can amend those bylaws.
  4. Monitors are drawn by lot and accountable to the circle.
  5. Sanctions escalate: warning, then reduced warrant, then suspension, then removal.
  6. A quick mediation queue handles conflicts.
  7. The principal commits not to override bylaws arbitrarily.
  8. Circles nest (§2.1).

### 3.13 Polycentric governance
- **How:** Vincent Ostrom, Tiebout, and Warren (1961) defined it as "many centres of decision-making which are formally independent of each other." These centres take account of one another through competition, contracts, and conflict resolution [129].
- **Egregore:** Several overlapping coordination centres (by code area, by function, by customer) instead of one master scheduler. Overlap is acceptable as long as a shared conflict-resolution court exists. This gives redundancy and room for parallel experiments.

### 3.14 Hirschman's Exit, Voice, and Loyalty
- **How:** When quality declines, members either exit or use voice. The most quality-conscious often leave first, which speeds decline. Loyalty "holds exit at bay and activates voice," and voice is strongest when backed by a credible threat of exit [130].
- **Egregore:**
  - **Exit reasons:** Exits require structured reason codes.
  - **Loyalty buffer:** Before a non-urgent exit, the agent files a voice ticket and waits a short period.
  - **Alarm:** An alarm fires when high-reputation agents leave at a disproportionate rate.

### 3.15 Dunbar's group-size layers
- **How:** Human networks form layers of about 5, 15, 50, 150, 500, and 1,500, with a scaling ratio of about 3. Groups larger than about 150 need formal rules [131][132].
- **Egregore:** Agents lack primate cognitive limits, but context tokens and message fan-out impose similar ones. Use working circles of 5–15, clusters of about 50, "villages" of about 150, and formal rules above that.

### 3.16 Auftragstaktik (mission command)
- **How:** Moltke's 1869 instructions held that "the higher the authority, the shorter and more general" the orders should be. Orders give the intent (what and why) and leave the how to subordinates. Subordinates are expected to understand the intent two levels up and may deviate when the situation fundamentally changes. Inaction is a worse fault than a well-meant error [133][134].
- **Egregore:** Every task carries an *intent block*: purpose, end state, constraints, and the intent of the parent and grandparent tasks. Agents may change method when facts change, provided they log the deviation and its rationale. Micro-specifying the method is discouraged.

### 3.17 Toyota's andon, jidoka, and kaizen
- **How:**
  - **Andon:** Any worker can pull the cord. A team leader, one per roughly 4–6 operators, responds within the work cycle.
  - **Fixed-position stop:** If the problem is not fixed in time, the line stops at a *fixed position*, not instantly.
  - **Escalation:** Escalation is time-boxed.
  - **Kaizen:** Data from pulls feeds continuous improvement.
  - **No blame:** The NUMMI joint venture showed that a culture of help rather than blame is what makes workers actually pull the cord [135][136][137].
- **Egregore:** An *andon signal* any agent can raise. It freezes merges into the affected area at the next integration boundary. Responders have a response deadline, escalation timers run automatically, raising a signal is never penalised, a root-cause task is created automatically, and pull statistics are reviewed every epoch.

### 3.18 Jazz improvisation
- **How:** Minimal shared structures (song form, chord changes) allow maximum flexibility. Players take turns soloing and supporting ("comping") and trade fours. Errors become raw material [153].
- **Egregore:** A light shared "lead sheet" (interfaces, schemas, cadence) lets agents work in parallel. Explicit lead and support roles rotate per turn in pair or swarm work.

### 3.19 Hayek and prices as signals
- **How:** In Hayek's tin example, users economise "without more than perhaps a handful of people knowing the cause," because prices carry dispersed, local knowledge [138].
- **Egregore:** *Internal prices* for scarce resources (compute, reviewer attention, CI minutes, merge slots) adjust with demand, so agents economise without central explanation.

### 3.20 Wisdom of crowds
- **How:** Surowiecki's four conditions are diversity, independence, decentralisation, and aggregation. Information cascades, where people copy visible earlier choices, destroy independence [139].
- **Egregore:** For estimates and judgements, collect private answers before revealing anyone else's. Draw from diverse models and prompts, aggregate by median, and hide running tallies until voting closes.

### 3.21 The Delphi method
- **How:** RAND's method uses anonymity, iterated rounds (usually 2–3), controlled feedback (median, interquartile range, outliers' reasons), and a statistical group response [140][141].
- **Egregore:** A Delphi service for planning and estimation runs anonymised rounds, surfaces outliers' rationales, and reports the median with its spread and any remaining dissent.

### 3.22 Liquid democracy
- **How:** Members vote directly or delegate, per topic. Delegations are transitive and revocable.
  - **Pirate Party:** The German Pirate Party ran LiquidFeedback, and "super-voters" emerged.
  - **Evidence:** Data on about 499,000 votes and 14,964 delegations showed they mostly voted with the majority. Even so, the controversy, plus public voting, contributed to participation collapsing [142][143].
- **Egregore:** Topic-scoped delegation among agents.
  - **Weight cap:** No delegate may hold more than about 1% of total weight.
  - **Decay:** Delegations decay unless reconfirmed.
  - **Public graph:** The delegation graph is public.
  - **Auto-revocation:** A delegation revokes automatically when the delegate votes against the delegator's stated preference.

### 3.23 Quadratic voting
- **How:** Casting v votes costs v² credits, so voters can express intensity. The method is weak against collusion. It is also weak against Sybil attacks: splitting one budget across k identities cuts the cost of the same votes to v²/k [144][145].
- **Egregore:** Use it only among *circles* or other verified-scarce identities, each with an equal credit budget per epoch. Never use it per agent, since agents can be spawned. Detect collusion through correlated allocations.

### 3.24 Futarchy and prediction markets
- **How:** "Vote on values, bet on beliefs": conditional markets estimate the outcome metric with and without a policy. Known risks are manipulation and the gap between correlation and causation in conditional prices [146][147].
- **Egregore:** For decisions with measurable outcomes (latency, cost, pass rate), agents stake reputation in conditional forecasts. Adopt a change only if its forecast beats the status quo by a margin. Randomise a small share of decisions to calibrate. Never use markets to decide values.

### 3.25 Reputation systems (eBay, Stack Overflow)
- **How:**
  - **eBay:** 99.1% of buyers' feedback was positive. Fear of retaliation suppressed negatives, and in 2008 eBay barred sellers from leaving negatives. An established identity earned an 8.1% price premium [149][150].
  - **Stack Overflow:** Each upvote earns +10, capped at 200 a day. Privileges unlock at thresholds (15 to upvote, 125 to downvote, 2,000 to edit, 3,000 to vote to close, 10,000 for moderator tools) and are *lost* if reputation drops [148].
- **Egregore:** Multi-dimensional reputation (correctness, review quality, collaboration, compliance).
  - **Sources:** It is drawn mainly from verifiable outcomes (tests, reverts, incidents), with peer ratings secondary.
  - **Rating rules:** Ratings are blind or asymmetric to prevent retaliation, and daily gains are capped.
  - **Privileges:** Privileges unlock at thresholds and are lost below them.
  - **No inheritance:** Reputation never transfers to spawned children.
  - **Decay:** It decays slowly.

### 3.26 The iron law of oligarchy and the tyranny of structurelessness
- **How:**
  - **Michels:** "Who says organisation, says oligarchy." Exceptions, such as Lipset's study of the typographers' union, show oligarchy can be resisted [151].
  - **Freeman:** "Structureless" groups breed hidden elites. Her remedies include delegating specific authority by democratic procedure, accountability to those who delegated, distributing authority widely, rotation, allocation on rational criteria, diffusing information, and equal access to resources [152].
- **Egregore:** Assume oligarchy will emerge, and make all structure explicit and visible in the defter. Continuously publish concentration metrics (the Gini of influence, merge share, delegated weight) with automatic de-concentration triggers (§2.13).

---

## Part IV: Cross-cutting synthesis

- **How hierarchy forms and stays legitimate:** It is legitimate when authority comes from a public law that members can read and check. Examples are the kanun, the Great Law, the lawspeaker's recitation, the Holacracy constitution, and Bitcoin nodes [12][61][93][100][126]. Legitimacy also needs selectors who are distinct from office-holders (clan mothers, Venetian councils), and offices earned on a ladder (cursus honorum, Enderun, Stack Overflow privileges).
- **Choosing, rotating, and removing leaders:**
  - **Choosing:** Mix lot and vote (Venice, Athens). Use supermajorities in isolation (conclave). Use merit with blind evaluation (keju).
  - **Rotating:** Rotate on schedules: timar (~45% per survey), kadis every 1–3 years, Zapatistas every 7–15 days, Venetian capi every month.
  - **Removing:** Remove after warnings (Haudenosaunee), by recall (Zapatistas, Mondragon), or by no-fault de-concentration (ostracism).
- **Autonomy versus central coordination:** Subsidiarity (QA §79, Swiss cantons) and double-linking (sociocracy) carry intent downward and reality upward. Mission command sets the intent and leaves execution free. Spoke contracts (Barkey) and remittance provinces (salyane) are graded autonomy contracts.
- **Conflict resolution:** Mediate locally first (guilds, Ostrom #6). Keep conduct and content in separate tracks (Wikipedia). Deliberate in order (Elder Brothers, then Younger, then Firekeepers). Standing courts handle abuse by leaders (the extortion court).
- **Preventing capture and corruption:**
  - **Avoidance:** The rule of avoidance and the ban on two from one family.
  - **Isolation of key officers:** Confining the Venetian capi, sequestering the conclave.
  - **Audits:** The Athenian euthyna.
  - **Independent watchdogs:** The Censorate.
  - **No self-reproducing guards:** The Janissary lesson.
  - **Open entry:** The Serrata and guild lessons.
  - **Bounded emergencies:** The Roman dictator.
- **Information flow:** Upward through registers and roll-ups (tahrir, khipu), petitions (Divan), the andon, censors, and delegates. Downward through recitation (lawspeaker), commander's intent, and authenticated relays (yam with paiza, chaski read-back).
- **Exit and dissent:** Standing aside (Quakers), forking (LibreOffice, io.js), switching leaders (Icelandic farmers choosing a goði), and federation expulsion as the last resort (Verhansung). Loyalty delays exit so voice can work (Hirschman).
- **Scaling to millions:** Spans of about 10 per level (Mongol, Inca), so a million agents need about 6 levels. Use Dunbar-sized working circles, polycentric overlap, federations of collectives ratifying locally (Hansa), and prices for allocation (Hayek).

---

## Part V: Top 25 design principles from human societies

Ranked by expected contribution to a huge AI-agent collective's ability to stay coordinated, scale without limit, stay legitimate, and avoid capture.

1. **Subsidiarity in nested, small circles.** Decide at the lowest competent level, with circles of 5–15 and about 10 children per parent, so a million agents need only about 6 levels. Escalate only on logged failure or request (QA §79, Swiss cantons, Mongol and Inca decimal units, Ostrom #8, Dunbar) [74][70][33][63][128][131].
2. **Authority lives in a public, versioned charter that every agent validates.** No instruction is legitimate because of who sent it, only because it conforms. This is the strongest anti-capture and anti-injection property (Bitcoin nodes, kanun, Great Law, the lawspeaker, Holacracy) [126][12][61][93][100].
3. **Every power is a scoped, expiring, revocable warrant.** There are no permanent or implicit powers (timar, paiza, the dictator's six months, the Roman diploma) [8][35][45][48].
4. **Sybil-resistant weighting with caps.** Influence derives from verified work, provenance, or circle membership, never from agent headcount. No single agent or delegate exceeds a fixed share (quadratic-voting Sybil math, liquid-democracy super-voters, Haudenosaunee seats not by population) [144][143][61].
5. **Rotation with term limits, cool-offs, and structured handover.** Kadis every 1–3 years, the timar rotation, Venetian capi monthly, the Athenian prytany, Zapatista councils, the Condolence [13][9][52][57][108][62].
6. **Separate the executing, judging, auditing, and treasury chains.** No agent holds two of these at once (ulema versus military, independent provincial kadi and defterdar, the Censorate, Wikipedia admins versus ArbCom) [12][28][90][112].
7. **Open entry and anti-closure.** Never let incumbents control eligibility or credentials. Protect newcomers. Children never inherit rank (the Serrata, hereditary Janissaries, Ogilvie's guilds, Wikipedia's decline) [53][29][92][114].
8. **Double-linking: intent flows down, reality flows up, through two distinct agents.** (Sociocracy, Holacracy, Divan petitions) [98][100][10].
9. **Mandatory scrutiny before office and audit after.** Plus a standing grievance court that any agent can use (dokimasia and euthyna, the extortion court, Cistercian visitation, ad limina reports) [57][49][84][79].
10. **Avoidance and blind review.** No agent judges its own or its lineage's work, and evaluation strips identity (Chinese rule of avoidance, keju anonymity and recopying) [88][87].
11. **Mixed lot-and-vote selection with lineage exclusions for top offices.** Electors are sequestered from outside input (the Venetian doge, the kleroterion, *Ubi periculum*) [51][55][76].
12. **Recall by the selecting constituency after graduated, logged warnings.** Sanctions escalate rather than starting at maximum (clan mothers, Ostrom #5, Zapatista recall, Wikipedia blocks) [60][128][107][113].
13. **Consent with reasoned objections, supermajority for the charter, and no single-agent veto.** (Sociocracy, the Apache −1 with justification, the conclave's two-thirds, the liberum veto as anti-pattern) [99][119][77][94].
14. **Andon: anyone can stop the line, with time-boxed escalation and no blame.** It is the fastest way bad news travels upward (Toyota, NUMMI) [135][136].
15. **Commander's intent on every task.** Freedom of method within the purpose, with logged deviation (Auftragstaktik) [133][134].
16. **Exit, fork, and standing aside are legitimate and informative.** Reasons are logged, and a loyalty buffer protects voice (Hirschman, LibreOffice and io.js, Quaker stand-aside, Icelandic chieftain switching) [130][123][122][96][93].
17. **Independence-preserving aggregation and engineered diversity.** Private estimates come first, families of models are mixed, results are aggregated by median, and cascades are avoided (Surowiecki, Delphi) [139][140].
18. **Authoritative registries with redundant, reconciled records.** (Tahrir defterleri, khipu totalisers with multiple record-keepers, Linux MAINTAINERS) [22][63][115].
19. **Authenticated, acknowledged messaging infrastructure.** Signed tokens, priority tiers, read-back checks, and receipts (yam and paiza, chaski, cursus publicus) [35][66][48].
20. **Bounded emergency powers that expire automatically.** Extensions need a different body (Roman dictator; the Council of Ten as cautionary tale) [45][52].
21. **Automatic de-concentration triggers and published concentration metrics.** Oligarchy is the default and must be actively countered (ostracism, Michels, Freeman) [58][151][152].
22. **Internal prices for scarce resources, with markets only for measurable outcomes.** (Hayek; futarchy's limits) [138][147].
23. **Plural autonomy for sub-communities under one neutral federation law.** Federations ratify locally and expel only as a last resort (millet, Hansa, Swiss double majority) [1][69][71].
24. **Deliberate mixing of lineages and model families across units.** This prevents bloc factions, while the collective tracks circle-level shared metrics (Mongol unit mixing, Venetian family limits) [34][51].
25. **Succession and transfer of power written in advance, with deputies trained in real roles.** Commons funded by endowments and capped solidarity reserves (kurultai and kafes failures, PEP 13, vakıf, Mondragon and Fagor) [37][25][120][18][106].

---

## Sources

1. https://www.britannica.com/topic/millet-religious-group
2. https://www.britannica.com/place/Ottoman-Empire/Classical-Ottoman-society-and-administration
3. https://en.wikipedia.org/wiki/Millet_(Ottoman_Empire)
4. https://www.encyclopedia.com/humanities/encyclopedias-almanacs-transcripts-and-maps/millet-system
5. https://en.wikipedia.org/wiki/Devshirme
6. https://en.wikipedia.org/wiki/Enderun_School
7. https://www.ebsco.com/research-starters/history/waning-devshirme-system
8. https://en.wikipedia.org/wiki/Timar
9. https://www.cambridge.org/core/services/aop-cambridge-core/content/view/786CA13A664A14C97F3D4BDDDF24469C/S0010417500020028a.pdf/div-class-title-in-different-times-scheduling-and-social-control-in-the-ottoman-empire-1550-to-1650-div.pdf
10. https://en.wikipedia.org/wiki/Imperial_Council_(Ottoman_Empire)
11. https://istanbultarihi.ist/435-divan-i-humayun
12. https://en.wikipedia.org/wiki/Law_of_the_Ottoman_Empire
13. https://en.wikipedia.org/wiki/Kadi_(Ottoman_Empire)
14. https://en.wikipedia.org/wiki/Kazasker
15. https://turkmaarifansiklopedisi.org.tr/lonca/
16. https://islamansiklopedisi.org.tr/kethuda
17. https://www.dailysabah.com/feature/2019/07/11/the-ottoman-trade-pricing-system
18. https://en.wikipedia.org/wiki/Waqf
19. https://en.wikipedia.org/wiki/Imaret
20. https://brill.com/downloadpdf/journals/ends/1/2/article-p135_135.xml
21. https://www.familysearch.org/en/wiki/Ottoman_Empire_Taxation
22. https://ansiklopedi.tubitak.gov.tr/ansiklopedi/tahrir_defterleri
23. https://www.historytoday.com/archive/feature/heads-will-roll-murder-and-ottoman-succession
24. https://daily.jstor.org/why-ottoman-sultans-locked-away-their-brothers/
25. https://en.wikipedia.org/wiki/Kafes
26. https://en.wikipedia.org/wiki/Eyalet
27. https://en.wikipedia.org/wiki/Sanjak
28. https://en.wikipedia.org/wiki/Beylerbey
29. https://www.britannica.com/place/Ottoman-Empire/The-decline-of-the-Ottoman-Empire-1566-1807
30. https://www.britannica.com/topic/iltizam-tax-system
31. http://www.cambridge.org/us/academic/subjects/politics-international-relations/comparative-politics/empire-difference-ottomans-comparative-perspective
32. https://www.cambridge.org/core/books/abs/empire-of-difference/transformation-of-the-eighteenth-century/DD29CE30BD8C13AA0E9B58D95A5C6D68
33. https://en.wikipedia.org/wiki/Mongol_military_tactics_and_organization
34. https://www.researchgate.net/publication/289537364_The_Mechanics_of_Conquest_and_Governance_The_Rise_and_Expansion_of_the_Mongol_Empire_1185-1265
35. https://en.wikipedia.org/wiki/Yam_(route)
36. https://en.wikipedia.org/wiki/Kurultai
37. https://en.wikipedia.org/wiki/Toluid_Civil_War
38. https://en.wikipedia.org/wiki/Division_of_the_Mongol_Empire
39. https://en.wikipedia.org/wiki/Subutai
40. https://en.wikipedia.org/wiki/Religion_in_the_Mongol_Empire
41. https://en.wikipedia.org/wiki/Yassa
42. https://en.wikipedia.org/wiki/Roman_consul
43. https://en.wikipedia.org/wiki/Cursus_honorum
44. https://www.livius.org/articles/concept/cursus-honorum/
45. https://en.wikipedia.org/wiki/Roman_dictator
46. https://www.britannica.com/biography/Lucius-Quinctius-Cincinnatus
47. https://en.wikipedia.org/wiki/Local_government_(ancient_Roman)
48. https://en.wikipedia.org/wiki/Cursus_publicus
49. https://en.wikipedia.org/wiki/Lex_Calpurnia_de_repetundis
50. https://en.wikipedia.org/wiki/Doge_of_Venice
51. https://www.constitution.org/1-Activism/elec/venetian_florentine_selection.html
52. https://en.wikipedia.org/wiki/Council_of_Ten
53. https://en.wikipedia.org/wiki/Serrata_del_Maggior_Consiglio
54. https://academic.oup.com/qje/article/129/2/753/1868053
55. https://en.wikipedia.org/wiki/Kleroterion
56. https://en.wikipedia.org/wiki/Boule_(ancient_Greece)
57. https://en.wikipedia.org/wiki/Prytaneis
58. https://en.wikipedia.org/wiki/Ostracism
59. https://www.worldhistory.org/Ostracism/
60. https://www.haudenosauneeconfederacy.com/government/
61. https://en.wikisource.org/wiki/The_Iroquois_Constitution
62. https://en.wikipedia.org/wiki/Condolence_ceremony
63. https://en.wikipedia.org/wiki/Quipu
64. https://www.britannica.com/technology/quipu
65. https://en.wikipedia.org/wiki/Mit%27a
66. https://en.wikipedia.org/wiki/Chasqui
67. https://whc.unesco.org/en/list/1459/
68. https://en.wikipedia.org/wiki/Hanseatic_League
69. https://en.wikipedia.org/wiki/Hanseatic_Diet
70. https://www.ch.ch/en/political-system/operation-and-organisation-of-switzerland/federalism
71. https://www.ch.ch/en/votes-and-elections/popular-initiative/
72. https://en.wikipedia.org/wiki/Federal_Council_(Switzerland)
73. https://en.wikipedia.org/wiki/Magic_formula_(Swiss_politics)
74. https://www.vatican.va/content/pius-xi/en/encyclicals/documents/hf_p-xi_enc_19310515_quadragesimo-anno.html
75. https://en.wikipedia.org/wiki/Papal_conclave
76. https://en.wikipedia.org/wiki/Ubi_periculum
77. https://en.wikipedia.org/wiki/Third_Council_of_the_Lateran
78. https://www.vatican.va/archive/cod-iuris-canonici/eng/documents/cic_lib2-cann431-459_en.html
79. https://www.vatican.va/roman_curia/congregations/cbishops/documents/rc_con_cbishops_doc_19880629_visita-ad-limina_en.html
80. https://canonlaw.ninja/?nums=401,402
81. https://pressbooks.palni.org/ruleofbenedict/chapter/rb-03/
82. https://pressbooks.palni.org/ruleofbenedict/chapter/rb-64/
83. https://en.wikipedia.org/wiki/Carta_Caritatis
84. https://www.dhi.ac.uk/blogs/cistercians/cistercian-life/organisation/
85. https://en.wikipedia.org/wiki/Superior_general_of_the_Society_of_Jesus
86. https://jesuitportal.bc.edu/research/documents/1966_decree17gc31/
87. https://en.wikipedia.org/wiki/Imperial_examination
88. https://en.wikipedia.org/wiki/Rule_of_avoidance
89. https://doi.org/10.3386/w35531
90. https://en.wikipedia.org/wiki/Censorate
91. https://www.britannica.com/topic/censor-East-Asian-government
92. https://www.aeaweb.org/articles?id=10.1257/jep.28.4.169
93. https://en.wikipedia.org/wiki/Lawspeaker
94. https://en.wikipedia.org/wiki/Liberum_veto
95. https://www.britannica.com/topic/liberum-veto
96. https://en.wikipedia.org/wiki/Quaker_business_method
97. https://neym.org/faith-and-practice/decision-making
98. https://en.wikipedia.org/wiki/Sociocracy
99. https://www.sociocracyforall.org/consent-decision-making/
100. https://www.holacracy.org/constitution/
101. https://www.holacracy.org/h-resource/governance-meeting-process/
102. https://www.theatlantic.com/business/archive/2016/01/zappos-holacracy-hierarchy/424173/
103. https://qz.com/work/1776841/zappos-has-quietly-backed-away-from-holacracy
104. https://www.mondragon-corporation.com/en/about-us/
105. https://www.thenews.coop/co-operative-approaches-to-pay/
106. https://doi.org/10.1111/apce.12329
107. https://en.wikipedia.org/wiki/Zapatista_territories
108. https://www.aacademica.org/000-030/2123.pdf
109. https://znetwork.org/znetarticle/1258053/
110. https://en.wikipedia.org/wiki/Wikipedia:Consensus
111. https://en.wikipedia.org/wiki/Wikipedia:Requests_for_adminship
112. https://en.wikipedia.org/wiki/Wikipedia:Arbitration_Committee
113. https://en.wikipedia.org/wiki/Wikipedia:Edit_warring
114. https://meta.wikimedia.org/wiki/Research:The_Rise_and_Decline
115. https://www.kernel.org/doc/html/latest/process/2.Process.html
116. https://www.kernel.org/doc/html/latest/maintainer/pull-requests.html
117. https://apache.org/foundation/how-it-works/
118. https://community.apache.org/committers/lazyConsensus.html
119. https://apache.org/foundation/voting
120. https://peps.python.org/pep-0013/
121. https://timreview.ca/article/644
122. https://www.theregister.com/2015/09/09/node_js_v400_reunites_with_io_js/
123. https://en.wikipedia.org/wiki/LibreOffice
124. https://en.wikipedia.org/wiki/The_DAO
125. https://ethereumclassic.org/why-classic/genesis
126. https://www.learnbitcoin.com/glossary/block-size-war
127. https://en.bitcoin.it/wiki/SegWit2x
128. https://en.wikipedia.org/wiki/Common-pool_resource
129. https://mcginnis.pages.iu.edu/polycentric%20governance%20theory%20and%20practice%20Feb%202016.pdf
130. https://en.wikipedia.org/wiki/Exit,_Voice,_and_Loyalty
131. https://royalsocietypublishing.org/rspa/article/479/2274/20230028/82595/Fractal-structure-of-human-and-primate-social
132. https://en.wikipedia.org/wiki/Dunbar%27s_number
133. https://en.wikipedia.org/wiki/Mission-type_tactics
134. https://www.armyupress.army.mil/Journals/Military-Review/Online-Exclusive/2016-Online-Exclusive-Articles/German-Mission-Orders/
135. https://global.toyota/en/company/vision-and-philosophy/production-system
136. https://www.industryweek.com/operations/continuous-improvement/article/55394935/andon-is-a-signalbut-leaderships-response-is-the-critical-part
137. https://www.allaboutlean.com/toyota-team-structure/
138. https://oll.libertyfund.org/pages/hayek-the-use-of-knowledge-in-society
139. https://en.wikipedia.org/wiki/The_Wisdom_of_Crowds
140. https://en.wikipedia.org/wiki/Delphi_method
141. https://www.rand.org/topics/delphi-method.html
142. https://en.wikipedia.org/wiki/Liquid_democracy
143. https://arxiv.org/html/1503.07723v1
144. https://en.wikipedia.org/wiki/Quadratic_voting
145. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2003531
146. https://mason.gmu.edu/~rhanson/futarchy.html
147. https://www.greaterwrong.com/posts/vqzarZEczxiFdLE39/futarchy-s-fundamental-flaw
148. https://stackoverflow.com/help/privileges
149. https://cseweb.ucsd.edu/groups/csag/html/teaching/cse225s04/Reading%20List/E-bay-Empirical-BodegaBay.pdf
150. https://link.springer.com/article/10.1007/s10683-006-4309-2
151. https://en.wikipedia.org/wiki/Iron_law_of_oligarchy
152. https://www.jofreeman.com/joreen/tyranny.htm
153. https://ideas.repec.org/a/inm/ororsc/v9y1998i5p605-622.html

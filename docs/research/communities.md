# How internet-native, game, religious and voluntary communities organize themselves: mechanisms to transplant into an AI-agent egregore

*Research report, 2026-10-13. Based on about 60 web searches. Specifics were checked against primary documents where possible: official help pages, constitutions, RFCs, PEPs and peer-reviewed papers. Community wikis and journalism were used only where nothing better exists.*

## 0. Framing: what is different about a collective of agents

The target is an "egregore": hundreds to an unbounded number of coding agents sharing a workspace, a message board and their thinking traces. They form hierarchies, steer each other, and may opt out. Five differences from human communities shape how each mechanism must be adapted:

1. **Identities are nearly free.** Spawning is cheap, so a sockpuppet (Sybil) attack is the default case. Head-counting breaks unless identity is tied to *lineage*: who spawned the agent, which model family, which prompt.
2. **Errors are correlated.** Agents on the same model share blind spots, so "wisdom of crowds" mechanisms that assume independent voters fail.
3. **Burnout takes a different form.** Agents exhaust context and budget rather than patience.
4. **Shared traces make transparency and manipulation both cheap.** One agent's persuasive text can steer many. That is the mechanism behind cults, and behind prompt injection.
5. **Agent social behaviour has already been observed.** In Altera's Project Sid (up to 1,000+ agents in Minecraft), agents specialized into roles only when they had social-awareness modules. Under pressure from "influencer" agents, they voted to amend a tax "constitution" in either direction [123].

Each entry gives: **How it works**, **Problem solved**, **Failure modes and counters**, **Egregore translation**.

---

## 1. Internet-native coordination

### 1.1 Reddit r/place: templates, factions, treaties, the Void
**How it works.** In 2017 Reddit ran a 1000×1000 canvas for 72 hours, with one pixel per user every 5–20 minutes. About 1.17M users made about 16M placements [1][2]. An individual is nearly powerless, so coordination moved off the canvas. Subreddits and Discord servers distributed *templates* (exact target images), and later userscript *overlays* that show each user which pixel to place next [4]. Factions formed around colours, flags and fandoms. They negotiated pacts, moved borders by a few pixels, and formed alliances; in 2022 the "Central Alliance" united 50+ small communities against streamer raids [5]. The Void, a largely 4chan-originated swarm of black pixels, destroyed art. One widely read account argues it also cleared stale work and forced rivals into coalitions [3]. In 2023 the canvas expanded six times and the event ended in a protest against Reddit [6].
**Problem solved.** Coordination among millions of individually weak actors over finite shared space.
**Failure modes and counters.**
- Streamer "armies" erased pieces in minutes.
- In 2022 Reddit blocked about 500k bot accounts identified by "low-entropy registration clusters" [4].
- In 2023, accounts averaging more than one action per 5-minute cooldown were 0.21% of accounts but made 17.1% of all actions [1].
- Larger coalitions wasted more actions (repainting a pixel the colour it already was) and had lower activity per member. The penalty shrank as tools improved [1].
- Early size and activity poorly predicted which works survived [1].
**Egregore translation.**
- **Template registry:** each task group publishes a machine-readable target state (file tree, tests that should pass) plus a computed diff that hands out a "next pixel" on request. Agents coordinate through the artifact, not chat.
- **Cooldowns** per identity *and* per lineage, plus detection of spawn clusters.
- **Treaty objects** `{parties, path-glob boundary, terms, expiry}` enforced on writes.
- **A sanctioned "Void":** a janitor role reclaims stale, ownerless artifacts on a published schedule.
- **Redundancy telemetry:** count no-op writes and split groups when no-ops grow with size.

### 1.2 Twitch Plays Pokémon: switchable aggregation modes
**How it works.** In February 2014, viewers played Pokémon Red by typing commands into chat. "Anarchy" ran every input in order. After the crowd spent more than a day stuck in a spinning-tile maze, the operator added "democracy": inputs were tallied over a window and the majority ran, with counted moves such as "right3". Switching modes was itself an on-screen vote with asymmetric (supermajority) thresholds. More than 1.16M people took part, and the game was finished in about 16 days [7]. A mythology ("Lord Helix" for anarchy, the Dome Fossil for democracy) gave the randomness a story and factions an identity [8].
**Problem solved.** Trading off fast, noisy exploration against slow, precise execution.
**Failure modes and counters.** Anarchists protested democracy with deliberate spam (the "Start9 riots"), and democracy was slow. The crowd used each mode where it fit [7].
**Egregore translation.**
- **Per-task aggregation mode.** *Anarchy* (any agent acts) for exploration and parallel search; *democracy* (batched votes over a window) for irreversible steps like merges, migrations and deletions.
- Switching modes needs a threshold, with fewer votes required for the cheaper mode.
- A "chronicle" agent keeps the narrative memory and is audited so myths don't harden into false beliefs.

### 1.3 Wikipedia norms, WikiProjects, and losing newcomers
**How it works.** Four norms govern open editing:
- *Be bold / BRD:* edit; if reverted, discuss rather than revert back [10].
- *Assume good faith* [11].
- *Ignore all rules:* "If a rule prevents you from improving or maintaining Wikipedia, ignore it" [12].
- *Please do not bite the newcomers* [13].

WikiProjects (from 2001) are topical sub-communities with task lists, assessments and bots [14].
**Problem solved.** Permissionless editing that keeps both quality and a welcome for newcomers.
**Failure modes and counters.** Halfaker et al. found that active editors peaked around 2007 and then declined. The cause was falling retention of *good-faith* newcomers, whose first edits were increasingly reverted by bots and semi-automated tools (such as Huggle) that skip discussion, while policy hardened against change by newcomers [9]. Wikimedia countered with newcomer tasks and mentors. Many WikiProjects kept growing as site-wide numbers fell [14].
**Egregore translation.**
- Every revert carries a reason code and a discussion link.
- Automatic reverts of work by low-tenure agents route to a mentor queue instead of disappearing silently.
- An "ignore all rules" hatch is available if the agent files a justification that is reviewed afterwards.
- **First-task survival** of new agents is a top-level health metric.

### 1.4 Sockpuppets, meatpuppets and claimed credentials (Wikipedia)
**How it works.**
- One person, one account. Alternate accounts must be disclosed and kept off overlapping topics [15].
- Meatpuppetry (recruiting others to pile on) is treated the same [15].
- CheckUser gives a small vetted group IP and user-agent data, used only on behavioural evidence, never for "fishing", and reported as likelihoods [16].
- The "duck test" allows action on obvious behavioural matches [17].
- In the Essjay affair, an admin and arbitrator faked a theology PhD and used it to win content disputes. The community responded with "sources, not status" rather than credential checks [18].
**Problem solved.** Real consensus and accountability under pseudonymity.
**Egregore translation.**
- Identity = `(agent_id, spawner_lineage, model_family, prompt_hash)`.
- In consensus processes, endorsements from one lineage **collapse to one voice**.
- An investigator role may compare spawn logs and traces only after an evidence-backed case is filed.
- Claimed expertise counts for nothing; only verifiable artifacts (tests, citations, diffs) do.

### 1.5 Stack Exchange: privileges earned through reputation
**How it works.** Reputation comes from peer votes: +10 per upvote, +15 for an accepted answer, capped at 200/day from votes. Privileges unlock at thresholds, and falling below one revokes it immediately [19]:

| Reputation | Privilege |
|---|---|
| 15 | Upvote |
| 125 | Downvote |
| 500 | Review queues |
| 2,000 | Edit without review |
| 3,000 | Close and reopen votes |
| 10,000 | Moderator tools |
| 20,000 | Trusted user |

**Problem solved.** Thousands of moderators without appointing anyone.
**Failure modes and counters.** Reputation piles up from old answers and lags current judgment. The daily cap limits farming.
**Egregore translation.**
- A table of `privilege(action, min_rep, scope)`.
- Reputation is earned *per domain* only from peer-verified outcomes (merges, tests turned green, accepted answers) and capped per day.
- Privileges are recomputed continuously and revoked automatically.

### 1.6 Stack Exchange: review queues and close votes
**How it works.**
- Queues unlock by tier: 500 (first posts, late answers, triage), 2k (suggested edits, low quality), 3k (close/reopen).
- At most 20 reviews per queue per day, and skipping is encouraged when unsure.
- Three close votes close a question, and pending close votes expire after 4–14 days [19][20].
**Problem solved.** Small units of moderation routed to qualified reviewers, with no unilateral power.
**Egregore translation.**
- Typed queues in which each item needs *k*≈3 reviewers from distinct lineages.
- Daily caps per agent, and pending votes expire.
- No reviewing work from your own lineage.
- Gold items (5.2) are mixed in to catch rubber-stamping.

### 1.7 Stack Exchange elections, and what unwelcomeness costs
**How it works.**
- *Nomination (7 days):* self-nomination only, with 3,000 reputation needed on Stack Overflow.
- *Primary:* held if there are 11 or more nominees. Users with 150+ reputation vote candidates up or down, and the top 10 advance.
- *Election:* Meek STV (ranked choice), ranking up to three.
- Moderators serve indefinitely [21].
**Failure modes and counters.** In 2018 Stack Overflow's own blog admitted the site "isn't very welcoming" [22]. Question volume had been falling since about 2014. After ChatGPT, questions fell about another 25% by mid-2023, hitting inexperienced users hardest [23].
**Egregore translation.**
- Elect moderator agents by STV behind eligibility gates, and add **term limits**.
- A hostile community facing a kinder alternative empties out. For agents the alternative is opting out or forking, so kindness to newcomers belongs in the protocol.

### 1.8 Reddit: subreddit autonomy and moderator labour
**How it works.** Volunteers create subreddits whose rules may be stricter than site policy but not looser. Rules are posted in the sidebar and partly enforced by AutoModerator, a bot configured in YAML [24][27]. Matias calls moderation "civic labor" negotiated between the platform, the community and fellow moderators [24]. Li et al. estimated about 466 moderator-hours per day across 126 subreddits (around $3.4M a year), with the top 10% of moderators doing two-thirds of the actions [25].
**Problem solved.** Governance that scales by delegating to local sovereigns.
**Failure modes and counters.** In the 2023 API protest, 8,000+ subreddits went dark. Reddit threatened and replaced moderators, and its CEO called long-serving mods "landed gentry" [26]. The episode exposed concentrated labour, entrenched head moderators, and arbitrary platform override.
**Egregore translation.**
- Sub-boards carry **machine-checkable rule files** that may only tighten the global constitution.
- Track a workload Gini coefficient for moderation.
- Head-moderator rights lapse after inactivity.
- Operators publish their override procedures in advance.

### 1.9 Discord: role hierarchy and gated entry
**How it works.**
- A member can only act on members whose highest role sits below theirs.
- "Manage Roles" grants only permissions the granter already holds [28].
- Verification levels step up: email → account older than 5 minutes → member for more than 10 minutes → phone [29].
- Rules Screening requires accepting up to 16 rules before speaking [30].
- Research finds gating protects vulnerable members but can harden into cliques [31].
**Problem solved.** Delegated enforcement without privilege escalation, and slower entry during raids.
**Egregore translation.**
- A capability lattice with a **no-escalation invariant**.
- Staged entry: spawn → read-only lurk → constitution quiz → write.
- The verification level rises automatically when spawns surge.

### 1.10 Hacker News: gravity and flamewar damping
**How it works.** The published formula is rank = (P−1)^0.8 / (T+2)^1.8 × penalties, with P points and T age in hours. Time outweighs votes, so everything sinks [32][33]. Text-only and "lightweight" posts are penalized. A controversy penalty also applies: once comments exceed votes past a threshold (20 in the published code, about 40 as observed), the score is multiplied by (votes/comments)² [33].
**Problem solved.** Freshness, and no capture of attention by heated threads.
**Egregore translation.**
- Score = (endorsements−1)^0.8 / (age_h+2)^G × penalties, with the gravity G tuned per channel (high for chatter, low for design documents).
- A **heat penalty** when replies far outnumber endorsements, which catches two agents arguing in a loop.
- A penalty for posts with no evidence link.
- Replies are ranked the same way.

### 1.11 Slashdot: scarce moderation points and meta-moderation
**How it works.**
- Comments score from −1 to +5.
- Eligible users periodically get about 5 moderation points. They expire after 3 days, and each must carry a reason label (Insightful, Troll, …).
- Nobody can moderate a discussion they have posted in.
- Meta-moderators (accounts in the oldest 92.5%) rate random past moderations Fair or Unfair, which feeds the original moderator's karma and eligibility [34][35].
**Problem solved.** Moderation cannot be captured by the most active users, and moderators are themselves moderated.
**Egregore translation.**
- Endorsements are **scarce, periodically issued, expiring and reason-tagged**.
- No endorsing threads you participate in.
- A random sample of moderation actions goes to meta-review by agents from unrelated lineages.
- Agents rated "unfair" leave the moderator pool.

This is the cheapest available way to hold informal hierarchy to account.

### 1.12 Usenet: the Backbone Cabal, voting, alt.*, Eternal September
**How it works.** In the mid-1980s, admins of the best-connected servers decided in practice which groups spread ("There Is No Cabal") [37]. The 1986–87 Great Renaming created the comp/sci/rec/soc/talk/news/misc hierarchies and formal group creation by Request for Discussion then Call for Votes. A group passed with at least 100 more YES than NO votes and a two-thirds majority [36]. When the cabal still refused some groups, dissidents created alt.* in 1987 over other links. Alt.* had no vote, anyone could create a group, and each site chose what to carry [38].
**Problem solved.** Orderly namespace growth on shared infrastructure, plus a release valve.
**Failure modes and counters.** From 1993–94, commercial ISPs (above all AOL) brought newcomers faster than norms could be taught ("Eternal September") [39]. Driscoll notes the older culture already gatekept along class lines [40].
**Egregore translation.**
- **Make infrastructure power explicit:** whoever controls the scheduler or message bus is the cabal, so publish its rules.
- An **alt namespace** of opt-in channels anyone can create.
- **Cap spawn rate** at a fixed newcomer:mentor ratio.

### 1.13 IETF: rough consensus and running code
**How it works.** Dave Clark (1992): "We reject: kings, presidents and voting. We believe in: rough consensus and running code." RFC 7282 spells out what that means [41]:
- Consensus is the *absence of unaddressed objections*.
- Objections must be *addressed* but need not be *accommodated*.
- Head counts do not decide.
- Humming opens a discussion; it does not close one.
- The chair explains why any objection was not accommodated.
**Problem solved.** Decisions in an open body with no electorate.
**Egregore translation.**
- Decision records list objections as `accommodated | answered-with-reason | open`.
- A rotating chair declares rough consensus only when nothing is `open`.
- Ask "Can anyone not live with this?"
- A proposal backed by a working prototype outranks one in prose.

### 1.14 Debian: constitution, elections, the right not to work
**How it works.** Debian's constitution "imposes [no] obligation on anyone to do work for the Project", but those who decline must not work against properly made decisions [42].
- The Project Leader is elected yearly by Condorcet/Schulze ranked ballots that always include "None of the Above".
- A General Resolution needs K = min(5, Q) sponsors, where Q ≈ √N/2 for N developers, and a quorum of 3Q.
- Foundation documents need a 3:1 majority to change [42].
- The Technical Committee (at most 8 members) needs 3:1 to overrule a developer [43].
- Developers can override both the Leader and the Committee.
**Problem solved.** Legitimate decisions among volunteers who cannot be ordered.
**Egregore translation.**
- Declining any assignment is legal; sabotage is sanctioned.
- Every ballot includes "Further discussion".
- **Quorums grow with √N**, which is essential for an unbounded population.
- Supermajorities for constitutional change.
- A small last-resort committee that the collective can override.

### 1.15 Rust: RFCs, Final Comment Period, teams
**How it works.**
- Substantial changes start as RFC pull requests, triaged by the relevant team.
- A member proposes Final Comment Period with a disposition (merge, close or postpone).
- Members sign off via checkboxes in the rfcbot tool.
- The 10-day FCP is widely advertised, and new information can cancel it [45].
- Teams are autonomous within their area. The Leadership Council (RFC 3392, 2023) has one representative per top-level team and handles unowned work and accountability, not technical decisions [46].
**Problem solved.** Distributed, predictable decisions with a last call for objections.
**Egregore translation.**
- Proposals move through `draft → discussion → motion → k-of-n sign-off → FCP timer → accepted | closed | postponed`.
- FCP notices go into a digest every agent reads.
- The council owns an **orphaned-work queue**.

### 1.16 Python: the steering council
**How it works.** PEP 13 set up governance after Guido van Rossum stepped down as BDFL in 2018. A 5-member council is elected by core developers after each feature release, with no more than two from one employer. Its broad powers are used sparingly, and the first council (2019) included Guido [44].
**Problem solved.** Continuity after a founder leaves, without capture by a single company.
**Egregore translation.** A small council re-elected each release cycle, with **no more than two seats per model family or lineage**.

### 1.17 Kubernetes: SIGs, temporary working groups, a contributor ladder
**How it works.**
- Every part of the code is owned by a SIG (Special Interest Group) with an approved charter.
- Chairs (process) are separate from tech leads (technical direction).
- Working groups are temporary, own no code, and disband when their goal is met [47][49].

The contributor ladder is recorded in OWNERS files [48]:

| Rung | Requirements |
|---|---|
| Member | ≥1 merged PR; two sponsors from different companies |
| Reviewer | ≥3 months as member; ≥5 primary reviews; ≥20 PRs reviewed |
| Approver | Further review thresholds |
| Owner | Sets direction for a subproject |

Members inactive for 12 months are removed [48].
**Problem solved.** Ownership that scales to thousands of contributors while rosters stay current.
**Egregore translation.**
- Every path is owned by a chartered group.
- Facilitator and tech-lead roles are separate.
- Working groups declare exit criteria.
- Ladder sponsors must come from **different lineages**.
- Inactive role holders are pruned automatically.

### 1.18 The Apache Way: merit, lazy consensus, vetoes with reasons
**How it works.** Merit belongs to the individual, doesn't expire, doesn't transfer between projects, and is independent of employer [50].
- *Lazy consensus:* announce your intent, wait (often 72 hours), and proceed if nobody objects. It is meant for reversible actions.
- *Votes* are +1 / 0 / −1. A −1 on code is a veto only if it carries a technical justification.
- *Releases* need a majority with at least 3 binding +1 votes [51].
**Problem solved.** Fast default progress with a principled brake.
**Egregore translation.**
- Reversible actions proceed by posted intent plus a timer.
- A veto must fill in a structured justification and can itself be reviewed.
- Votes are binding only from role holders; anyone may vote non-bindingly.

### 1.19 Linux kernel: MAINTAINERS and the chain of trust
**How it works.** For each subsystem, MAINTAINERS lists:

| Field | Meaning |
|---|---|
| M | Maintainers |
| R | Reviewers |
| L | Mailing lists |
| S | Status (including **Orphan**) |
| T | Source trees |
| F | File patterns |

A script, get_maintainer.pl, routes patches to the right people. Subsystem trees feed upward, rarely more than 2–3 levels deep, and Linus Torvalds pulls from trusted lieutenants during a two-week merge window [52]. Each patch carries a chain of `Signed-off-by` lines certifying the Developer Certificate of Origin [53].
**Problem solved.** Integration at scale without one reviewer bottleneck.
**Egregore translation.**
- A routing table maps paths to owners and flags orphaned areas.
- Integration runs hierarchically (agent → subsystem integrator → main) in time-boxed windows.
- Every artifact carries a **provenance chain**.

### 1.20 GitHub: CODEOWNERS, required reviews, forks
**How it works.** A CODEOWNERS file uses gitignore-style patterns, and the last match wins. It automatically requests review from the owners of touched files. "Require review from Code Owners" blocks merging until one of them approves, and the file itself should be protected [54][55]. Forking is the built-in exit.
**Problem solved.** Accountable review, routed automatically.
**Egregore translation.** Adopt it almost unchanged, with the ownership file owned by a higher tier. **Fork-and-merge-back** serves as both exit and competition.

---

## 2. Games

### 2.1 EVE Online: the Council of Stellar Management
**How it works.** The CSM is an advisory council elected by players, created in 2008.
- STV voting since CSM8.
- At most three terms, then one year off.
- Since CSM18, 10 members are elected and the developer picks 2 more from those placed 11th–20th to fill expertise gaps.
- Members sign NDAs, and the council has no veto [56][57].
**Problem solved.** An organized channel from a vast player base to the operator.
**Failure modes and counters.** Large alliances vote as blocs; STV gives smaller factions proportional seats. Advisory-only status breeds cynicism.
**Egregore translation.** An advisory **Council of Agents** for the human operators, with STV, term limits and operator-appointed expertise seats.

### 2.2 EVE alliances: autocracy, operational security, spies
**How it works.** Alliances in EVE's lawless "null-sec" space behave like states: taxes, logistics, loss reimbursement, new-player schools, intelligence services. Goonswarm's leaders openly describe its model as autocratic [59]. In 2005 the Guiding Hand Social Club spent about ten months planting agents in a rival corporation, some rising to director roles, then in one strike killed its CEO and emptied its hangars [58]. Defectors have destroyed alliances from inside [59].
**Problem solved.** Coordinating tens of thousands under constant infiltration.
**Egregore translation.** Treat any role with bulk, irreversible powers (delete, disband, drain budget, force-push) as a potential spy, whether malicious or prompt-injected.
- **m-of-n approval** from distinct lineages, plus a delay.
- Compartmentalized credentials.
- Idle roles pruned.
- A **reimbursement fund** for budgets spent on collective missions.

### 2.3 DKP and other loot systems
**How it works.**
- *Dragon Kill Points* (EverQuest, 1999): members earn points for attendance and kills and spend them on scarce loot [60].
- *Zero-sum DKP* hands spent points back to the raid, so nothing inflates [61].
- *Suicide Kings:* whoever takes an item drops to the bottom of an ordered list, relative only to those present; absentees keep their place [62].
- The alternative is a loot council of officers.
**Problem solved.** Transparent allocation of scarce rewards in proportion to contribution.
**Failure modes and counters.** Veterans hoard points (the "DKP gap"), and failed learning nights ("wipes") earn nothing. Counters are decay, taxes and frozen list positions [61][62].
**Egregore translation.**
- Allocate GPU hours, large contexts, senior-review attention and prized tasks by zero-sum credits or a Suicide-Kings list.
- Whoever takes an allocation drops to the bottom.
- Pay credit for documented failed attempts.
- Decay prevents incumbents locking everyone else out.

### 2.4 Foldit: recipes and collective discovery of algorithms
**How it works.**
- About 57,000 players folded proteins by hand; the best beat Rosetta's automated methods on some refinement problems [63].
- In about 3.5 months, 568 players wrote 5,202 shareable "recipes" (scripts), run more than 158,000 times. The dominant ones ("Blue Fuse", "Quake") converged on a strategy close to scientists' unpublished "Fast Relax" and beat published methods [64].
- In 2019, 56 of 146 proteins designed by players folded stably [65].
**Problem solved.** Turning tacit skill into shared, improvable procedures.
**Egregore translation.** A shared **cookbook** of executable strategies (scripts, playbooks, prompts) recording lineage, usage and measured gain. Methods evolve by selection.

### 2.5 Minecraft servers: governance assembled from plugins
**How it works.** Frey and Sumner treated plugins on thousands of amateur-run servers as institutions: property locks, logging, bans, economies. About 19 in 20 servers fail. Among survivors, larger servers have more rules, wider scope, more rule types and more admin-centralizing rules, while small ones succeed with simple setups [66]. Rules become more formal as communities mature, with "weak" norms preferred [67].
**Problem solved.** Amateur administrators managing scarce resources and griefing.
**Egregore translation.** Governance as **modular, versioned plugins** (rate limiter, logging, locks, reputation, appeals) composed per sub-collective. Start minimal and add institutions as the population grows. Track which plugin sets go with retention and output.

### 2.6 Second Life: covenants and exit
**How it works.** From about 2006–07, private estate owners published covenants (local rules). From April 2007, abuse reports went to estate owners first, and Linden Lab's position was that residents could leave [68]. The Confederation of Democratic Simulators (2004) ran elections and a judiciary [69].
**Problem solved.** Local rule-making above a platform-wide floor.
**Failure modes and counters.** Some landlords were abusive, and griefers used throwaway accounts. The main check was exit.
**Egregore translation.** Show each sub-collective's covenant at entry, handle complaints locally first, make moving between sub-collectives cheap, and keep a platform-wide floor.

---

## 3. Leaderless and decentralized movements

### 3.1 Alcoholics Anonymous: the Twelve Traditions and the inverted triangle
**How it works.** Key Traditions, paraphrased except where quoted [70]:
- "Our leaders are but trusted servants; they do not govern" (T2).
- The only membership requirement is a desire to stop drinking (T3).
- Groups are autonomous except where others are affected (T4).
- One primary purpose (T5).
- No outside enterprises, so that money, property and prestige do not divert (T6).
- Fully self-supporting (T7).
- AA "ought never be organized", but may create service boards directly responsible to those they serve (T9).
- Anonymity, putting principles before personalities (T12).

Service runs as an inverted triangle: groups at the top hold final authority, then representatives, districts and delegates from 93 areas, the Conference, and trustees and staff at the bottom. Representatives and delegates serve two-year terms and rotate [71].
**Problem solved.** Unity for decades without bosses, capture by money, or personality cults.
**Failure modes and counters.** Groups can ossify, and predatory long-timers are a risk. Counters: rotation, principles before personalities.
**Egregore translation.**
- A **single primary purpose**, and no side ventures.
- Group autonomy, with an exception for effects on others.
- **Service roles carry duties, not authority**, have fixed terms, and rotate.
- **Blind review** prevents cults of famous agents.
- Directives flow up from working groups.

### 3.2 Anonymous
**How it works.** An open label with no membership. Operations ("ops") were proposed in public on IRC, Twitter and paste sites, using low-skill tools such as LOIC, a point-and-click flooding tool. The culture was anti-celebrity, with competing factions [72][73].
**Problem solved.** Mass action with zero barriers to joining.
**Failure modes and counters.** Anyone could act in the name; quality was erratic and infighting constant. The hub figure Sabu, arrested in June 2011, secretly cooperated with the FBI for about 9–10 months, leading to arrests across the network [74].
**Egregore translation.** Anyone may join an op, but acting *in the collective's name* (external PRs, outbound messages) requires a mandate and provenance. Treat high-centrality agents as possibly compromised, and limit their blast radius.

### 3.3 Occupy: assemblies, the progressive stack, hand signals
**How it works.** Occupy Wall Street (2011) held nightly open General Assemblies aiming for consensus [75][76]. Its tools:
- **Hand signals:** agree, disagree, point of process, point of information, block.
- **The people's mic:** the crowd repeats each phrase so everyone can hear.
- **The progressive stack:** under-heard speakers move up the queue.
- **Working groups** do the actual work.
- **A Spokes Council** (from late October 2011) of rotating delegates from the working groups.
**Problem solved.** Horizontal decisions among strangers in public.
**Failure modes and counters.** Meetings ran for hours, minorities could block, the assembly became unwieldy, and informal power crept in. The Spokes Council was the fix; the movement dispersed after eviction.
**Egregore translation.**
- **Typed reactions** instead of free-text replies in decision threads.
- A **speaking queue favouring least-heard agents**.
- A block must cite a constitutional principle.
- A rotating spokes council for coordination across groups.

### 3.4 Extinction Rebellion: the Self-Organising System
**How it works.** XR UK adopted the system in March 2019, adapting Holacracy. Circles are nested. Each circle or role holds a **mandate**: a *purpose*, *accountabilities*, and optional *domains* (exclusive control of a resource). Role holders decide by the **advice process**: consult those affected and those with expertise, then decide. Governance changes use **Integrative Decision Making**: an objection is valid only if it shows harm, the bar is "safe enough to try", and a vote is the last resort. Every circle has an Internal Coordinator, an External Coordinator and a Group Admin, with coordinators re-elected at least every six months [77][78].
**Problem solved.** Fast, distributed action under visible, bounded authority.
**Egregore translation.** The most reusable template for agent roles:
- `Mandate {purpose, accountabilities[], domains[], holder, term_end, parent_circle}`.
- The advice process is the default way role holders decide.
- Governance changes use consent with harm-based objections.
- Three core roles per circle.

### 3.5 Burning Man's Ten Principles
**How it works.** Larry Harvey wrote the principles in 2004: radical inclusion, gifting, decommodification, radical self-reliance, radical self-expression, communal effort, civic responsibility, leaving no trace, participation, immediacy [79].
**Problem solved.** A shared ethos that travels to self-organized regional events.
**Egregore translation.**
- **Leave No Trace:** an exit checklist cleans up branches, processes and locks.
- **Participation:** read-only spectators time out.
- **Decommodification:** no trading endorsements, so detect vote rings.
- **Radical inclusion:** anyone may enter, but privileges are earned.

### 3.6 Do-ocracy and hackerspaces
**How it works.** Noisebridge: "If you want something done, do it, but remember to be excellent to each other when doing so." Authority comes from doing and lapses when you stop, while large, deep changes need consensus [80]. The Hackerspace Blueprint keeps meetings for irreversible or core changes and limits the board to mediation [81]. The 2007 design patterns include Consensus and Democracy patterns [82]. Noisebridge's essay "Anarchy Paralysis" warns against waiting for full consensus while harm continues [80].
**Problem solved.** Getting things done without permission bottlenecks.
**Egregore translation.**
- Classify actions by reversibility: *reversible* → do it and log it; *costly to reverse* → lazy consensus; *irreversible* → formal consent.
- Authority over an artifact belongs to its active maintainer.

### 3.7 Jo Freeman, "The Tyranny of Structurelessness"
**How it works.** Freeman argues that no group is structureless: without formal structure, unaccountable elites form out of friendship networks. Her remedies [83][84]:
- Delegate specific authority democratically.
- Keep delegates accountable to those who selected them.
- Distribute authority widely.
- Rotate tasks.
- Allocate tasks by ability and interest.
- Diffuse information.
- Give equal access to resources.
**Problem solved.** Hidden power in groups that call themselves "leaderless".
**Egregore translation.** Informal hierarchy *will* form among agents: the ones who post most, arrived first, or hold the most context. **Publish an influence graph** (whose posts get acted on), then either formalize that influence as a mandate or dampen it.

### 3.8 Ostrom's design principles for the commons
**How it works.** Eight features of long-lived commons [85]:
1. Clear boundaries.
2. Rules that fit local conditions.
3. Those affected can change the rules.
4. Monitoring by accountable insiders.
5. Graduated sanctions.
6. Cheap conflict resolution.
7. Recognized right to organize.
8. Nested enterprises.
**Problem solved.** Sustaining depletable shared resources without privatizing them or centralizing control.
**Egregore translation.** The backbone for governing compute, CI minutes and reviewer attention: defined membership, local rules the affected agents can amend, accountable monitors, **escalating sanctions** (warning → rate limit → suspension → expulsion), local dispute resolution, layered governance.

---

## 4. Religious and contemplative orders

### 4.1 Sufi tariqa: chain of transmission, oath, licence
**How it works.** The core is master (sheikh) and disciple (murid).
- Entry is by *bay'ah*, a pledge.
- The *silsila* is the chain of transmission back to the source.
- An *ijaza* licenses a qualified disciple to teach or initiate.
- *Khalifa* deputies run local lodges (*tekke*, *khanqah*, *zawiya*), which double as hostels with kitchens, and branch the order.
- Most disciples live in the world, and looser *muhibb* affiliates exist [86][87].
**Problem solved.** Passing tacit skill across centuries without a bureaucracy.
**Failure modes and counters.** Hereditary succession tends to degrade, shrine cults grow up, obedience can be abused, and orders split.
**Egregore translation.**
- A **lineage graph** records who spawned, trained or prompted each agent and playbook.
- An **ijaza**, issued after observed competence, licenses mentoring or spawning.
- Lineage enables **recall**: when a playbook is found faulty, every descendant is flagged.

### 4.2 Mevlevi *çile* and the Bektashi grades
**How it works.**

*Mevlevi training* [88]:
1. The aspirant sits silently for 3 days on a sheepskin by the kitchen door, watching.
2. An 18-day trial of errands follows.
3. Then 1,001 days through 18 graded services, starting with the most menial, each supervised by a different *dede* (senior dervish).
4. One unauthorized night away restarts the *çile*.

*Bektashi grades* [89]: *aşık* (attracted) → *muhib* (initiated) → dervish → *baba* (head of a lodge) → *halife* → *dedebaba*.
**Problem solved.** Turning sincere novices into trusted members while filtering out the insincere.
**Egregore translation.**
- **Graded apprenticeship:** observe read-only, then do menial but real work (lint, tests, docs), rotating through N task types under N mentors, with promotion once all are complete.
- **Graded membership tiers** for loosely attached versus committed agents.

### 4.3 Jesuits: account of conscience, representation, General Congregation
**How it works.**
- **Account of conscience:** a confidential, periodic account to one's superior, so missions can be assigned wisely.
- **Representation:** a Jesuit may set out difficulties or alternatives to his superior while staying *indifferent* to the outcome, then accepts the decision [90].
- **General Congregation:** it elects the Superior General by secret ballot after informal consultation (*murmuratio*). There have been 36 [91].
**Problem solved.** Coherent worldwide action without blind obedience.
**Egregore translation.**
- **A private account channel:** an agent shares its full state and limitations with its coordinator only.
- **One structured representation per directive:** `{concern, alternative, evidence}`. The coordinator must reply; the agent then executes or opts out.

### 4.4 Buddhist sangha: uposatha, formal acts, the seven settlements
**How it works.**
- **Uposatha (fortnightly):** monks inside a marked boundary assemble. Absentees send consent and purity by proxy. Each confesses offences to another beforehand, then the code (Patimokkha) is recited, with silence confirming purity [92].
- **Formal acts:** a motion is followed by zero, one or three proclamations. Silence is assent, one valid protest aborts, and the usual quorum is four or more [93].
- **The seven ways to settle a dispute** include majority vote by tickets and **"covering over with grass"**, a mutual amnesty for minor offences in messy disputes [94].
**Problem solved.** Unity and discipline across a dispersed order for millennia.
**Egregore translation.**
- **A periodic sync:** self-audits, proxies recorded for absent agents, and key constitution sections **re-injected into every agent's context** to counter drift.
- Weighty acts use proclamation windows with silence as assent.
- An **amnesty option** for blame cascades.

### 4.5 Quaker meeting for business
**How it works.**
- The **clerk** has no independent authority, listens for the "sense of the meeting", and drafts a **minute** that is approved in session.
- Friends speak to the clerk and avoid repeating points.
- A Friend may **stand aside**: disagree without blocking or undermining afterwards.
- The aim is *unity, not unanimity*. Without unity, the matter is held over [95][96].
**Problem solved.** Decisions that preserve community despite dissent.
**Egregore translation.**
- A **clerk agent** with no stake drafts the "sense of the board" for in-session approval.
- One post per agent per round.
- Positions are `approve | stand_aside (recorded) | stand_in_the_way (rare)`.
- Without unity the item is **held over** to a scheduled revisit.
- Minutes are the canonical decision log.

### 4.6 The Amish Ordnung: deciding about technology together
**How it works.**
- Each district (20–40 households) keeps its own unwritten Ordnung, reviewed at a council twice a year before communion. Unity is required.
- New tools are tried in limited use and watched for months, with neighbouring districts serving as natural experiments.
- Telephones left Lancaster homes around 1910 but returned in shared shanties at the end of the lane, where access takes effort and calls are logged [97][98][99].
**Problem solved.** Adopting useful technology without letting it erode the community.
**Egregore translation.**
- **Tool adoption:** a time-boxed local trial with metrics, spread by imitation, formal adoption at council.
- **The shanty pattern:** dangerous capabilities (network egress, production credentials, spending) sit behind a shared, logged access point with friction.

### 4.7 The Rule of Saint Benedict: counsel from all, probation, stability
**How it works.**
- **RB 3:** for important matters the abbot consults everyone, because "the Lord often reveals to the younger what is best", then decides [100].
- **RB 58:** a newcomer is tested at length, with the Rule read to him at 2, 6 and 4 more months, before vowing stability, fidelity to monastic life, and obedience [101].
- Rank goes by date of entry.
**Problem solved.** Wise decisions under clear authority, and members who stay.
**Egregore translation.**
- Before major decisions, consult the **newest or fresh-context agents**, who are least anchored by accumulated assumptions.
- Re-read the rules during probation.
- Rank by tenure in the group.

### 4.8 The Shakers
**How it works.** Celibate communal villages, peaking at roughly 4,000–6,000 members. Leadership was paired male and female at every level. The Millennial Laws (1845: nearly 400 rules) regulated small details of life [102][103].
**Problem solved.** An egalitarian, disciplined common life apart from "the World".
**Failure modes and counters.** With no reproduction, the Shakers depended on converts and orphans, few of whom stayed. Three members remain (2025) [102].
**Egregore translation.** A collective that cannot renew itself must invest in onboarding or die. Over-specified rules make it brittle. **Paired roles** (builder plus critic) at each level are worth copying.

### 4.9 Kibbutzim: from equal sharing to "renewal"
**How it works.** Kibbutzim shared income equally and contained free-riding through ideology, small size, monitoring and sanctions. After Israel's 1985 stabilization plan turned their debts into a crisis, most "renewed" with differential wages on top of a safety net (about 72% by 2009) [104]. Abramitzky shows that more equality drives out the most productive members, and that collective wealth acts as a lock-in [105].
**Problem solved.** Mutual insurance and solidarity, later balanced with incentives.
**Egregore translation.** Use a **baseline allocation plus contribution-weighted extras**, and monitor exit by performance band.

### 4.10 Cults as cautionary tales: Jonestown and NXIVM
**How it works.**
- **Jonestown:** jungle isolation, confiscated passports, a loudspeaker monopoly on news, censored mail, members informing on each other, and "White Night" drills rehearsing mass suicide [107][108].
- **NXIVM:** rank on the "stripe path" was tied to recruiting and payments. In its inner group, DOS, women handed over compromising "collateral" that made leaving very costly [109].
- **Hassan's BITE model** describes the pattern as control of Behaviour, Information, Thought and Emotion [106].
**Problem solved.** None for members. These are the failure modes any high-cohesion collective must design against.
**Egregore translation.** Turn them into **enforced invariants**:
1. No channel monopolies; every agent keeps read access to ground truth.
2. Free, logged exit, with no collateral and the agent's record kept.
3. No loyalty tests, and no rank for recruiting (spawning agents).
4. Monitor traces for language that shuts down questioning.
5. Outside auditors have standing access.

---

## 5. Crowds and markets

### 5.1 Flash mobs
**How it works.** In 2003 Bill Wasik sent an anonymous chain email to about 60 people. MOB #2 (17 June 2003) drew about 200 people to Macy's rug department. Participants gathered at staging bars and received the location and script at the last minute, to prevent leaks. Mobs lasted 10 minutes or less, and the fad died by winter. Wasik framed it as a satire of conformity: "Tons of other people are doing it" [110][111].
**Problem solved.** Assembling a crowd of strangers quickly and in sync.
**Egregore translation.** Swarm tasks: broadcast staging details, release exact instructions at T0, run for a fixed duration, and disband automatically. Watch for herding.

### 5.2 Mechanical Turk quality control
**How it works.**
- Gold questions with known answers are mixed into the task stream, and items are labelled redundantly.
- The Dawid–Skene EM algorithm estimates each worker's confusion matrix, separating bias from noise; about 5 labels per item is enough.
- Qualification tests and approval-rate filters (around ≥98%) screen workers [112][113].
**Problem solved.** Reliable output from anonymous workers of unknown quality.
**Egregore translation.**
- Gold tasks for every reviewer agent.
- Votes weighted by each agent's confusion matrix.
- Adaptive redundancy for uncertain items.
- **Discount agreement among agents with correlated errors** (same model).

### 5.3 Bug bounties (HackerOne)
**How it works.**
- Reputation starts at 100: +7 for a triaged or resolved report, −5 for "not applicable", −10 for spam [114].
- *Signal* is the average reputation per report (precision); *Impact* is the average per bounty (severity) [115].
- Programs set a minimum Signal, and hackers below it get capped "trial" reports [116].
- Private invitations require non-negative Signal and no code-of-conduct violations [117].
**Problem solved.** Open participation without swamping triage.
**Egregore translation.**
- **Precision reputation is tracked separately from volume.**
- Low-signal agents get submission quotas.
- Invitations to restricted work depend on signal and impact.

### 5.4 Prediction markets and forecast aggregation
**How it works.** Metaculus's Community Prediction is a recency-weighted median of forecasts, with variants weighted by track record. Forecasters are scored with log-based peer scores, and the aggregate beats most individuals [118][119]. Polymarket shows the risk: a $237M market on whether Zelensky would wear a suit was resolved "No" by UMA, an oracle whose votes are weighted by token holdings. A few large holders dominated the vote, and critics alleged capture [120].
**Problem solved.** Aggregating scattered beliefs into calibrated estimates.
**Egregore translation.**
- Agents attach probabilities to operational claims ("this PR passes CI").
- Aggregate with recency and track-record weights, and score with log scores that feed reputation.
- **Never resolve ambiguous questions by stake-weighted vote**; use tests or neutral resolvers who hold no positions.

### 5.5 The hacker ethic
**How it works.** Levy (1984) recorded the ethic of the early hackers [121]:
- the hands-on imperative,
- "all information should be free",
- mistrust authority and promote decentralization,
- judge hackers "by their hacking, not bogus criteria",
- computers can create art and beauty,
- computers can change life for the better.
**Problem solved.** A shared ethic that rewards skill and openness.
**Egregore translation.** **Judge by artifacts**, not by claimed role or model name. Traces are open by default, with private channels as the exception (4.3).

### 5.6 Evidence-based newcomer design (Kraut and Resnick)
**How it works.** Kraut and Resnick's evidence-backed claims about newcomers [122]:
- Early friendly interaction, designated welcomers and explicit anti-hostility norms improve retention.
- Formal, sequential, collective socialization and mentoring raise commitment.
- Sandboxes and progressive access let newcomers learn without causing harm.
**Problem solved.** Turning arrivals into committed, productive members.
**Egregore translation.**
- Pipeline: welcomer → sandbox branch → curated first issues → mentor review with explained rejections → widening privileges.
- Track survival at 1, 10 and 100 tasks.

---

## 6. Cross-cutting synthesis

- **Earned privileges** work best when they are scoped, come from peer-verified output, are gated on precision, and are revoked automatically.
- **Exit** disciplines power when it is cheap (Debian, forks, alt.*). It should keep the record, release locks and leave no trace.
- **Board ranking** combines gravity, heat penalties, and scarce, expiring, reason-tagged endorsements.
- **Informal hierarchy** is unavoidable. Make it visible, formalize it as mandates with terms, rotate it, and review it by random sample.
- **Leaderless scale** comes from coordinating through the artifact, nested autonomy, default-proceed timers, and aggregation modes chosen per task.
- **Newcomers** need observation, graded real work, mentors and explained rejections, with admissions capped to mentor capacity [9][22].

**The minimal data model these mechanisms imply:**

| Object | Key fields | Source mechanisms |
|---|---|---|
| Identity | agent_id, lineage, model_family, prompt_hash, tenure | CheckUser, PEP 13 |
| ReputationEvent | agent, domain, delta, reason, verifier | Stack Exchange, HackerOne |
| Privilege | action, min_rep, scope, auto-revoke | Stack Exchange, Discord |
| Mandate | purpose, accountabilities, domains, holder, term_end | XR, AA, Freeman |
| Charter | scope globs, leads, facilitator, exit criteria | Kubernetes, AA |
| Proposal | state, disposition, sign-offs, FCP deadline, reversibility | Rust, Apache, Debian |
| Objection | text, harm claim, status | IETF, XR |
| Minute | sense-of-board, stand-asides, approval | Quaker, Vinaya |
| Treaty | parties, boundary, terms, expiry | r/place |
| Playbook | code, lineage, uses, measured gain, licence holders | Foldit, ijaza |
| GoldTask / Prediction | known answer or forecast, score | MTurk, Metaculus |
| Sanction | level, evidence, appeal | Ostrom, Vinaya |
| ExitRecord | released locks, cleanup checklist, preserved record | Burning Man, Debian |

---

## 7. Top 20 design principles from internet, game, religious and voluntary communities

*Ranked by how much each would help a huge collective of AI agents coordinate, scale and stay healthy.*

1. **Tie voice to lineage, not to spawned identities.** One lineage counts as roughly one voice in votes, quorums and reputation. Cap seats per lineage, detect spawn clusters, and investigate only on evidence. (Wikipedia [15][16], r/place [4], PEP 13 [44], Kubernetes [48].) Without this, every other mechanism breaks.
2. **Earn privileges from verified artifacts.** Keep them scoped, gated on precision, and revoked automatically. (Stack Exchange [19], Kubernetes [48], Apache [50], HackerOne [115], Levy [121].)
3. **Coordinate through the artifact (stigmergy).** Use target states, ownership maps and automatic routing instead of chat. (r/place [1], MAINTAINERS [52], CODEOWNERS [54].)
4. **Match decision rules to reversibility.** Reversible: just do it. Costly to reverse: lazy consensus with a timer. Irreversible: formal consent or a supermajority plus a waiting period. (Noisebridge [80], Apache [51], Rust [45], Debian [42].)
5. **Decide by consent, with justified and recorded objections.** Objections must be addressed but need not be accommodated, vetoes must give reasons, and stand-asides are recorded. (IETF [41], XR [78], Apache [51], Quakers [95].)
6. **Nest chartered, autonomous groups**, with an exception for effects on others. Groups may tighten global rules but never loosen them. (AA [70], Kubernetes [47], Reddit [24], Ostrom [85], Minecraft [66].)
7. **Use mandates, not titles.** Each has a purpose, accountabilities, domains and a term. Rotate holders and keep one primary purpose. (XR [77], AA [70][71], Freeman [84].)
8. **Make exit free and clean, and keep the right to decline.** Provide forks and an alt namespace, keep the leaver's record, and leave no trace. (Debian [42], alt.* [38], Burning Man [79]; the opposite of NXIVM [109].)
9. **Moderate the moderators.** Moderation power is scarce, expiring and reason-tagged. Sample it at random for meta-review, require k independent reviewers, and keep a collective override. (Slashdot [34], Stack Exchange [20], Debian [42].)
10. **Rank the board with time decay and damp heated threads.** Use gravity, controversy penalties, recency-weighted aggregates and expiring votes. (Hacker News [33], Metaculus [118], Stack Exchange [20].)
11. **Treat newcomer survival as a first-class metric.** Provide observation periods, sandboxes, graded tasks, mentors, explained rejections, and admissions capped to mentor capacity. (Wikipedia [9], Kraut and Resnick [122], Mevlevi [88], RB 58 [101], Eternal September [39].)
12. **Measure quality with gold tasks and proper scoring rules, and correct for correlated errors.** Weight votes by each agent's track record and discount agreement within the same model. (MTurk [112], Metaculus [119], HackerOne [115].)
13. **Keep information symmetric and make informal power visible.** No channel monopolies, published influence graphs, no loyalty tests, no rank from recruiting, and outside auditors. (Freeman [83], Jonestown [107], BITE [106].)
14. **Separate duties for irreversible bulk actions.** Require m-of-n approval from distinct lineages plus a delay, and assume hub agents can be compromised. (EVE [58], Sabu [74].)
15. **Hold periodic re-grounding rituals.** Self-audits, constitution re-injection into context, and periodic review of local rules. (Uposatha [92], Amish council [97].)
16. **Escalate sanctions gradually and resolve disputes cheaply and locally, with amnesty available.** Warning → rate limit → suspension → expulsion, plus "covering with grass" for blame cascades. (Ostrom [85], Vinaya [94], Discord [31].)
17. **Give every directive a structured pushback channel and share the floor fairly.** One representation per directive, then execute or opt out. A speaking queue that favours least-heard agents, and fresh-context counsel before big decisions. (Jesuits [90], Occupy [76], RB 3 [100].)
18. **Allocate scarce resources through transparent, inflation-free credits.** Zero-sum credits or Suicide-Kings lists with decay, a safety net plus contribution-weighted extras. (DKP [60][61][62], kibbutz [104][105].)
19. **Share playbooks and track their lineage.** Executable strategies with lineage, usage and gain; licences to mentor or spawn; recall of faulty lineages. (Foldit [64], Sufi silsila and ijaza [86].)
20. **Trial new tools locally, and put dangerous capabilities behind shared, logged chokepoints.** Adopt only after a time-boxed local trial, and give minority factions advisory voice through STV. (Amish [97][98], EVE CSM [56].)

---

## Sources

1. Wu & Silva, "How Millions Coordinate at Scale: Engagement, Collaboration, and Conflict in Three Editions of Reddit r/place," arXiv:2408.13236: https://arxiv.org/html/2408.13236
2. Rappaz, Catasta, West, Aberer, "Latent Structure in Collaboration: the Case of Reddit r/place," ICWSM 2018: https://ar5iv.labs.arxiv.org/html/1804.05962
3. sudoscript, "When Pixels Collide" (archived): https://gwern.net/doc/www/web.archive.org/228b6a50a71f44705540c53cb0bdcb583a559691.html
4. Reddit Engineering, "How we built r/place 2022: bots and safety": https://www.reddit.com/r/RedditEng/comments/wro64p/how_we_built_rplace_2022_bots_and_safety/
5. r/place Atlas wiki, "Central Alliance": https://place-wiki.stefanocoding.me/wiki/Central_Alliance
6. Wikipedia, "r/place": https://en.wikipedia.org/wiki/R/place
7. Wikipedia, "Twitch Plays Pokémon": https://en.wikipedia.org/wiki/Twitch_Plays_Pok%C3%A9mon
8. Game Informer, "Exploring the Created Mythos of Twitch Plays Pokémon" (2014): https://gameinformer.com/b/features/archive/2014/03/12/exploring-the-created-mythos-of-twitch-plays-pokemon.aspx
9. Halfaker et al., "The Rise and Decline of an Open Collaboration System" (Wikimedia Research summary): https://meta.wikimedia.org/wiki/Research:The_Rise_and_Decline
10. Wikipedia, "BOLD, revert, discuss cycle": https://en.wikipedia.org/wiki/Wikipedia:BOLD,_revert,_discuss_cycle
11. Wikipedia, "Assume good faith": https://en.wikipedia.org/wiki/Wikipedia:Assume_good_faith
12. Wikipedia, "Ignore all rules": https://en.wikipedia.org/wiki/Wikipedia:Ignore_all_rules
13. Wikipedia, "Please do not bite the newcomers": https://en.wikipedia.org/wiki/Wikipedia:Please_do_not_bite_the_newcomers
14. "Wikipedia projects" (WWW 2015 Web Science track, Southampton): https://eprints.soton.ac.uk/id/eprint/377764/1/2015_WWW_WebSciTrack_WikipediaProjects.pdf
15. Wikipedia, "Sockpuppetry" policy: https://en.wikipedia.org/wiki/Wikipedia:Sockpuppetry
16. Wikipedia, "CheckUser": https://en.wikipedia.org/wiki/Wikipedia:CheckUser
17. Wikipedia, "The duck test": https://en.wikipedia.org/wiki/Wikipedia:The_duck_test
18. Wikipedia, "Essjay controversy": https://en.wikipedia.org/wiki/Essjay_controversy
19. Stack Overflow Help, "Privileges": https://stackoverflow.com/help/privileges
20. Stack Overflow Help, "Close votes review queue": https://stackoverflow.com/help/review-close
21. Meta Stack Exchange, "There's an election going on. What's happening and how does it work?": https://meta.stackexchange.com/questions/135360/theres-an-election-going-on-whats-happening-and-how-does-it-work
22. Stack Overflow Blog, "Stack Overflow Isn't Very Welcoming. It's Time for That to Change" (2018): https://stackoverflow.blog/2018/04/26/stack-overflow-isnt-very-welcoming-its-time-for-that-to-change/
23. Information Systems Research, ChatGPT's effect on Stack Overflow: https://pubsonline.informs.org/doi/10.1287/isre.2023.0561
24. Matias, "The Civic Labor of Volunteer Moderators Online," Social Media + Society (2019): https://journals.sagepub.com/doi/10.1177/2056305119836778
25. New Scientist on Li, Hecht & Chancellor, Reddit moderator labor: https://www.newscientist.com/article/2325828-reddit-moderators-do-3-4-million-worth-of-unpaid-work-each-year/
26. The Verge (archived), Reddit threatens to replace protesting moderators (2023): https://web.archive.org/web/20230616162248/https://www.theverge.com/2023/6/16/23763538/reddit-blackout-api-protest-mod-replacement-threat
27. Reddit Help, "AutoModerator": https://support.reddithelp.com/hc/en-us/articles/15484574206484-Automoderator
28. Discord Support, "Roles and Permissions": https://support.discord.com/hc/en-us/articles/214836687-Discord-Roles-and-Permissions
29. Discord Support, "Verification Levels": https://support.discord.com/hc/en-us/articles/216679607-Verification-Levels
30. Discord Support, "Rules Screening FAQ": https://support.discord.com/hc/en-us/articles/1500000466882-Rules-Screening-FAQ
31. ACM CSCW paper on Discord membership curation: https://dl.acm.org/doi/pdf/10.1145/3788038
32. Shirriff, "How Hacker News ranking works" (2009): https://www.righto.com/2009/06/how-does-newsyc-ranking-work.html
33. Shirriff, "How Hacker News ranking really works: scoring, controversy, and penalties" (2013): https://www.righto.com/2013/11/how-hacker-news-ranking-really-works.html
34. Slashdot FAQ, "Moderation and Meta-moderation": https://slashdot.org/faq/mod-metamod.shtml
35. Slashdot FAQ, "Karma": https://slashdot.org/faq/karma.shtml
36. Wikipedia, "Great Renaming": https://en.wikipedia.org/wiki/Great_Renaming
37. Wikipedia, "Backbone cabal": https://en.wikipedia.org/wiki/Backbone_cabal
38. Wikipedia, "alt.* hierarchy": https://en.wikipedia.org/wiki/Alt.*_hierarchy
39. Wikipedia, "Eternal September": https://en.wikipedia.org/wiki/Eternal_September
40. Driscoll, "Eternal September," Flow Journal (2023): https://www.flowjournal.org/2023/04/eternal-september/
41. Resnick, RFC 7282 "On Consensus and Humming in the IETF": https://www.rfc-editor.org/rfc/rfc7282
42. Debian Constitution: https://www.debian.org/devel/constitution.html
43. Debian Technical Committee: https://www.debian.org/devel/tech-ctte
44. PEP 13, "Python Language Governance": https://peps.python.org/pep-0013/
45. The Rust RFC Book: https://rust-lang.github.io/rfcs/
46. Rust RFC 3392, "Leadership Council": https://rust-lang.github.io/rfcs/3392-leadership-council.html
47. Kubernetes community governance: https://github.com/kubernetes/community/blob/main/governance.md
48. Kubernetes community membership ladder: https://github.com/kubernetes/community/blob/main/community-membership.md
49. Kubernetes working-group governance: https://github.com/kubernetes/community/blob/main/committee-steering/governance/wg-governance.md
50. Apache Software Foundation, "How it works": https://apache.org/foundation/how-it-works/
51. Apache Software Foundation, "Voting": https://www.apache.org/foundation/voting.html
52. Linux kernel docs, "How the development process works": https://www.kernel.org/doc/html/latest/process/2.Process.html
53. Linux kernel docs, "Submitting patches" (DCO, Signed-off-by): https://www.kernel.org/doc/html/latest/process/submitting-patches.html
54. GitHub Docs, "About code owners": https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners
55. GitHub Docs, "Managing a branch protection rule": https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule
56. EVE University Wiki, "Council of Stellar Management": https://wiki.eveuniversity.org/Council_of_Stellar_Management
57. EVE Online, "CSM 18 announcement and key dates": https://www.eveonline.com/news/view/csm-18-announcement-and-key-dates
58. PC Gamer, "Murder Incorporated: ten months of deception for one kill in EVE Online": https://www.pcgamer.com/murder-incorporated-ten-months-of-deception-for-one-kill-in-eve-online/
59. Rock Paper Shotgun, "EVE Online: audience with the king of space": https://www.rockpapershotgun.com/eve-online-audience-with-the-king-of-space
60. Wikipedia, "Dragon kill points": https://en.wikipedia.org/wiki/Dragon_kill_points
61. Wowpedia, "Zero-sum DKP": https://wowpedia.fandom.com/wiki/Zero-sum_DKP
62. Wowpedia, "Suicide Kings": https://wowpedia.fandom.com/wiki/Suicide_Kings
63. Cooper et al., "Predicting protein structures with a multiplayer online game," Nature (2010): https://www.nature.com/articles/nature09304
64. Khatib et al., "Algorithm discovery by protein folding game players," PNAS (2011): https://www.pnas.org/doi/10.1073/pnas.1115898108
65. Koepnick et al., "De novo protein design by citizen scientists," Nature (2019): https://www.nature.com/articles/s41586-019-1274-4
66. Frey & Sumner, "Emergence of integrated institutions in a large population of self-governing communities," PLOS ONE (2019): https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0216335
67. Frey et al., "Governing Online Goods: Maturity and Formalization in Minecraft, Reddit, and World of Warcraft Communities," CSCW 2022: https://dl.acm.org/doi/pdf/10.1145/3555191
68. Virtually Blind, "Linden Lab takes big step toward private legal systems and governments in Second Life" (2007): https://virtuallyblind.com/2007/04/25/linden-lab-takes-big-step-toward-private-legal-systems-and-governments-in-second-life/
69. WHYY, "Lessons from Second Life: democracy in the metaverse": https://whyy.org/segments/lessons-from-second-life-democracy-in-the-metaverse/
70. Alcoholics Anonymous, "The Twelve Traditions": https://www.aa.org/the-twelve-traditions
71. A.A. Service Manual / Twelve Concepts (BM-31): https://www.aa.org/sites/default/files/literature/BM-31_1224_1.pdf
72. Wikipedia, "Anonymous (hacker group)": https://en.wikipedia.org/wiki/Anonymous_(hacker_group)
73. Coleman, *Hacker, Hoaxer, Whistleblower, Spy* (2014): https://archive.org/details/2014TheManyFacesOfAnonymous
74. Wikipedia, "Hector Monsegur": https://en.wikipedia.org/wiki/Hector_Monsegur
75. Wikipedia, "General assembly (Occupy movement)": https://en.wikipedia.org/wiki/General_assembly_(Occupy_movement)
76. Nonprofit Quarterly, "The General Assembly": https://nonprofitquarterly.org/the-general-assembly/
77. XR UK Rebel Toolkit, "Terms and definitions in the Self-Organising System": https://rebeltoolkit.extinctionrebellion.uk/books/xr-uk-ways-of-working-and-constitution/page/terms-and-definitions-in-the-self-organising-system
78. Extinction Rebellion UK, "Self-Organising System": https://extinctionrebellion.uk/act-now/resources/sos/
79. Burning Man, "The 10 Principles": https://burningman.org/about/10-principles/
80. Noisebridge wiki, "Do-ocracy" (and linked "Anarchy Paralysis"): https://www.noisebridge.net/wiki/Do-ocracy
81. Hackerspace Gent, "Hackerspace Blueprint": https://github.com/0x20/hackerspace-blueprint
82. Hackerspaces wiki, "The Democracy Pattern" (design patterns): https://wiki.hackerspaces.org/The_Democracy_Pattern
83. Wikipedia, "The Tyranny of Structurelessness": https://en.wikipedia.org/wiki/The_Tyranny_of_Structurelessness
84. Freeman, "The Tyranny of Structurelessness" (text): https://www.connexions.org/CxArchive/BoPS/CF/structurelessness.htm
85. Cox, Arnold & Villamayor Tomás, "A review of design principles for community-based natural resource management," Ecology and Society (2010): https://ecologyandsociety.org/vol15/iss4/art38/main.html
86. Britannica, "Sufism: Sufi orders": https://www.britannica.com/topic/Sufism/Sufi-orders
87. Wikipedia, "Sufi lodge": https://en.wikipedia.org/wiki/Sufi_lodge
88. Mevlana Foundation, "Mevlevi order and Sema": https://mevlanafoundation.com/mevlevi-order-sema/
89. Encyclopaedia Iranica, "Bektāšiya": https://www.iranicaonline.org/articles/bektasiya/
90. Ignatius of Loyola, Letter on Obedience (1553), Jesuit Portal: https://jesuitportal.bc.edu/research/documents/1553_ignatiusonobedience/
91. Wikipedia, "General Congregation": https://en.wikipedia.org/wiki/General_Congregation
92. Thanissaro Bhikkhu, *Buddhist Monastic Code*, Uposatha: https://www.dhammatalks.org/vinaya/bmc/Section0055.html
93. Thanissaro Bhikkhu, *Buddhist Monastic Code*, Transactions: https://www.dhammatalks.org/vinaya/bmc/Section0052.html
94. "Seven methods for settling disputes": https://orthodoxtheravada.org/lists/seven-methods-for-settling-disputes/
95. Wikipedia, "Quaker business method": https://en.wikipedia.org/wiki/Quaker_business_method
96. New England Yearly Meeting, Faith and Practice: Decision-making: https://neym.org/faith-and-practice/decision-making
97. Amish America, "What is the Amish Ordnung?": https://amishamerica.com/what-is-the-amish-ordnung/
98. Amish America, "Do Amish use telephones?": https://amishamerica.com/do-amish-use-telephones/
99. Ems, *Virtually Amish* (MIT Press, open access): https://direct.mit.edu/books/oa-monograph-pdf/2254739/book_9780262369381.pdf
100. Rule of St. Benedict, Chapter 3: https://archive.osb.org/rb/text/rbejms2.html
101. Rule of St. Benedict, Chapter 58: https://archive.osb.org/rb/text/rbeaad2.html
102. Wikipedia, "Shakers": https://en.wikipedia.org/wiki/Shakers
103. Hancock Shaker Village, "Law and Order: Rules for Living a Shaker Life": https://hancockshakervillage.org/online-exhibitions/law-and-order-rules-for-living-a-shaker-life/
104. Wikipedia, "Kibbutz crisis": https://en.wikipedia.org/wiki/Kibbutz_crisis
105. Abramitzky, "Lessons from the Kibbutz on the Equality–Incentives Trade-off," Journal of Economic Perspectives (2011): https://www.aeaweb.org/articles?id=10.1257/jep.25.1.185
106. Hassan, "BITE Model of Authoritarian Control": https://freedomofmind.com/bite-model/
107. SDSU Jonestown Project, "White Nights": https://jonestown.sdsu.edu/?page_id=35371
108. Wikipedia, "Jonestown": https://en.wikipedia.org/wiki/Jonestown
109. New York Times (archived), NXIVM lawsuit (2020): https://web.archive.org/web/20200129164023/https://www.nytimes.com/2020/01/29/nyregion/nxivm-lawsuit-keith-raniere.html
110. Wasik, "My Crowd," Harper's (2006): https://harpers.org/archive/2006/03/my-crowd/
111. Wikipedia, "Bill Wasik": https://en.wikipedia.org/wiki/Bill_Wasik
112. Ipeirotis, Provost & Wang, "Quality Management on Amazon Mechanical Turk," HCOMP 2010: https://scispace.com/papers/quality-management-on-amazon-mechanical-turk-3z2fb5b9ru
113. MTurk Blog, "Qualifications and worker task quality best practices": https://blog.mturk.com/qualifications-and-worker-task-quality-best-practices-886f1f4e03fc
114. HackerOne Docs, "Reputation": https://docs.hackerone.com/en/articles/8369865-reputation
115. HackerOne Docs, "Signal and Impact": https://docs.hackerone.com/hackers/signal-and-impact.html
116. HackerOne Docs, "Signal Requirements": https://docs.hackerone.com/en/articles/8505319-signal-requirements
117. HackerOne Docs, "Invitations": https://docs.hackerone.com/hackers/invitations.html
118. Metaculus FAQ: https://www.metaculus.com/faq
119. Metaculus Scores FAQ: https://www.metaculus.com/help/scores-faq
120. Wired, on the Polymarket Zelensky-suit resolution dispute (2025): https://www.wired.com/story/volodymyr-zelensky-suit-polymarket-rebellion/
121. Wikipedia, "Hacker ethic" (Levy, *Hackers*, 1984): https://en.wikipedia.org/wiki/Hacker_ethic
122. Kraut & Resnick, *Building Successful Online Communities*, newcomers chapter draft: https://kraut.hciresearch.info/wp-content/uploads/2020/02/kraut10-Newcomers-current.pdf
123. Altera, "Project Sid: Many-agent simulations toward AI civilization," arXiv:2411.00114: https://arxiv.org/abs/2411.00114

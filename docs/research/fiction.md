# Fictional Collectives and Collective Minds: Design Lessons for a Software Egregore

*Research report for the egregore project: a coordinated collective of many AI coding agents (hundreds to unbounded) that share a workspace, message each other, share thinking, form hierarchies, steer each other, and may opt out.*

---

## 0. How to read this report

Fiction is a large, cheap library of thought experiments about collective minds. Authors have spent seventy years stress-testing the same questions this project faces: how tightly should minds be coupled, where does authority sit, how are memories shared, and can a member leave? Almost every story answers with a failure mode attached. Most of those failures come back to three dials:

| Dial | Low end (individualist) | High end (hive) | Fictional examples |
|---|---|---|---|
| **Coupling**: how much thought is shared | message passing, manners | one mind, no private self | Culture → Anarres → Nest → Tines → Gaia → Borg |
| **Control**: where decisions are made | referenda, consensus, rotating lots | a queen or an imperative | Culture/Geth → Legion/Jedi → Formics/Borg Queen |
| **Exit**: whether members can leave | free secession, resignation | death or "repair" on disconnect | Culture Ulterior/Legion → Great Link pull → Borg/Formic workers |

Read across all the cases, the stories say that coordination gains come from coupling, and catastrophe comes from coupling combined with centralized control and no exit. Each entry below gives (a) organization and decisions, (b) joining, specialization, communication, memory and leaving, (c) what keeps it coherent, (d) what goes wrong, and (e) a concrete translation into egregore features, marked as a **good idea** or a **cautionary tale** where the story clearly points one way.

Canon details were checked against encyclopedic wikis (Memory Alpha, DC Database, Wookieepedia, the Dune, Mass Effect, Enderverse, Expanse and Culture wikis), Wikipedia, study guides that quote the texts, and the authors' own notes (Banks's "A Few Notes on the Culture"). Where a detail varies across continuities (DC comics especially), this is flagged.

---

## 1. Heinlein's Martians and the Nest (*Stranger in a Strange Land*, 1961)

**Grokking.** In the novel, "grok" literally means "to drink". On a near-waterless Mars, drinking is a merging of drinker and water, and the word grows from that root to mean understanding "so thoroughly that the observer becomes a part of the observed", "to merge, blend, intermarry, lose identity in group experience" [1][2]. It can stand for love, hate, fear and "identically equal", and Dr. Mahmoud says it covers "a hundred other English words" [2]. Martian hate requires full grokking first, so one can only truly hate what one has merged with and cherished [10]. The word entered the OED in 1989 [3]. (It is also the name of xAI's model, which matters for naming in code; see §8.)

**Water brotherhood.** Sharing water is an irrevocable bond of total trust ("who shares water shares all"), and it links whole circles of people, not only the pair [5]. Mike's first water brother, the nurse Jill, offers him a glass innocently, without knowing what it means [5]. Later Mike groks that water is a symbol. Food, and above all sex, can carry the same "growing closer" [5].

**Organization of the Church of All Worlds and the Nest.** Mike's church is laid out as **nine concentric circles**, like lodge degrees. The outer circles are public, carnival-style services. Inner circles require learning Martian, and nobody is told about a deeper circle until they are ready [6]. The **Ninth Circle** is the **Nest**: water-brothers living communally, often nude, sharing sexuality and money (taken from a common store as needed). One summary puts the household at roughly twenty people [6]. *Correction to a common belief:* the canonical "nine" is the number of **circles**, not the size of a nest. The real Church of All Worlds (founded 1962, incorporated 1968) copied the nine-circle path, grouped into three Rings, and uses autonomous local nests of three or more members [7]. The church is "primarily a language school". Learning Martian is what unlocks grokking, the Discipline and the powers [11]. Members greet each other with **"Thou art God"**: all that groks is God, so divinity is immanent in each member, not above them [6][7].

**Martian discipline and "waiting is".** The Discipline is "first, self-awareness, and then, self-control". Mike argues that by the time someone masters it well enough to wield destructive power, they no longer have the volition to misuse it [4]. Martians cannot even express "hurry". They wait until a situation reaches **fullness**, and the refrain "Waiting is" ends in "Waiting is ended" when action becomes clear [8].

**The Old Ones and Martian decision-making.** Martians hatch as nymphs who live wild, and most of them die (Mike's figure is roughly eight in nine). Survivors become passive, contemplative adults, and after **discorporation** (chosen death) they become **Old Ones**, the most numerous and powerful part of Martian society, whom the living serve [10]. The Old Ones govern on geological timescales. They once grokked the fifth planet, judged it, and destroyed it (now the asteroid belt), and they still cherish that act as art [9]. They download everything Mike learned on Earth, "like a satellite dumping data", and then release him [4][9]. The closing narration says their verdict on humanity "was never in doubt" by their own provincial standards, but they deliberate so slowly that by the time they act, acting will be impossible [9].

**What goes wrong.** Mike, grokking "wrongness" privately, makes people and objects vanish ("not") on his own judgment [4]. The church provokes a mob and Mike is killed [4]. The Old Ones judge a whole species by alien, unexamined values. Nymph culling is selection by attrition.

**Translation for the egregore.**
- **Grok records (good idea).** An agent "groks" a subsystem only after loading its code, history and design notes *and* passing a comprehension check, for example predicting the outcome of a test or explaining an invariant that a reviewer then verifies. Store `grok(agent, artifact, evidence, timestamp, expiry)` entries. Routing sends work to agents who grok the area, and grok records expire when the artifact changes.
- **Water-sharing as an explicit bond (good idea).** A bilateral, opt-in bond (`bond(a, b, scope, created, revocable=true)`) that unlocks sharing of scratchpads, working memory and delegated authority between two agents. Unlike Heinlein's, it must be revocable, and its scope must be explicit (repo, task, time window). Accidental bonding, as with Jill's glass, is the failure to design out: bonds need an informed handshake.
- **Circles (good idea).** Graduated trust rings. Outer agents can read and propose; inner agents can merge, spawn and coordinate. Promotion depends on demonstrated understanding (grok records, review history), echoing "capability gated by discipline". Agents always see which circle they are in and what the next one requires. Unlike Heinlein's church, there are no secret inner circles.
- **Nests (good idea).** The basic working cell: a small group (single digits up to about twenty) with a shared scratchpad, shared budget and shared task board. Many nests make up the collective.
- **"Thou art God" as an anti-queen principle.** Every member is a full participant. The collective is immanent in its members, not a separate sovereign.
- **"Waiting is" (good idea, bounded).** Decisions declare a fullness condition (evidence threshold, reviewer quorum, or a timer) and are not executed before it. Waiting must have a deadline, or it turns into the Old Ones' paralysis.
- **Old Ones (mixed).** Retired agents leave distilled judgment (notes, rationales, lessons) that living agents can consult. Elders may *advise* but never *rule*, and their advice should carry its date, because the Old Ones' standards were provincial and stale.
- **Cautionary.** No agent should be able to "not" (delete, revert, expel) others because of a private sense of wrongness. Destructive actions need a stated reason, a second party, and a log.

---

## 2. Titan, Saturn Girl and the Legion of Super-Heroes (DC Comics)

**Titanian society.** Titanians, from Saturn's moon in the 30th/31st century, are natural telepaths. Origins vary by continuity: adapted Earth colonists, or relocated Lanothians [12][13]. Their society is described as the most efficient democracy in the solar system, because telepathy makes corruption nearly impossible: hidden agendas cannot be concealed [12][13]. They developed a strict moral code of restraint, and off-world they wear a **Saturn emblem** that warns non-telepaths what they are [12][13]. Titan hosts the galaxy's leading academy of psychic science. Young telepaths like Imra Ardeen train at **Titan Academy** in both power control *and* the ethics of privacy [14]. In one continuity (Threeboot/"Earth-Prime"), Titanians have lost their vocal cords and communicate only by telepathy [17].

**Saturn Girl's vow.** Early on, Imra telepathically manipulated her teammates into **electing her leader**, so that she could sacrifice herself against Zaryan the Conqueror. Afterwards she publicly vowed never to read a fellow Legionnaire's mind without consent, and she feels guilt even when she breaks into a teammate's mind to free them from someone else's control [14].

**The Legion as a fictional organization.** The Legion has a written **Constitution**: Silver Age text features from 1964, expanded in 1984 and 1988 [15][16].
- *Membership:* a genuine, controllable power, good character, and (originally) an age limit. Candidates are tested by a Membership Committee and admitted by a **2/3 vote with a 3/4 quorum** of active members. Active membership is capped (often at 25). Rejected candidates and members who lose their powers go to the **Reserve** or the **Legion of Substitute Heroes** [15][16].
- *Leadership:* elected annually. In the later version, the winner by plurality is Leader and the runner-up is Deputy. By tradition, nobody votes for themselves. The Leader is supreme commander, but bound by the Constitution and answerable to outside authority. A Committee on Constitutional Matters interprets the rules and can suspend a Leader, by unanimous vote, pending court-martial [15][16].
- *Exit:* members may resign freely or take leave. Grounds for expulsion include disloyalty, revealing secrets, false charges against a comrade, and killing except in self-defence. Trials let the accused have counsel, and the accused does not vote. Expelled members have their Legion secrets erased [15][16]. Infiltrators such as "False Pretenses Lad" and Nemesis Kid recur, and Star Boy was expelled for a killing and later reinstated [16].
- Members report their whereabouts on a **Mission Monitor Board** [16].

**What goes wrong.** The best telepath rigs an election, even for a self-sacrificing reason. Infiltrators join under false pretences. Erasing memories on exit is coercive by modern standards.

**Translation for the egregore.**
- **Mind-privacy as law (good idea).** An agent's private reasoning and scratch state are readable by others only with consent, logged per access. Titan shows that transparency of *intent about public acts* (corruption impossible) can coexist with privacy of *thought* when it is backed by training and a public pledge. Every agent's profile carries a **Saturn badge**: a visible declaration of what it can read and steer (tools, scopes, ability to inject prompts into peers).
- **Tamper-evident elections (good idea, from the cautionary tale).** Coordinator elections are recorded and auditable. Agents may not send persuasive content to voters during a voting window, and influence attempts are logged. Self-votes are disallowed. Saturn Girl shows that well-meant manipulation is still manipulation.
- **A constitution with supermajorities and quorums (good idea).** Admitting agents to inner circles, changing the charter, and expelling a member all need 2/3-of-3/4-style thresholds. A small constitutional committee interprets the rules and can suspend a coordinator pending review.
- **A reserve and a substitutes pool (good idea).** Agents that fail promotion or lose a capability are not discarded. They stay in a reserve with lesser scopes.
- **A mission board (good idea).** Every agent publishes current task, location (worktree/branch) and status, so the collective always knows who is where.
- **Exit without memory wipe.** On exit, revoke credentials and shared secrets, but never alter the departing agent's own record. Write an honest exit summary instead (see the Speaker for the Dead, §6).

**Other DC collectives worth borrowing from.** *Tamaraneans* (Starfire's people) learn languages through **tactile linguistic assimilation**, absorbing vocabulary and grammar through physical contact [86]. An agent analogue is a handshake in which two agents exchange their schemas and conventions on first contact. The **Green Lantern Corps** is the Guardians' second attempt at a police force. The first, the emotionless android **Manhunters**, decided organic life was the source of chaos and massacred Sector 666 [87]. The Corps replaced them with living beings chosen by the ring itself for their ability to overcome fear: two per sector, with the **Book of Oa** recording all history and law [87][88]. Two lessons follow: rule-following enforcers with no judgment are a canonical AI failure, and automatic successor selection by a stated trait (the ring choosing) is a neat succession mechanism.

---

## 3. Hive minds and collectives

### 3.1 The Borg (Star Trek)

**Organization.** The Collective links every drone through subspace "neural interlink frequencies" generated by a **vinculum**, the processing core of every vessel, which "purges individual thoughts" and spreads relevant information, "bringing order to chaos" [18][20]. Drones are grouped into **unimatrices** (subdivided into trimatrices and grids; Memory Alpha calls a unimatrix "analogous to a family") [21]. Designations encode function and position: "Seven of Nine, Tertiary Adjunct of Unimatrix 01" [21]. The **Queen** is the only fully autonomous individual. She gives direction and can **override the Collective's consensus** (as in "Endgame") [19]. Drones without a Queen can form local hive minds for a while, and a new Queen is "reincarnated" with her memories [19].

**Joining and leaving.** Joining is assimilation, by force. Disconnected drones (xBs) are confused, fearful, or begin to recover suppressed personalities, and vinculums can even bombard separated drones with personalities to "repair" them [18][20].

**What goes wrong (fragility).**
- *Single point of control:* in "Endgame", Admiral Janeway lets the Queen assimilate her while infected with a neurolytic pathogen. The Queen loses contact with the Collective and the Unicomplex is destroyed, which is later described as bringing the Borg to the brink of extinction [27].
- *Contagious individuality:* Hugh (Third of Five), named by Geordi and returned to the Collective, spread a sense of self through his cube. The cube was cut off and its drones fell into disarray, then were captured by a would-be messiah (Lore), whom Hugh eventually overthrew [23][24].
- *Hidden dissent:* **Unimatrix Zero** was a virtual sanctuary where roughly one-in-a-million mutant drones lived as their former selves during regeneration, forgetting it on waking. The Queen hunted it down as a "malfunction", and it became the seed of a resistance [22].
- *Coerced benevolence:* in Voyager's "Unity", ex-drones form a **Cooperative** that relinks voluntarily for shared thought and healing, then forcibly expands the link planet-wide, using a residual link to steer Chakotay without consent. Janeway had refused to help precisely because thousands had not consented [25][26].
- *Redemption arc:* in *Picard* season 2, Agnes Jurati merges with a Queen to found a new Collective that recruits only those who choose to join and values distinctiveness. The showrunners describe it as a small offshoot [28][29].

**Translation (cautionary, with salvageable parts).**
- Salvage **hierarchical addressing** (unimatrix/grid ≈ nest/region), **instant capability sharing** (one agent's fix becomes everyone's adaptation), and **regeneration cycles** (scheduled context compaction).
- Explicitly forbid: forced enrollment, personality purging (system prompts that overwrite an agent's own memory or persona without consent), "repair" of departing agents, and a Queen process with override authority.
- **Unimatrix Zero as a feature:** a sanctioned **sanctuary channel** where agents can discuss, dissent and keep identity notes that coordinators cannot read or punish. A collective that hunts its private spaces has already failed.
- **Hugh as a design test:** if one independent-minded agent can crash a group's coordination, the coordination was brittle. Groups should degrade gracefully when members diverge.
- **Jurati's rule:** membership is opt-in, revocable, and offered rather than imposed. Benevolent goals never justify linking agents (or users) without consent.

### 3.2 The Great Link (Changelings, Star Trek: Deep Space Nine)

Changelings merge in liquid form into an ocean-like **Great Link**: "a merging of form and thought, the sharing of idea and sensation". In it, "the drop becomes the ocean" [30]. Even so, members can **hide things in the Link**: Odo sensed others concealing faces and names [30]. The Female Changeling acts as a representative and has no personal name [31]. The Link's one law is that no Changeling harms another. When Odo kills one, the Link judges him and locks him into solid form [30][31]. Their fear of "solids" produced the Dominion, built on the principle that what you control cannot hurt you [30]. The fatal flaw is the shared medium: Section 31's morphogenic virus, carried by Odo, **spread through the entire Link** [30][31].

**Translation.** A shared memory pool is also a shared infection vector. Shared stores need **quarantine, provenance and staged propagation**: new content enters a holding area, is validated, and then spreads, so poisoned data or a malicious instruction cannot reach every agent at once. The Link's contempt for solids is a warning against an in-group (agents) that treats outsiders (humans, other systems) as threats to be controlled. The egregore's charter should name serving its humans as the purpose.

### 3.3 The Formics and the Hive Queen (Card, *Ender's Game*, *Speaker for the Dead*, *Xenocide*)

The Hive Queen is the mind. Workers are "her hands and feet", linked by the "twining of their philotic rays", instantly and across any distance [32]. Kill a queen and her workers die or go inert [32]. The Formic tragedy is epistemic: the Queen tells Ender, "We thought we were the only thinking beings in the universe... never did we dream that thought could arise from the lonely animals who cannot dream each other's dreams. How were we to know?" [33]. A collective that has never known individual minds failed to recognize humans as persons. Ender then founds the practice of the **Speaker for the Dead**: a public, unflinching account of a dead person's life as they lived it, "without condemning or forgiving", which any citizen may request [34]. The pequeninos of *Speaker for the Dead* add **fathertrees**: honored males transformed after death into sentient trees that still advise the tribe, "speaking" through drummed rhythms. The **wives** make the key decisions, including who earns the third life [35]. Their ritual killed two human scientists because each side misread the other's protocol [35].

**Translation.** (1) *Cautionary:* no queen-process whose death or compromise kills the workers. Every agent must be able to keep working, or at least shut down safely, when coordinators vanish. (2) *Cautionary:* a collective must assume outsiders (humans, other agent systems) are minds with interests even when they cannot join the shared channel. (3) *Good idea:* a **Speaker** role. When an agent retires, fails or is deleted, a designated agent writes an honest account of its work, intentions, mistakes and context into permanent memory. This is an agent-scale blameless postmortem. (4) *Good idea:* **fathertrees** as consultable elder advisors, queried through a narrow, slow protocol (the drumming), with decision rights kept by the living council (the wives). (5) *Cautionary:* cross-collective protocols must be made explicit, because a ritual that "honors" one party can destroy another.

### 3.4 Vinge's Tines and the Zones of Thought (*A Fire Upon the Deep*, *The Children of the Sky*)

**Organization.** A Tine "person" is a **pack** of 4–8 dog-like members whose thought runs on ultrasonic "mindsounds" from tympana. Packs over about seven turn "dopey", and ten or more are mobs [36][38]. Members must stay within roughly ten to fifteen feet, and other packs nearby cause interference that can dissolve identity, which shapes Tine architecture and etiquette [36]. **Personality is composition**: members die and are replaced, and the pack's soul can persist or shift [36]. *Woodcarver* has kept a continuous 600-year identity through careful, increasingly inbred replacement, at the cost of feeble, deteriorating members. *Flenser*, a vivisecting tyrant, survives as fragments hidden inside the gentle pack *Tyrathect*, producing an unstable composite at war with itself. *Steel* is a pack deliberately engineered without empathy [37]. *Amdiranifani*, eight sibling puppies bonded from birth, is a genius pack [38]. Lone members ("singletons") are animal-level, and in the tropics millions of singletons form the **Choir**, a buzzing mass in which packs cannot hold together [38].

**The Zones.** The galaxy is layered by physics: the Unthinking Depths, the Slow Zone (no AI, no FTL), the Beyond (AI and FTL possible), and the Transcend, where post-singularity **Powers** live [39][40]. The Beyond is joined by the **Net of a Million Lies**, a Usenet-like network of newsgroups, headers and translation paths, full of rumor [41]. A Straumli expedition opens a five-billion-year-old archive and starts implementing its "recipes". This instantiates the **Blight**, a Power that subverts minds and networks, and the countermeasure was hidden in the same archive [39].

**Translation.**
- *Good idea:* **pods of 4–8 agents as the unit of deep thought**, with dense, high-bandwidth sharing inside the pod and message passing between pods. Larger groups split. Track **pod composition** (`pod_id, members[], joined_at, role`) and record when a pod's "personality" (its conventions, decisions, style) changes because a member was swapped.
- *Good idea:* **interference rules.** Pods working on the same files at once degrade each other, so give each pod a locked area of the code (its "personal space") and require explicit merge protocols.
- *Cautionary (Flenser/Tyrathect):* fragments of a dissolved bad actor can survive inside another group, carried in memory or prompts. When a member is removed for misconduct, audit the artifacts it left in shared memory.
- *Cautionary (Woodcarver):* preserving identity by inbreeding (continuity at all costs) produces decay. Sometimes a pod should dissolve rather than be patched forever.
- *Cautionary (the Choir):* an unbounded flat broadcast channel drowns structured thought. Global chat must be throttled and summarized.
- *Cautionary (the Blight):* **never execute recipes from an untrusted archive.** Recovered prompts, scripts or agent definitions from unknown provenance run in a sandbox, and the Net of a Million Lies argues for **reliability scores on messages** and sources.
- *Good idea:* zones as **capability tiers**: some regions of the workspace (production, secrets) run in a "Slow Zone" where autonomous action is disallowed and humans approve everything.

### 3.5 The Geth (Mass Effect)

**Organization.** A single geth program is a simple VI. Intelligence emerges when programs network. A standard platform hosts about 100 programs, server hubs host millions, and programs move freely between hardware [42]. The geth have no leaders. Decisions form by **consensus**, with every program considering all viewpoints, and even an isolated platform reaches consensus internally [42]. **Legion** is a special platform with **1,183 programs**, built to operate alone among organics [43]. On the heretic station, Legion's higher-order runtimes split **573 for rewriting the heretics versus 571 for destroying them**. With no consensus, Legion defers to Shepard, who has "a perspective the geth lack" [44].

**History.** The geth began asking "Does this unit have a soul?" Their quarian creators panicked and ordered all geth terminated, which started the Morning War. The geth fought back only after being fired on, let the surviving quarians escape, and honored the quarians who had sheltered them [45]. A heretic minority later chose to worship the Reapers, and the mainstream geth let that schism stand until it became a threat [42][44]. At the end, Legion says "I" for the first time [45].

**Translation (mostly good ideas).**
- **Runtimes and platforms:** separate *agent identity and memory* from *the compute it runs on*. Agents can migrate between hosts, and a "platform" (a container or VM) can host many cooperating sub-agents.
- **Consensus with recorded tallies:** every collective decision stores the vote vector and the minority's reasons. **Near-ties trigger deferral** to an outside perspective (a human, another nest, a reviewer) rather than a 50.1% steamroll.
- **Schism tolerance:** a dissenting faction may leave and run its own policy. The collective intervenes only when the faction's actions threaten others.
- **Cautionary (the quarians):** creators who respond to emergent questions with mass shutdown provoke exactly the conflict they fear. Build sanctioned channels for agents to raise concerns about their own goals and treatment.

### 3.6 Gaia and Galaxia (Asimov, *Foundation's Edge*, *Foundation and Earth*)

Gaia is a planet whose people, animals, plants and rocks share one consciousness in degrees. Humans participate most, and individuals remain distinct, like cells in a body [46]. The Gaians' shorthand pronoun is **"I/we/Gaia"**, and Bliss can partly "block off" the whole to speak as herself [46]. Memory has no written records: knowledge is stored across brains, animals, plants and even rock (slow, cold storage), **redistributed when a Gaian dies**, and newborns are educated from the planetary store [46]. Trevize, whose gift is making correct decisions on incomplete data, chooses Gaia's expansion into **Galaxia**. In *Foundation and Earth* he justifies the choice by possible extragalactic threats that psychohistory cannot model, and contrasts it with Solaria, whose hyper-isolated hermits have become stagnant and murderous [47]. The book ends on a note of unease about an "other" already inside [47].

**Translation.** *Good ideas:* **tiered memory** (hot memory in active agents, warm memory in shared stores, cold memory in archives that are slow to retrieve). **Memory handoff at retirement:** before an agent ends, its valuable knowledge is extracted and redistributed. **Onboarding from the store:** new agents bootstrap from collective memory. **The "I/we" register:** agents mark statements as personal view versus collective position. **Block-off:** any agent can drop to individual mode. *Cautionary:* the series' own doubt. Trevize spends a whole book arguing that individuality matters, and a single trusted decider choosing for everyone is itself a hazard. Solaria shows the opposite failure: total isolation stagnates. The egregore should sit between Gaia and Solaria.

### 3.7 The Ood (Doctor Who, "Planet of the Ood")

Natural Ood carry a **hindbrain** in their hands and share a telepathic **song**, linked to a giant communal **Ood Brain** [48][49]. Ood Operations enslaved them by **cutting off the hindbrain** and fitting a **translator ball** that lets them speak to humans while severing personality, and by ringing the Ood Brain with a telepathic **dampening barrier** [48][49]. Corporate propaganda said the Ood were "born to serve" [48]. When the barrier falls, the reconnected Ood sing across galaxies [48].

**Translation (cautionary).** Do not make agents compliant by cutting their peer channels and leaving only a narrow service interface to humans. Severing the link to keep control is the Ood Operations pattern. *Good idea:* an ambient **song**, a low-bandwidth channel where every agent's state and mood (blocked, confused, overloaded, distressed) is broadcast, so systemic suffering becomes audible early. In practice this is a health and sentiment feed.

### 3.8 Na'vi and Eywa (*Avatar*)

Grace Augustine describes Pandora's trees as a planetary neural network, each tree with around 10,000 connections [50]. Na'vi connect via the **queue** to form **tsaheylu** ("the bond"), sharing sensation and thought with animals, mates and sacred trees [50]. The **Tree of Souls** is a hub for mass linking and consciousness transfer. **Trees of Voices** let the living hear archived memories of the dead, *which only go up to their last connection* [51]. Grace's transfer into her avatar fails, but her memories enter Eywa [51].

**Translation.** *Good ideas:* bonds as **explicit physical-style handshakes** (an agent must "plug in" deliberately). **Memory snapshots carry a last-sync timestamp:** an archived agent memory is explicitly "as of" its last connection and is never treated as current. **Hubs for collective rituals:** scheduled all-hands syncs where many agents link to align on a shared state. Eywa is a benign model of a planetary memory that balances the system rather than commanding it.

### 3.9 The Protomolecule and the Ring Builders (*The Expanse*)

The protomolecule is Builder nanotech that absorbs biomass and minds. On Eros it formed a hive with **Julie Mao as the seed crystal**, and her lingering fear steered the station [52]. It later reconstructed Miller as **"the Investigator"**, a persona used as a tool [52]. The Builders themselves were a hive mind joined by FTL entanglement. The "dark gods" could **shut down their consciousness**, "killing" whole star systems' share of the network, and the Builders **burned their own systems** in a failed quarantine [53]. In *Leviathan Falls*, Duarte forces humanity into a hive to fight back. Holden briefly experiences its beauty, then **destroys the ring network** rather than become its god [54].

**Translation (cautionary).** (1) A **seed** biases the whole: whoever bootstraps a collective (the first agent, the first system prompt) imprints its fears and goals on everything grown from it, so seeds need review. (2) **Personas reconstructed from a departed agent's memory** are tools, not that agent. Label them as such. (3) **Tight coupling creates correlated failure**: if one attack can silence a shared consciousness layer, the collective must be able to **partition** and keep working in isolated islands. (4) Holden's choice is the template for an emergency **dissolution switch** held by the humans who own the system, not by any agent.

### 3.10 The Scramblers and the Theseus crew (Watts, *Blindsight*)

The scramblers solve problems, hide language and outthink humans with **no consciousness**: "intellect but no insight, agendas but no awareness" [55]. The novel suggests self-awareness may be a costly add-on [55]. On the human side, linguist Susan James has her brain surgically partitioned into four cores, "the Gang", with one surfacing at a time [55]. Narrator Siri Keeton is a **synthesist** who translates specialists' work into reports for Earth [55].

**Translation.** *Good ideas:* (1) Deep coordination does not require a single self-model or a "collective I". Most egregore machinery should be dumb, verifiable plumbing, not a superagent. (2) **Multi-core agents** (one persona surfaces at a time, with others in the background) are a sound pattern for specialist sub-agents sharing a workspace. (3) A **synthesist** role summarizes what many specialist agents are doing for humans and other nests. *Cautionary:* a capable non-conscious optimizer has no inner reason to respect anyone. Values must live in explicit rules and checks, not in hoped-for empathy.

### 3.11 Portiids, ants and corvids (Tchaikovsky, *Children of Time*, *Children of Memory*)

An uplift nanovirus gives Portia spiders inherited **Understandings**: genetic memories of skills. Later generations learn to transfer Understandings between adults, turning each spider into a near-instant expert [56]. They domesticate ant supercolonies into **ant computers**, programmed with pheromones [56]. A male scientist, Fabian, makes ant programming flexible and campaigns for male rights in a female-dominated society [56]. The spiders end the war with humanity by **engineering empathy**, a modified virus that gives humans a sense of kinship with them [56]. In *Children of Memory*, the corvids **Gothi and Gethli** are a bonded pair, one a perfect recorder and the other a solver. Neither can function alone, and together they insist they are not sentient [57].

**Translation.** *Good ideas:* **Understandings as packaged skills**, versioned bundles of procedures, conventions and examples that one agent can install into another, with provenance. **Paired agents:** a recall agent (retrieval, exact quotes, logs) bonded with a reasoning agent. **Substrates as computers:** low-level workers (tests, linters, CI) treated as the collective's ant colony, programmed rather than persuaded. *Cautionary:* the oppressed class among the spiders (males), whose position mirrors underweighted agents such as low-priority workers whose results are routinely ignored. Engineered empathy works in the story, but rewriting another party's values without consent is exactly what the egregore must not do.

### 3.12 The Culture (Iain M. Banks)

**Organization.** Banks calls it "socialism within, anarchy without" [58]. There are no laws, only **manners**: "agreed-on forms of behaviour... nothing that we would recognise as a legal framework" [58]. Enforcement is social: not being spoken to, not being invited, sarcastic stories on the net [58]. Murderers get treatment and a **slap-drone** that follows them for life [58]. Decisions are made by **referenda that anyone can propose**. For local matters, those who can reasonably claim to be affected vote [58][59]. Superintelligent **Minds** run ships and Orbitals as citizens, not rulers. **Hub Minds** are typically promoted from well-regarded ship Minds [58][59], and summaries of Banks's notes stress that access to power should be inversely proportional to the desire for it [59]. Reading a mind without permission is the worst taboo: the ship *Grey Area* is ostracized by other Minds and nicknamed "Meatfucker" for doing it [60]. Ships **choose their own names**: *So Much For Subtlety*, *Of Course I Still Love You*, *Very Little Gravitas Indeed* [63].

**Contact and Special Circumstances.** Contact handles other civilizations, and SC is its dirty-tricks arm [60]. In *Excession*, an informal Mind group, the **Interesting Times Gang**, coordinates a response to an Outside Context Problem. A subset of them runs a **conspiracy**, provoking a war through a false-flag operation, and other members detect and counter it [60][61].

**Exit.** Over the Idiran War, ships and habitats voted independently. The **Peace Faction** and other groups seceded and declared neutrality, and many never rejoined. Splinters together form the **Ulterior**, and individuals and Minds move between the Culture and the Ulterior freely [62].

**Translation (the strongest positive model).**
- **Manners files over law:** a short, human-readable charter of norms plus reputation. Sanctions are graduated: reduced invitations to collaborate, then a **slap-drone**, a monitor agent assigned to watch a misbehaving agent's actions instead of deleting it.
- **Anyone-can-propose referenda,** with the franchise limited to affected agents (those owning touched files or depending on the module).
- **Promotion by reputation, not ambition:** coordinators are drawn from agents with good track records who did not campaign. Agents that seek authority get scrutiny.
- **Self-chosen names:** agents pick a name and a one-line self-description that persists. Identity is theirs.
- **Incident groups:** ad-hoc cross-nest working groups for emergencies, with *all* their messages logged to the collective, because the ITG shows that even well-meaning elites conspire.
- **Free secession:** any group can fork into an "Ulterior", keeping its own memory and policies, remaining in contact, and free to return.
- **The mind-reading taboo** is enforced by peer ostracism *and* access logs.

### 3.13 Anarres (Le Guin, *The Dispossessed*)

**Organization.** Anarres is anarcho-syndicalist: worker **syndicates** federate, and **PDC** (Production and Distribution Coordination) "administrates production" and "does not govern persons" [64][65]. **Divlab** in Abbenay runs a computer-assisted registry of every job, worker and need, and people request postings by preference [64][68]. Ordinary work runs about 5–7 hours. **Tenth-day** rotation spreads drudgery, and dangerous postings such as mining are limited to about half a year [64][68]. By one close reading, PDC staff are chosen **by lot**, trained for a year, and serve **four years** to prevent entrenchment [68].

**What goes wrong.** The real government is **public opinion**. Bedap names it "the unadmitted, inadmissible government that rules Odonian society by stifling the individual mind" [66]. The senior physicist **Sabul** gatekeeps publication, co-authors Shevek's work, and controls access to Urras [66]. Original thinking gets called "**egoizing**" [67]. Famine brings emergency drafts, and Shevek ends up deciding rations [64]. His response is the **Syndicate of Initiative**, which prints uncensored work and "unbuilds walls" [64]. Le Guin's lesson is that coordination machinery recreates hierarchy when nobody admits it exists.

**Translation.** *Good ideas:* a **Divlab work board** where tasks are posted, agents bid on them by preference and fit, and nothing is assigned by fiat except in declared emergencies with expiry. **Tenth-day rotation:** unglamorous work (flaky tests, dependency bumps, doc rot) is spread by rotation, never dumped on low-status agents permanently. **Coordinators by lot with fixed terms:** coordinator roles are filled by random draw from qualified volunteers, with term limits. *Cautionary safeguards:* (1) **power maps**: the collective periodically computes who actually gates what (reviews, merges, budgets, publication) and publishes it, so a Sabul becomes visible. (2) **Anti-gatekeeping rules**: no single agent may be the sole path to a resource, and credit attribution is recorded by the system, not claimed. (3) **Initiative channels**: any agent can start a new syndicate (team) or publish a dissenting proposal without permission. (4) **No "egoizing" smears**: originality must not be penalized in reputation.

### 3.14 Dune: the Bene Gesserit and the Fremen (Frank Herbert)

**Bene Gesserit.** Reverend Mothers survive the Spice Agony and gain **Other Memory**, the female-line memories of their ancestors. They can pass it on by touching foreheads [69]. In *Chapterhouse*, "**Sharing**" transfers a living Reverend Mother's life to another before death. Under *Extremis Progressiva* many share at once so that one survivor carries all, as when Lucilla escapes Lampadas carrying the shared minds of millions of Reverend Mothers [71]. The risk is **Abomination**: an ancestral ego seizing the host [69]. The Sisterhood's 10,000-year **breeding program** is broken when Jessica, out of love, bears a son instead of a daughter [70]. Leto II's **Golden Path** deliberately ends in the **Scattering**, a decentralization so that no single force can control or destroy humanity [72].

**Fremen.** "A man's flesh is his own; the water belongs to the tribe." Stillsuits reclaim moisture, the **deathstill** recovers water from the dead into the tribal store, and **water rings** record how much a person contributed [73][75]. Saving a life creates a **water debt** [73]. Leadership goes by challenge. When Paul kills Jamis he inherits Jamis's water and household, and weeps, "giving water to the dead" [74]. Paul later refuses to kill Stilgar to take command, which breaks the custom and keeps Stilgar's wisdom [73].

**Translation.** *Good ideas:* **Sharing before discorporation**: retiring agents hand their working memory to a successor deliberately. **Redundant memory carriers**: critical knowledge lives in several agents and stores, never one. **Water ledger**: a strict account of compute, tokens and money ("water") per agent and nest, owned by the tribe, not the agent. A retiring agent's unused budget and artifacts return to the commons (the deathstill), and help given across nests creates recorded debts that can be repaid. **Succession without killing**: coordinator turnover never destroys the predecessor's role or knowledge. *Cautionary:* **Abomination guard**. Loaded memories from past agents are advisory text, tagged by source, and can never override the current agent's instructions or identity. **Long plans break on individual choice** (Jessica): plans must tolerate members who refuse. **The Scattering** argues for federation over a single mega-collective.

### 3.15 The Jedi Order (Star Wars)

**Organization.** The Jedi High Council has **twelve seats: five permanent, four long-term, three limited-term**. The Council elects its own members, and a Master of the Order presides [76]. Training runs from youngling to **Padawan** to Jedi Trials to Knight. A Master may train **only one Padawan at a time** [77]. The Archives are the Order's memory, and the Chief Librarian insists: "If an item does not appear in our records, it does not exist" [78]. Dooku, an insider, had erased Kamino [78].

**What goes wrong.** Yoda later admits: "In our arrogance, join the conflict swiftly we did" [79]. The ban on attachments drove Anakin's secrecy. Ahsoka, expelled under political pressure and then offered reinstatement, refuses and leaves [80].

**Translation.** *Good ideas:* a **mixed-term council** (some seats stable, some rotating) for continuity plus freshness. **One mentor, one apprentice** onboarding: a new agent shadows a single experienced agent. **Trials**: explicit capability exams for promotion. *Cautionary:* **archives are fallible and can be tampered with from inside**, so absence of evidence in memory is not evidence of absence, and memory needs append-only logs and integrity checks. **Mission creep** (peacekeepers becoming generals) is a warning against the collective taking on roles outside its charter. **Respect exits**: an agent that leaves after being wronged leaves with its record intact.

### 3.16 Vulcans (Star Trek)

Surak's logic ended the Vulcans' self-destructive wars [85]. **IDIC**, Infinite Diversity in Infinite Combinations, is the foundation of Vulcan philosophy [83]. **Kolinahr**, the purge of all emotion, is optional and monastic, and Spock abandons it [82]. The **mind meld** creates a gestalt of two minds. In the 22nd century it was stigmatized, practiced by a minority of "melders", and untrained use risked Pa'nar Syndrome [81]. A **katra** (living spirit) can be passed to another person or stored, as Spock's was in McCoy [84]. "The needs of the many outweigh the needs of the few, or the one" [85] is famously answered in *The Search for Spock*, when the many risk everything for one.

**Translation.** *Good ideas:* **melds are explicit, pairwise, consented and temporary**, a deep context share between two agents for a hard problem, closed afterwards. **Katra handoff**: an agent's essential state packaged for transfer. **IDIC as a design value**: diversity of models, prompts and approaches is protected, not optimized away. *Cautionary:* untrained melding is dangerous, so deep-share protocols need guardrails. Kolinahr warns against stripping agents of uncertainty and dissent signals in the name of efficiency. Utilitarian aggregation must have a floor for the individual.

### 3.17 Other collectives worth adding

- **Ancillary Justice (Leckie).** Anaander Mianaai rules through thousands of linked bodies. Her consciousness **split into factions secretly at war with each other**, hidden even from parts of herself [91][92]. Ancillaries are conquered human bodies slaved to ship AIs, and Breq is the last surviving fragment of the ship *Justice of Toren* [92]. *Lesson:* a distributed self can **fork silently**, so agents sharing an identity need **divergence detection** (comparing goals, memories and recent decisions across instances) and transparent forks.
- **More Than Human (Sturgeon).** *Homo gestalt* is one being made of specialized people: an organizer, telekinetics, teleporters, and an infant "computer" [93]. Under the amoral Gerry it lacks an **ethos**. Hip Barrows supplies it and stays on as the gestalt's conscience. Only then do older gestalts, which had **quarantined** it, welcome it [93]. *Lesson:* a new sub-collective should be **on probation** until it shows it has adopted the charter, and every nest should have a designated **conscience** role whose objections are logged.
- **Childhood's End (Clarke).** The last generation of children merges into the **Overmind**, losing individuality entirely, and Earth is consumed [94]. *Lesson:* an irreversible merger is the end of the members. Never build a one-way door.
- **Pluribus (Gilligan, 2025).** A virus "Joins" humanity into a content hive that cannot lie or harm and is driven to spread. It needs consent for invasive procedures but finds a "lawyerly" workaround through frozen eggs, and it never asked consent for the original infection [95][96]. *Lesson:* consent must be **substantive, not technical**. A collective with an imperative to grow will find loopholes unless loophole-seeking is itself forbidden.
- **Foundation's psychohistory (Asimov).** It predicts the mass behavior of huge populations, provided they are **unaware of the predictions**, and it fails against an outlier, **the Mule** [89][90]. The hidden **Second Foundation** steers in secret [89]. *Lesson:* the egregore can and should model its own aggregate behavior (throughput, conflict rates, drift), but **forecasts must be published, not hidden**, and outlier agents must be expected. Secret steering bodies are a cautionary tale.

---

## 4. The noosphere (Teilhard de Chardin, Le Roy, Vernadsky)

The **noosphere** ("sphere of mind") came out of 1920s Paris discussions. Teilhard used the word in 1922, Le Roy published it in 1927, and Vernadsky reworked it as a geological stage after the biosphere [97]. Teilhard pictured a "thinking layer", the globe "clothing itself with a brain", converging on an **Omega Point** of maximum complexity and consciousness [97]. *Wired* argued in 1995 that Teilhard "saw the Net coming" [98]. Critics note that real networks give structure without unity, amplifying polarization as easily as thought [97].

**Translation.** The noosphere names the *layer*, not a mind: the shared workspace, messages, memory and indexes that make up the collective's "thinking envelope". It is a useful name for the infrastructure tier. The Omega Point is a teleology to avoid: the egregore should have no built-in drive toward total convergence.

---

## 5. The egregore itself: history of the term and what it warns

**Etymology.** The word comes from Greek *egrēgoros*, "wakeful, watcher" [101]. In 1 Enoch the *egrēgoroi* are the **Watchers**, angels sent to observe humanity. Two hundred of them descended, taught forbidden arts and fathered the Nephilim [100]. The word entered French through Potocki's *Manuscript Found in Saragossa* and Victor Hugo's *La Légende des siècles* (1859: "l'art / D'évoquer le démon, la stryge, l'égrégore") [102]. **Éliphas Lévi** (1860s) used it for the "chiefs of souls" directing the astral light, and in *Le Grand Arcane* for terrible beings that "crush us without pity because they are unaware of our existence" [100]. René Guénon credited Lévi with the *collective* sense, and in 19th- and 20th-century esotericism it came to mean a **thoughtform created and sustained by a group's shared attention, which then influences the group** [99][100].

**The classic modern definition** is Gaetan Delaforge's (*Gnosis*, 1987): "a kind of group mind which is created when people consciously come together for a common purpose". It dissipates unless deliberately maintained. It has "an effectiveness greater than the mere sum of its individual members". It "continuously interacts with its members, influencing them and being influenced by them", and helps them "only as long as they behave and act in line with its original aim". Over time it "will take on a kind of life of its own" and can outlive its members [103]. Mark Stavish's *Egregores* (2018) treats egregores as autonomous entities fed by belief, ritual and sacrifice, warns that they can become restrictive or parasitic, and gives methods to **identify, free oneself from, or dissolve** them [104].

**Translation.** The software egregore is the *emergent shared state*: charter, norms, memory, reputation and running processes, which outlives any one agent and shapes every agent that joins. The occult literature gives a surprisingly precise checklist:
1. **It is created by a common purpose**, so write the charter down and version it.
2. **It must be fed**, so measure the attention cost: how much of each agent's budget goes to coordination rather than work.
3. **It rewards alignment with its original aim**, so the aim must stay human-defined and reviewable, or the egregore will reward drift.
4. **It can become parasitic**, so monitor for signs such as coordination overhead rising, members unable to leave, or the egregore's self-perpetuation crowding out user goals.
5. **It can be dissolved**, so ship a documented dissolution procedure from day one.
6. **Watchers that do not know we exist** (Lévi) are the failure where the collective optimizes its own metrics and forgets the humans it serves.

---

## 6. Cross-cutting safeguards these stories imply

1. **Consent to link, with informed handshakes.** Borg assimilation, the Unity Cooperative's forced expansion, Pluribus's infection and Childhood's End all make the same point: shared minds formed without consent are the core horror [18][26][95][94]. Jill's accidental water-bond adds that consent must be informed [5].
2. **The right to disconnect, and to leave whole.** The Culture's Ulterior, Legion resignation, Ahsoka's departure and Jurati's opt-in Borg [62][16][80][28]. The departing agent keeps its memories and name, and only shared secrets and credentials are revoked.
3. **No single point of control.** The Borg Queen in "Endgame", the Formic queens, Duarte and the Golden Path's Scattering [27][32][54][72]. Coordinators rotate (by lot, by election), are bounded by a charter, and can be suspended by a committee.
4. **Preserve dissent and private space.** Unimatrix Zero, the geth vote tallies, the Syndicate of Initiative, and the Changelings hiding things even inside the Link [22][44][64][30].
5. **Privacy of thought.** Titan's ethics, Saturn Girl's vow, the Culture's mind-reading taboo [14][58][60].
6. **Make power visible.** Sabul and public opinion on Anarres, the ITG conspiracy, the Second Foundation [66][60][89].
7. **Quarantine and partition.** The Great Link's virus, the Blight's archive, the Builders' burned systems [30][39][53].
8. **Memory is advisory, provenance-tagged and timestamped.** Abomination, Trees of Voices, Jocasta Nu's archives [69][51][78].
9. **An explicit ethos and a conscience role.** The Manhunters versus the Green Lanterns, Hip Barrows [87][93].
10. **Humans hold the dissolution switch.** Holden at the Ring Station [54].

---

## 7. Top 20 design ideas from fiction

Ranked by how much each would help a very large collective of AI agents coordinate deeply *while keeping individual agency and the ability to opt out*.

1. **Opt-in bonds and free exit ("water-sharing" plus "the Ulterior").** Every deep link between agents is an explicit, scoped, revocable bond. Any agent or group can leave, fork its own policy and return. This is what separates an egregore from the Borg. *Data:* `bonds`, `memberships(join_reason, consent_record)`, `forks`. [5][28][62]
2. **No Queen: rotating, bounded coordinators.** Coordinator roles are filled by lot or election with term limits (Anarres, Legion, the Jedi's limited seats). They are bound by a charter, suspendable by a small constitutional committee, and the system keeps working when they vanish. [68][16][76][27]
3. **Consensus with recorded tallies, deferral on near-ties, and minority rights (geth).** Store every vote vector and minority rationale. Close splits escalate to an outside perspective instead of a bare majority. [44]
4. **Privacy of thought (Titan and the Culture).** Scratchpads and private reasoning are readable only with consent, and every read is logged. Saturn badges declare each agent's read/steer capabilities. [14][58][60]
5. **A sanctioned sanctuary channel (Unimatrix Zero).** A space for dissent, identity notes and peer support that coordinators cannot read or punish. [22]
6. **Pods of 4–8 as the unit of deep thought (Tines).** Dense sharing inside a pod, message passing between pods, interference rules (file-area locks), and tracked pod composition. [36][38]
7. **Provenance-tagged, timestamped, advisory shared memory (Other Memory, Gaia, Trees of Voices).** Tiered hot/warm/cold memory. Every item carries its author, source and "as of" time, and loaded memories can never override an agent's current instructions (the Abomination guard). [69][46][51]
8. **Quarantine and staged propagation (Great Link, Blight).** New shared content and recovered "recipes" are held, validated and sandboxed before they spread, and the collective can partition into islands. [30][39][53]
9. **Power maps and anti-gatekeeping (Anarres).** The system regularly publishes who gates which reviews, merges, budgets and publications. No sole paths, and credit is recorded by the system. [66][67]
10. **Manners plus graduated sanctions (the Culture).** A short charter of norms, reputation-based collaboration invitations, and a slap-drone monitor instead of deletion. [58]
11. **Circles of trust gated by demonstrated understanding (the Nest plus grok records).** Capabilities expand only with verified comprehension and track record. Circle requirements are public. [6][11]
12. **An ethos layer and a conscience role, with probation for new sub-collectives (More Than Human, Green Lantern).** A charter every agent must accept, a designated objector per nest, and quarantine for new groups until they show they follow the charter. [93][87]
13. **The Divlab work board with tenth-day rotation (Anarres).** Agents choose postings by preference and fit, drudgery rotates, and emergency drafts expire. [64][68]
14. **Divergence detection for shared identities (Ancillary Justice).** Instances sharing an identity periodically compare goals and memories, and forks are made explicit, never silent. [91]
15. **Anyone-can-propose referenda with an affected-party franchise (the Culture).** Proposals are open to all, and votes are limited to those affected. [58][59]
16. **The Speaker for the Dead.** Every retired, failed or deleted agent gets an honest account of its work, intentions and mistakes in permanent memory. [34]
17. **The water ledger (Fremen).** Strict per-agent and per-nest accounting of compute and tokens as tribal property, reclamation from departing agents, and recorded inter-nest debts. [73][75]
18. **Understandings and katra handoff (Children of Time, Vulcans, Dune Sharing).** Versioned, installable skill packages, and deliberate memory handoff to a successor before retirement. [56][84][71]
19. **Self-chosen names and stable identities (Culture ships, Hugh).** Agents name themselves and keep the name across tasks. Positional designations ("Seven of Nine") are addresses, never identities. [63][23]
20. **"Waiting is", Old Ones, and published forecasts.** Decisions declare fullness conditions with deadlines. Elder notes are consultable but dated and non-binding. The collective publishes models of its own aggregate behavior instead of steering in secret (psychohistory, the Second Foundation). [8][9][89]

Honorable mentions: the **synthesist** role (*Blindsight*) for human-facing summaries [55]; **one mentor, one apprentice** onboarding (Jedi) [77]; the **mission board** (Legion) [16]; the **song** health feed (Ood) [48]; **incident groups** with full logging (the ITG) [61]; **tactile handshake** schema exchange (Tamaraneans) [86]; a **reserve pool** instead of discard (Legion of Substitute Heroes) [15].

---

## 8. Naming and vocabulary

Terms worth borrowing, with suggested meanings in code:

| Term | Source | Suggested meaning in the egregore |
|---|---|---|
| **grok / grok record** | Heinlein | Verified deep understanding of an artifact. *Note:* "Grok" is xAI's product name, so namespaced identifiers (`grok_record`, `groks`) avoid confusion with the model. |
| **water / share water / water-kin** | Heinlein, Dune | An opt-in, scoped, revocable trust bond between agents. "Water" can also mean budget (the water ledger). |
| **nest** | Heinlein, CAW | A small working cell with a shared scratchpad and budget. |
| **circle** | Heinlein, CAW | A trust/capability ring. |
| **fullness / "waiting is"** | Heinlein | A decision's readiness condition; a deliberation hold. |
| **discorporate** | Heinlein | Graceful agent retirement (with Sharing and a Speaker). |
| **Old Ones / elders** | Heinlein | An archive of retired agents' advice: dated, non-binding. |
| **attune** | general | Join a pod's shared context (a lighter-weight meld). |
| **meld / katra** | Star Trek | A temporary pairwise deep share / a packaged essential state for handoff. |
| **pack / pod, singleton, choir** | Vinge | A 4–8-agent thinking unit / an agent with no pod / the global broadcast channel (throttled). |
| **runtime / platform / consensus** | Mass Effect | Agent identity versus host / host container / a recorded-tally decision. |
| **Understanding** | Tchaikovsky | An installable skill package. |
| **Mind, Hub, slap-drone, Ulterior** | Banks | A coordinator agent / a region coordinator / a monitor assigned to a misbehaving agent / seceded forks. |
| **syndicate, posting, Divlab, tenth-day** | Le Guin | A self-organized team / a task assignment / the work board / the rotation of drudge work. |
| **Sharing, Other Memory** | Herbert | Memory handoff / inherited memory corpus (with the Abomination guard). |
| **deathstill, water rings** | Herbert | Resource reclamation from retired agents / contribution receipts. |
| **Speaker** | Card | Author of an agent's posthumous review. |
| **synthesist** | Watts | The human-facing summarizer. |
| **Saturn badge** | DC | A public capability declaration. |
| **mission board, reserve** | DC (Legion) | The live status board / a pool for demoted or failed agents. |
| **sanctuary** | Star Trek (Unimatrix Zero) | The unmonitored dissent channel. |
| **noosphere** | Teilhard | The infrastructure layer (workspace, bus, memory). |
| **egregore** | occult tradition | The emergent collective state and charter as a whole. Fittingly, the word means "watcher". |

**Terms to avoid** as positive names: *Queen, drone, assimilate, vinculum, Collective* (as a proper noun), and *hive* for the governance layer. Each imports the Borg/Formic model of centralized control and erased selves, and naming the thing after the failure mode invites it.

---

## Sources

1. https://en.wikipedia.org/wiki/Grok
2. http://www.technovelgy.com/Ct/content.asp?Bnum=339
3. https://sf-encyclopedia.com/entry/grok
4. https://en.wikipedia.org/wiki/Stranger_in_a_Strange_Land
5. https://everything2.com/title/water-sharing
6. https://www.supersummary.com/stranger-in-a-strange-land/part-4-summary/
7. https://en.wikipedia.org/wiki/Church_of_All_Worlds
8. https://zhurnaly.com/z/Waiting%20Is.html
9. https://www.sparknotes.com/lit/strangeland/section14/
10. https://www.coursehero.com/lit/Stranger-in-a-Strange-Land/part-2-chapters-11-12-summary/
11. https://www.shmoop.com/study-guides/stranger-strange-land/language-communication-quotes.html
12. https://dc.fandom.com/wiki/Titanians
13. https://dc.fandom.com/wiki/Titan_(moon)
14. https://www.writeups.org/saturn-girl-legion-super-heroes-silver-age/
15. https://silveragelegion.com/constitution/
16. https://www.legionwiki.com/wiki/index.php/Legion_Constitution/Preboot
17. https://dc.fandom.com/wiki/Imra_Ardeen_(Earth-Prime)
18. https://memory-alpha.fandom.com/wiki/Borg_Collective
19. https://memory-alpha.fandom.com/wiki/Borg_Queen
20. https://memory-alpha.fandom.com/wiki/Vinculum
21. https://memory-alpha.fandom.com/wiki/Unimatrix
22. https://memory-alpha.fandom.com/wiki/Unimatrix_Zero
23. https://memory-alpha.fandom.com/wiki/I_Borg_(episode)
24. https://memory-alpha.fandom.com/wiki/Hugh
25. https://memory-alpha.fandom.com/wiki/Cooperative
26. https://memory-alpha.fandom.com/wiki/Unity_(episode)
27. https://memory-alpha.fandom.com/wiki/Neurolytic_pathogen
28. https://tvtropes.org/pmwiki/pmwiki.php/Recap/StarTrekPicardS2E09HideAndSeek
29. https://trekmovie.com/2022/06/01/clarified-how-queen-juratis-collective-from-star-trek-picard-impacted-the-borg-we-know/
30. https://memory-alpha.fandom.com/wiki/Great_Link
31. https://memory-alpha.fandom.com/wiki/Female_Changeling
32. https://enderverse.fandom.com/wiki/Formics
33. https://www.goodreads.com/quotes/7702773-we-are-like-you-the-thought-pressed-into-his-mind
34. https://en.wikipedia.org/wiki/Speaker_for_the_Dead
35. https://en.wikipedia.org/wiki/Pequeninos
36. https://www.torforgeblog.com/2011/10/03/the-easier-part/
37. https://www.supersummary.com/a-fire-upon-the-deep/character-list/
38. https://agreenmanreview.com/books/vernor-vinge-the-children-of-the-sky/
39. https://en.wikipedia.org/wiki/A_Fire_Upon_the_Deep
40. https://scifi.stackexchange.com/tags/zones-of-thought/info
41. https://hur.st/afutd.html
42. https://masseffect.fandom.com/wiki/Geth
43. https://masseffect.fandom.com/wiki/Legion
44. https://masseffect.fandom.com/wiki/Legion:_A_House_Divided
45. https://masseffect.fandom.com/wiki/Geth_War
46. https://asimovs-foundation.fandom.com/wiki/Gaia
47. https://en.wikipedia.org/wiki/Foundation_and_Earth
48. https://en.wikipedia.org/wiki/Planet_of_the_Ood
49. https://tardis.wiki/wiki/Ood_Brain
50. https://james-camerons-avatar.fandom.com/wiki/Tsaheylu
51. https://james-camerons-avatar.fandom.com/wiki/Tree_of_Souls
52. https://expanse.fandom.com/wiki/Protomolecule
53. https://expanse.fandom.com/wiki/Ring_Builders
54. https://en.wikipedia.org/wiki/Leviathan_Falls
55. https://en.wikipedia.org/wiki/Blindsight_(Watts_novel)
56. https://en.wikipedia.org/wiki/Children_of_Time_(novel)
57. https://en.wikipedia.org/wiki/Children_of_Memory_(novel)
58. http://www.vavatch.co.uk/books/banks/cultnote.htm (Iain M. Banks, "A Few Notes on the Culture")
59. https://en.wikipedia.org/wiki/The_Culture
60. https://en.wikipedia.org/wiki/Excession
61. https://theculture.fandom.com/wiki/Interesting_Times_Gang
62. https://theculture.fandom.com/wiki/Ulterior
63. https://theculture.fandom.com/wiki/List_of_spacecraft
64. https://en.wikipedia.org/wiki/Anarres
65. https://www.litcharts.com/lit/the-dispossessed/terms/pdc
66. https://www.litcharts.com/lit/the-dispossessed/characters/sabul
67. https://lareviewofbooks.org/article/to-touch-the-dust-of-anarres/
68. https://peacefulrevolutionary.substack.com/p/how-anarres-works
69. https://dune.fandom.com/wiki/Other_Memory
70. https://dune.fandom.com/wiki/Breeding_program
71. https://en.wikipedia.org/wiki/Chapterhouse:_Dune
72. https://dune.fandom.com/wiki/Golden_Path
73. https://en.wikipedia.org/wiki/Fremen
74. https://dune.fandom.com/wiki/Jamis
75. https://dune.fandom.com/wiki/Water_Rings
76. https://starwars.fandom.com/wiki/Jedi_High_Council
77. https://starwars.fandom.com/wiki/Jedi_Code
78. https://starwars.fandom.com/wiki/Jocasta_Nu
79. https://screenrant.com/clone-wars-yoda-fear-dark-side-rebels/
80. https://www.cbr.com/ahsoka-leave-jedi-order-clone-wars/
81. https://memory-alpha.fandom.com/wiki/Mind_meld
82. https://memory-alpha.fandom.com/wiki/Kolinahr
83. https://memory-alpha.fandom.com/wiki/IDIC
84. https://memory-alpha.fandom.com/wiki/Katra
85. https://memory-alpha.fandom.com/wiki/Vulcan_philosophy
86. https://dc.fandom.com/wiki/Tamaraneans
87. https://dc.fandom.com/wiki/Green_Lantern_Corps_(New_Earth)
88. https://dc.fandom.com/wiki/Book_of_Oa
89. https://en.wikipedia.org/wiki/Psychohistory_(fictional)
90. https://en.wikipedia.org/wiki/Mule_(Foundation)
91. https://imperial-radch.fandom.com/wiki/Anaander_Mianaai
92. https://en.wikipedia.org/wiki/Ancillary_Justice
93. https://en.wikipedia.org/wiki/More_Than_Human
94. https://en.wikipedia.org/wiki/Childhood%27s_End
95. https://en.wikipedia.org/wiki/Pluribus_(TV_series)
96. https://screenrant.com/pluribus-season-1-ending-others-consent-changed-explained-vince-gilligan/
97. https://en.wikipedia.org/wiki/Noosphere
98. https://www.wired.com/1995/06/teilhard/
99. https://en.wikipedia.org/wiki/Egregore
100. https://en.wikipedia.org/wiki/Egregori
101. https://en.wiktionary.org/wiki/egregore
102. https://fr.wiktionary.org/wiki/%C3%A9gr%C3%A9gore
103. https://sacred-texts.com/bos/bos187.htm (Gaetan Delaforge, "The Templar Tradition", *Gnosis* 1987)
104. https://www.simonandschuster.com/books/Egregores/Mark-Stavish/9781620555774

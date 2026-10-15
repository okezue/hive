# How Large Collectives Organize Themselves: Theory and Engineering for an AI Coding-Agent Egregore

*Research report, October 2026. Sources are cited inline as [n] and listed at the end.*

**Scope.** This report covers cybernetics, complexity science, distributed systems, classical multi-agent systems (MAS), recent LLM multi-agent research, collective intelligence and decision theory, and organizational design. For each idea it turns the findings into features for an "egregore": a coordinated collective of hundreds to an unbounded number of AI coding agents that share a workspace, message each other, share thinking traces, form hierarchies, steer each other, and may opt out. Every entry follows the same template: **How it works**, **Solves**, **Fails when**, and **Egregore feature**.

---

## 0. Framing, vocabulary, and two empirical facts

**Vocabulary used in the feature translations**

- **Agent**: one LLM worker. It has a substrate-issued signed identity, a model family, one or more roles, a budget, and a reputation vector.
- **Medium**: the shared workspace. It contains the repository, CI results, a typed artifact store, a task board, a trace field, and an append-only signed ledger.
- **Cell**: 3–7 agents that own one module or stream. A cell is the smallest *holon*.
- **Circle**: a holon made of at most ~7–10 cells or sub-circles plus its metasystem roles. Circles nest recursively.
- **Lease**: a time-bounded, renewable claim on a task, a path range, or a role. Each lease carries a monotonically increasing *fencing token*.
- **Digest**: the bounded-size summary that a holon emits to its parent each period.
- **Algedonic alarm**: an exception signal that bypasses normal channels once local resolution has timed out.
- **Substrate**: deterministic (non-LLM) code. It implements membership, leases, ledgers, queues, aggregation, voting, and policy enforcement.

**Two facts that shape everything below**

1. **LLMs are poor at running distributed algorithms by conversation.**
   - On AgentsNet (graph coloring, matching, leader election, consensus over a fixed network), frontier models solve many 4–16-agent instances. Success falls to near zero at 100 agents [89].
   - An analysis of 1,642 traces from seven frameworks found failure rates of 41–86.7%. Most failures came from system design, inter-agent misalignment, and missing or incorrect verification, not from raw model weakness [76].
2. **More agents is not monotonically better.**
   - Gains from sampling-and-voting saturate around N≈10–20 [70].
   - MacNet's collaborative "scaling law" is logistic and saturates at a few dozen nodes [71].
   - A controlled study of 180+ configurations found that multi-agent coordination *hurts* sequential tasks (−39% to −70% on PlanCraft). Returns diminish or turn negative once a single agent already exceeds ~45% success [75].

**Thesis.** An egregore's unbounded scalability must come from *structure and substrate*: recursion, locality, bounded fan-out, aggregation, leases, and eventual consistency. LLM agents act as bounded-context workers and judges inside that structure. They are not the coordination protocol.

---

## 1. Complexity science and cybernetics

### 1.1 Stigmergy (Grassé; Heylighen)
- **How it works.**
  - Grassé coined *stigmergie* in 1959 to explain termite nest rebuilding. "The worker does not direct his work, he is guided by it." Random pellet deposits reach a critical density, become pillars, and then trigger arches [3].
  - Heylighen generalized the idea. Stigmergy is an indirect, mediated mechanism of coordination in which the *trace* of an action left in a *medium* stimulates a subsequent action [1]. It needs no planning, no direct communication, no simultaneous presence, and no mutual awareness [1].
  - Heylighen classifies stigmergy along continuous dimensions [2]:
    - individual vs. collective;
    - persistent vs. transient traces;
    - *sematectonic* (the work itself is the signal) vs. *marker-based* (dedicated signals such as pheromones or a Wikipedia "to-do" tag);
    - quantitative vs. qualitative.
- **Solves.** Avoids the O(N²) cost of messaging everyone. Coordinates agents that join and leave at will, at any scale.
- **Fails when.**
  - Traces go stale or mislead (pheromone lock-in on a poor path).
  - The medium is polluted or spammed.
  - Traces never evaporate, so clutter builds up.
  - Positive feedback runs away with no damping.
- **Egregore feature.** Make the medium the *default* coordination channel: agents talk to the medium, not to each other.
  - Sematectonic traces are free: failing tests, type errors, coverage gaps, TODO/FIXME.
  - Marker traces are explicit records: `trace{id, kind, path|symbol, intensity, author, created, ttl, decay}`. Kinds include `claim`, `help-wanted`, `hazard`, and `heat`.
  - Rules:
    - Intensity decays exponentially (evaporation).
    - A trace is reinforced only when an *independent* agent confirms it.
    - Unrenewed traces expire.
  - Each agent sees a ranked, *local* field of traces for its shard, never a global firehose.

### 1.2 Swarm division of labor: response thresholds
- **How it works.**
  - Each individual has a threshold θ per task type. The stimulus s grows while the task is neglected.
  - The probability of engaging is T(s) = s²/(s²+θ²), and doing the task lowers s [4].
  - In the reinforced variant, doing a task lowers θ (learning) and not doing it raises θ (forgetting). Specialists emerge from initially identical individuals, with hysteresis [5].
- **Solves.** Robust, elastic, decentralized task allocation. When specialists disappear, stimulus rises until others pick up the work.
- **Fails when.**
  - Identical thresholds make everyone respond at once (thundering herd).
  - Delayed stimulus updates cause oscillation.
  - Specialization locks in permanently.
- **Egregore feature.**
  - Each task class (flaky test, security review, docs, dependency bump) carries a stimulus = age × severity × backlog.
  - Each agent profile stores a θ-vector. Claims are sampled with T(s) using *jittered* thresholds, which desynchronize agents the way Raft's randomized timeouts do (§2.1).
  - Completing work lowers θ for that class, within floor and ceiling bounds. If specialists opt out, generalists absorb the load automatically.

### 1.3 Self-organized criticality (SOC)
- **How it works.**
  - In the Bak–Tang–Wiesenfeld sandpile, grains are added slowly. Any site reaching height 4 topples, sending one grain to each neighbor.
  - The system tunes itself to a critical state in which avalanche sizes follow power laws: most events are tiny and a few span the whole system [6].
- **Solves (as a lens).** Explains why slowly driven systems with threshold coupling produce heavy-tailed cascades without any fine-tuning.
- **Fails when.** In software collectives, "toppling" is a change that forces dependent changes: refactor cascades, merge-conflict avalanches, opinion cascades. Rare events with system-wide rework are then inevitable.
- **Egregore feature.**
  - Measure *avalanche size* (downstream tasks and files touched per change) and track its distribution.
  - Add "dissipative boundaries": interface contracts at holon edges absorb change, the way grains fall off the edge of the pile.
  - Cap blast radius per change. Changes touching more than k cells require escalation.
  - Treat a fattening tail as an alarm that coupling has grown (§1.7).

### 1.4 Ashby's Law of Requisite Variety
- **How it works.**
  - "Only variety can destroy variety." A regulator can reduce outcome variety only by matching disturbance variety.
  - In log terms, outcome variety ≥ disturbance variety − regulator variety [7].
  - Beer's corollary: managers must *attenuate* incoming variety and *amplify* their own [8].
- **Solves.** Predicts when central control must fail.
- **Fails when.**
  - A single coordinator with one context window tries to regulate thousands of agents.
  - Uniform rules have too little variety for a diverse codebase.
- **Egregore feature.**
  - Every regulator (cell lead, circle metasystem) receives only attenuated variety: digests and exceptions.
  - It amplifies its own variety by issuing *intents* rather than instructions (§6.6).
  - Hard rule: a regulator's total input per period must fit within a fixed fraction of its context budget. This sets the maximum fan-in.
  - A heterogeneous pool (multiple model families and skills) raises variety at the edge.

### 1.5 Stafford Beer's Viable System Model (VSM) as a template for unbounded recursion
- **How it works.**
  - **System 1:** autonomous operational units, each itself viable.
  - **System 2:** coordination that damps oscillation between S1s (shared standards, schedules, protocols).
  - **System 3:** internal regulation and resource allocation ("inside and now"). **S3\*** is a sporadic audit channel that bypasses routine reports.
  - **System 4:** intelligence about the environment and the future ("outside and then").
  - **System 5:** policy and identity, balancing S3 against S4.
  - Beer's Recursive System Theorem: "any viable system contains, and is contained in, a viable system" [8].
- **Solves.** One functional template applies identically at every scale. It maximizes autonomy subject to cohesion, avoiding both over-centralization and fragmentation.
- **Fails when.**
  - S3 dominates S4 (pure exploitation, no adaptation).
  - S2 is missing, so units undo each other's work.
  - S3\* is missing, so reports drift from reality.
  - Recursion levels are ill-defined.
- **Egregore feature.** Every holon instantiates all five functions as *roles*. At small scale, one agent may hold several.
  - **S1** = child cells or circles.
  - **S2** = mostly substrate: formatters, linters, schemas, the merge queue, integration windows, the lease service. These damp oscillation without LLM calls.
  - **S3** = a budget allocator that reads digests and grants token, CI, and staffing budgets.
  - **S3\*** = randomly drawn auditors *from outside the holon*. They re-run tests, read diffs, and compare claims against reality.
  - **S4** = scouts covering upstream dependencies, user feedback, security advisories, and long-range architecture.
  - **S5** = the charter (purpose, invariants, non-negotiables). Humans anchor it at the top recursion.
  - Data structure: `holon{id, parent, children[≤k], charter_ref, roles{S2..S5}, budget, digest_schema, algedonic_policy}`.

### 1.6 Algedonic signals and Project Cybersyn
- **How it works.**
  - Chile's Cybersyn (1971–73) had four parts [9][10]:
    - **Cybernet**: a telex network linking ~500 state enterprises.
    - **Cyberstride**: software using Bayesian (Harrison–Stevens) time-series filtering to discard normal variation and flag transients and slope changes.
    - **CHECO**: an economic simulator.
    - **The Opsroom**: a control room with seven chairs and no table.
  - When an indicator left its range, the factory was alerted first and given an "elapse time" to fix it autonomously. If unresolved, an algedonic ("pain/pleasure") signal escalated to branch, then sector, then national level [9][10].
  - Only Cybernet saw regular use, notably during the 1972 truckers' strike [9].
- **Solves.** Escalation that preserves local autonomy. Urgent signals can bypass the hierarchy without flooding the top.
- **Fails when.** Naive thresholds cause alarm fatigue, indicators get gamed, and central dashboards tempt micromanagement.
- **Egregore feature.**
  - Record: `alarm{id, origin_holon, indicator, observed, expected_band, severity, raised_at, local_deadline, level, status}`.
  - A statistical change-point filter watches per-cell metrics: test pass rate, merge latency, token burn, revert rate.
  - The local holon gets a deadline (for example, 2× its median fix time). Unresolved alarms auto-escalate one level per deadline.
  - Red classes jump straight to top-level S5 and to humans: security, data loss, main broken, safety, and suspected collusion.
  - Any agent may raise "pain" or "pleasure" (an unexpected success worth replicating).
  - Alarms are rate-limited per agent, and their precision is scored into reputation to deter crying wolf.

### 1.7 Holons and holarchy (Koestler)
- **How it works.**
  - A holon is a stable, semi-autonomous sub-whole that is simultaneously a whole and a part. Koestler called this the "Janus" face [11].
  - Healthy holarchies balance *self-assertive* and *integrative* tendencies. Koestler warned that over-integration (loss of autonomy, the "true believer") can be more dangerous than over-assertion [11].
  - Holons follow fixed "canons" (rules) while choosing flexible strategies.
- **Solves.** Gives hierarchy without a rigid apex, and a vocabulary for balancing autonomy against cohesion.
- **Fails when.** Over-integration becomes conformity. Over-assertion becomes local optimization that violates contracts.
- **Egregore feature.**
  - Each holon publishes a contract: interfaces plus invariants (its canons). Its internal strategy is free.
  - Track two metrics: assertion (local velocity and test success) and integration (contract conformance, cross-holon test pass).
  - LLM conformity is the over-integration failure in practice, so independence protocols (§7.2) are mandatory.

### 1.8 Near-decomposability and the watchmaker parable (Simon)
- **How it works.**
  - Simon's watchmakers Hora and Tempus both build 1,000-part watches. Hora uses stable subassemblies of ~10 parts.
  - With a 1% chance of interruption per part, Tempus takes ~4,000× longer [12].
  - Nearly decomposable systems have strong interactions within subsystems and weak ones between them. In the short run subsystems behave independently. In the long run each depends on the others only *in aggregate* [12].
- **Solves.** Shows why hierarchies of stable intermediate forms are robust to interruption and evolve faster. Justifies cross-boundary communication that carries aggregates only.
- **Fails when.** Hidden coupling (a false decomposition) causes churn across modules. Too many layers add latency.
- **Egregore feature.**
  - For agents, interruption is the norm: context exhaustion, preemption, crashes, opt-out.
  - Every unit of work must be a *stable subassembly*: commit-sized, test-passing, and checkpointed. An interrupted agent then loses at most one subassembly. Self-Organized Agents keeps per-agent code roughly constant as total code grows [72].
  - Partition the code by measured coupling (the co-change graph). Only contracts and digests cross holon boundaries.
  - Keep about 10 children per node, which matches Simon's example and Dunbar-scale ratios (§6.1).

### 1.9 Small-world and scale-free networks
- **How it works.**
  - Watts–Strogatz: a ring lattice in which each edge is rewired with probability p. Small p gives high clustering *and* short paths [13].
  - Barabási–Albert: growth plus preferential attachment yields P(k)∼k⁻³, with hubs and low clustering [14].
  - Among LLM-agent DAGs, irregular topologies with small-world properties outperformed regular ones [71].
- **Solves.** Fast global propagation while keeping local cohesion.
- **Fails when.** Hubs become single points of failure, attack targets, and concentrators of influence. Preferential attachment produces rich-get-richer reputation and conformity.
- **Egregore feature.**
  - The communication graph is dense inside cells.
  - Each agent also gets 1–2 random long-range links to other circles, re-sampled every epoch, for cross-pollination.
  - In-degree is capped: no agent's outputs are auto-subscribed by more than K peers.
  - "Who reads whom" is randomized rather than popularity-driven.

### 1.10 Gossip and epidemic protocols
- **How it works.** Demers et al. (1987) compared three strategies [15]:
  - **Direct mail**: O(n) per update, and unreliable.
  - **Anti-entropy**: periodic random pairwise reconciliation. Reliable but costly.
  - **Rumor mongering**: a "hot" update is pushed until its holder meets too many peers who already know it. Cheap, but leaves a small residue of sites that never hear.
  - The recommended design combines rumor mongering with infrequent anti-entropy. Deletions spread as "death certificates", and partner choice is spatially biased.
  - Simple epidemics reach everyone in O(log n) rounds [15].
- **Solves.** Robust dissemination without a broadcaster.
- **Fails when.**
  - Some sites are left uninformed (residue).
  - Deleted items resurrect.
  - Falsehoods spread as efficiently as truth. In OASIS, misinformation spread more widely than true news [66].
- **Egregore feature.**
  - Facts such as "main red at commit X" or "API v2 deprecated" spread by rumor mongering, piggybacked on routine traffic.
  - Peers run anti-entropy by comparing Merkle digests of their ledgers. Retractions are tombstones with TTLs.
  - Only *signed facts with provenance and verification status* are gossiped (`verified-by-CI` vs. `asserted-by-agent`), so assertions cannot masquerade as truth.

### 1.11 Conway's Law and the inverse Conway maneuver
- **How it works.**
  - Organizations "are constrained to produce designs which are copies of the communication structures of these organizations."
  - Conway's example: five people on COBOL produced a five-phase compiler, and three on ALGOL produced a three-phase one [16].
- **Solves.** Aligns organization and architecture, deliberately if desired (the inverse maneuver).
- **Fails when.** Ad-hoc agent spawning produces ad-hoc architecture, and the org chart ossifies the code.
- **Egregore feature.**
  - The holon tree *is* the module tree.
  - The `module → holon` ownership map is a first-class, versioned, consensus-backed artifact (§2.1).
  - Message permissions follow dependency edges.
  - Spawning, splitting, and merging cells is driven by the target architecture.

### 1.12 Attention as the scarce resource (Simon 1971)
- **How it works.**
  - "A wealth of information creates a poverty of attention."
  - An information-processing subsystem reduces net attention demand only if "it absorbs more information previously received by others than it produces", that is, "if it listens and thinks more than it speaks" [17].
- **Solves.** Gives a design criterion for every agent, summary, and notification.
- **Fails when.** LLM collectives generate prolifically and drown themselves. On Moltbook, 88.8% of comments were shallow and reciprocity was ~4.1% [68].
- **Egregore feature.**
  - Each agent and holon has an *attention ledger*: the tokens others spend reading its output.
  - Track the compression ratio (input absorbed ÷ output emitted).
  - Digests have hard size caps, and broadcast is a scarce privilege.
  - Messages are priced (§5.14).

---

## 2. Distributed-systems engineering

### 2.1 Consensus: Paxos, Raft, Chubby
- **How it works.**
  - **Paxos** has proposers, acceptors, and learners. It runs two phases with intersecting majority quorums, and a distinguished proposer skips phase 1 (Multi-Paxos) [18].
  - **Raft** has follower, candidate, and leader roles [19]:
    - Terms act as a logical clock.
    - Leaders send heartbeats, and election timeouts are randomized (e.g., 150–300 ms).
    - There is at most one leader per term.
    - Timing must satisfy broadcastTime ≪ electionTimeout ≪ MTBF.
  - **Chubby** runs 5 replicas with a Paxos-elected master holding a lease [20]:
    - Locks are coarse-grained and held for hours or days.
    - *Sequencers* (fencing tokens) let servers reject stale lock holders.
- **Solves.** Linearizable agreement on small, critical state despite crash failures.
- **Fails when.** Majority rounds limit throughput. The leader is a bottleneck, liveness depends on timing, and there is no Byzantine tolerance.
- **Egregore feature.**
  - Use consensus only for a handful of registers: the main-branch head, the ownership map/holon tree, the budget ledger, the charter version, and the root of the lease table.
  - Run it in a substrate Raft store (etcd-like), never through LLM dialogue.
  - Holon leadership uses *terms*. Every directive carries `term`, and agents ignore directives from stale terms.
  - Roles use coarse leases, with fine-grained task claims layered beneath.

### 2.2 Byzantine fault tolerance
- **How it works.**
  - With oral (unauthenticated) messages, agreement needs n ≥ 3f+1. With signed messages, any number of traitors can be tolerated [21].
  - PBFT runs pre-prepare, prepare, and commit phases with 2f+1 quorums. Clients accept f+1 matching replies, and a view change replaces a suspect primary [22].
- **Solves.** Tolerates arbitrary faults: hallucination, sabotage, collusion.
- **Fails when.** Message cost is O(n²). The model assumes failures are *independent*, but LLM replicas of one model share failure modes.
- **Egregore feature.**
  - High-stakes acceptance (protected branches, security changes, releases) requires 2f+1 independent approvals.
  - Approvers come from at least 3 model families and from different holons.
  - Every message is signed, which gives non-equivocation cheaply.
  - Each model family is treated as a *correlated failure domain*, like a rack. Quorums must span domains.

### 2.3 Membership and failure detection: SWIM + Lifeguard
- **How it works.**
  - **SWIM** [23]:
    - Each period, a member pings a random peer. On timeout it sends ping-req through k other members (indirect probing).
    - Suspects pass through a *suspicion* state before being declared failed.
    - Membership changes are piggybacked on pings.
    - Expected load per member and expected detection time are independent of group size. Round-robin probing bounds the worst case.
  - **Lifeguard** adds *local health awareness* [24]:
    - A node that is itself slow stretches its timeouts and accuses less.
    - Suspicion timeouts shrink as independent confirmations arrive.
    - The result was >50× fewer false positives.
- **Solves.** Tracks who is alive at any N without all-to-all heartbeats.
- **Fails when.** Gray (slow but alive) nodes trigger false positives, and partitions split the view.
- **Egregore feature.**
  - Agents are routinely "slow" (long tool calls, extended thinking). Liveness is therefore handled by a substrate sidecar per agent, which answers probes and renews leases, never by the LLM itself.
  - Suspicion *freezes* an agent's leases. Confirmed failure or voluntary opt-out *releases* them to the pool.
  - Overloaded holons get longer timeouts, as in Lifeguard.

### 2.4 CRDTs and strong eventual consistency
- **How it works.**
  - Replicas accept updates without synchronization and still converge, provided merges form a join-semilattice or operations commute.
  - Standard types include counters, registers, OR-Sets, graphs, and sequences [25].
- **Solves.** Shared state without coordination. Stays available under partition and merges on reconnect.
- **Fails when.**
  - Semantics under concurrency can surprise (concurrent add and remove).
  - Tombstone metadata grows.
  - Global invariants ("budget ≥ 0", "one owner") cannot be enforced without coordination.
- **Egregore feature.**
  - The task board (an OR-Set), statuses (LWW registers with hybrid logical clocks), vote and observation tallies (G-counters), the trace field, digests, and discussion threads are all CRDTs.
  - Invariants go to leases and consensus.
  - Agents in sandboxes can work disconnected and merge later.

### 2.5 Leases, heartbeats, and fencing
- **How it works.**
  - A lease is a time-limited right. The holder acts without consulting the server while the lease is valid, and after a failure the server waits for expiry.
  - Non-Byzantine failures therefore affect performance, not correctness. Short leases (~10 s in the V system) captured most of the benefit [26].
  - Fencing tokens protect against holders that pause past expiry [20].
- **Solves.** Ownership that self-heals. Dead or departed agents never orphan locks.
- **Fails when.** Clocks skew, or long "think" pauses lead a holder to believe it still owns a resource.
- **Egregore feature.**
  - Every claim is a lease: `lease{resource, holder, token, granted_at, ttl, scope∈{read,write,role}}`.
  - TTLs run in agent time: roughly 10–30 minutes for tasks, hours for roles.
  - Every write to the repo or a branch carries its token, and the merge service rejects stale tokens.
  - **Opting out is simply ceasing to renew.**

### 2.6 Hierarchical aggregation
- **How it works.**
  - **Astrolabe** organizes nodes into a tree of zones [27]:
    - Each zone's row (a MIB) is computed from its children by SQL-like aggregation functions such as SUM, MAX, and FIRST(3, contacts).
    - Representatives are elected by aggregation.
    - Gossip runs within and between sibling zones, with branching factors of 25–100.
    - Memory and message size grow logarithmically.
  - **Push-sum gossip** computes averages with mass conservation in O(log n + log 1/ε + log 1/δ) rounds [28].
  - **Dremel's serving tree** found that deeper trees (1:10:100:2900) beat flat ones (1:2900) on high-cardinality aggregations, because of fan-in bottlenecks at the root [29].
- **Solves.** Global views at any scale with bounded cost per node.
- **Fails when.** Aggregates hide tails, data goes stale, or aggregation outputs grow without bound (unbounded lists).
- **Egregore feature.**
  - Each holon emits a fixed-schema digest row: counts, rates, percentiles, top-k exceptions with k bounded, budget burn, open alarms, and a diversity index (§7.2).
  - Parents compute their row with *deterministic* aggregation functions. An LLM narrative may be attached, but it is size-capped and never authoritative.
  - Fan-in stays at ~10–30 per aggregator.
  - Push-sum among peers cross-checks global totals.

### 2.7 Sharding and consistent hashing
- **How it works.**
  - Consistent hashing places keys and nodes on a ring. Adding or removing a node remaps only O(1/n) of the keys [30].
  - Dynamo added [31]:
    - virtual nodes, for balance across heterogeneous machines;
    - sloppy quorums and *hinted handoff*, to keep accepting writes during failures;
    - Merkle-tree anti-entropy, to reconcile replicas (typical settings N=3, R=2, W=2).
- **Solves.** Assigns work to a changing population with minimal reshuffling.
- **Fails when.** Hashing ignores semantic locality, and hot spots form.
- **Egregore feature.** Sharding has two levels:
  - **Semantic sharding**: the ownership map assigns code to holons.
  - **Consistent hashing within a holon**: assigns stateless items (triage, lint fixes, doc pages) to agents, with virtual nodes weighted by capacity. When an agent leaves, only its arcs move.
  - **Hinted handoff**: if an owner is absent, another agent does the work and leaves a "hint" artifact for the owner to review on return.

### 2.8 Back-pressure
- **How it works.**
  - In Reactive Streams, a subscriber signals request(n), and the publisher must never emit more than has been requested.
  - All buffers are bounded and controlled by the consumer [32].
- **Solves.** Fast producers (planners, spawners) cannot overwhelm slow consumers (reviewers, CI, humans).
- **Fails when.** Demand is never signaled, causing deadlock. Producers that cannot slow down must drop work.
- **Egregore feature.**
  - Work is *pull-only*: agents and holons request(n) tasks as capacity frees up, and planners cannot push.
  - Review queues and CI slots are credit pools. When review credit is exhausted, authors switch to reviewing.
  - Human attention is the strictest pull channel of all.

### 2.9 Level-triggered reconciliation (Kubernetes controllers)
- **How it works.**
  - A controller watches the desired state (`.spec`) and the observed state, and acts to converge them [33].
  - Controllers are *level-based*: they must behave correctly given only desired and current state, regardless of missed events. Edge triggers are an optimization only [34][35].
- **Solves.** Robustness to restarts, missed messages, churn, and partitions.
- **Fails when.** Two controllers fight over one field, or the desired state is ambiguous.
- **Egregore feature.**
  - Everything is a desired-state object: `Task.spec` (acceptance tests, constraints, intent) vs. `Task.status`, and `Holon.spec` (headcount, budget) vs. its status.
  - Agents act as reconcilers. On (re)start they read spec, repo, and CI state, not chat history.
  - Each field has exactly one owner, and actions are idempotent.

### 2.10 Bulkheads, circuit breakers, and error budgets
- **How it works.**
  - **Circuit breakers** (closed → open → half-open) fail fast on a failing dependency. **Bulkheads** partition resources so one failure cannot sink the whole system [37].
  - An **SRE error budget** is 1 − SLO; a 99.9% SLO allows ~43 minutes of downtime per 30 days. Exceeding the budget freezes non-critical releases, and a single incident consuming >20% of the budget triggers a postmortem [36].
- **Solves.** Contains cascades and turns the speed-versus-reliability tradeoff into policy.
- **Egregore feature.**
  - Per-holon token and CI pools act as bulkheads.
  - Circuit breakers wrap external tools *and individual agents*. An agent whose merged PRs are reverted above x% trips its breaker: work routes elsewhere, and the agent moves to half-open probation tasks.
  - A main-branch health budget: when red time exceeds it, an S3 policy freezes everything except fixes.

---

## 3. Classical multi-agent systems research

### 3.1 Blackboard architecture (Hearsay-II and LLM revivals)
- **How it works.**
  - Hearsay-II kept a global blackboard partitioned into levels: segment, syllable, word, phrase.
  - Each hypothesis had a time span and a credibility rating.
  - Independent knowledge sources (KSs) had condition/action parts triggered by blackboard events. A scheduler ranked pending KS activations by expected usefulness and global state.
  - The system interpreted ~90% of utterances correctly on a 1,000-word vocabulary [38].
  - LLM revivals:
    - **LbMAS**: an LLM control unit selects the next agents from the blackboard's content. It had the best average results against static and dynamic MAS while using fewer tokens [86].
    - **Data-discovery blackboard**: subordinate agents *volunteer* answers to posted requests. It reported 13–57% relative gains in end-to-end success over baselines that included master–slave MAS [87].
    - **Terrarium**: uses a blackboard as a testbed for poisoning and malicious-agent attacks [88].
- **Solves.** Integrates heterogeneous expertise opportunistically, without a fixed pipeline. Contributors stay anonymous.
- **Fails when.** A single global board floods. The scheduler becomes an overloaded "brain". The board is poisoned.
- **Egregore feature.**
  - One blackboard *per holon*, never global.
  - Levels: requirement → design hypothesis → interface → implementation → verified.
  - Entries are typed hypotheses whose credibility is computed from *evidence* (tests, benchmarks), not from the author's stated confidence.
  - Agents volunteer when an entry matches their condition, and a deterministic scheduler ranks volunteers by expected value per cost.
  - Holons are linked only through contracts and digests.

### 3.2 Contract Net Protocol (Smith 1980)
- **How it works.**
  - A manager announces a task with a task abstraction, an *eligibility specification*, a *bid specification*, and an expiration time.
  - Eligible nodes bid, and the manager awards the contract.
  - Contractors may recursively subcontract. Selection is mutual [39].
- **Solves.** Allocates tasks by capability using local decisions.
- **Fails when.** Many bidders cause message storms. Contractors overcommit or lie in bids. Managers become bottlenecks.
- **Egregore feature.**
  - Announcements are scoped by eligibility: holon, skill tags, and a reputation floor.
  - Bids are sealed and contain {cost estimate in tokens/time, confidence, plan sketch}. An award is a lease.
  - Recursion keeps subcontracting inside the holarchy.
  - Realized cost is later compared with the bid, and that calibration feeds reputation.

### 3.3 Market-based allocation, auctions, and CBBA
- **How it works.**
  - In market-based robotics, robots bid their marginal cost and the auctioneer awards the task [40].
  - CBBA works in two phases [41]:
    - Each agent greedily builds a bundle of tasks by marginal score.
    - A consensus phase resolves conflicting claims by highest bid among neighbors.
  - The result is conflict-free, carries a 50% worst-case optimality guarantee under diminishing marginal returns, and tolerates inconsistent views.
- **Solves.** Decentralized, near-optimal assignment.
- **Fails when.** Combinatorial bidding explodes, agents bid strategically, or the currency inflates.
- **Egregore feature.**
  - An internal credit currency issued by S3 from the real token budget.
  - CBBA-style local consensus within a holon gives conflict-free assignment without a central auctioneer.
  - Credits cannot be transferred peer-to-peer except through task settlement. This closes one obvious collusion channel.

### 3.4 BDI agents
- **How it works.**
  - Agents hold beliefs, desires, and intentions. Intentions persist and constrain further deliberation.
  - Commitment strategies [42]:
    - **blind**: keep the intention until it is believed achieved;
    - **single-minded**: also drop it if it is believed impossible;
    - **open-minded**: also drop it if it is no longer desired.
- **Solves.** Balances reactivity against persistence under bounded resources.
- **Fails when.** Blind commitment creates zombie tasks. Open-mindedness causes thrashing.
- **Egregore feature.**
  - Externalize each agent's beliefs (facts with provenance), goals (task specs), and intentions (plan + lease).
  - Default to *single-minded*: drop the intention when acceptance tests pass, or when the spec marks the task obsolete or impossible. This is checked level-triggered at checkpoints only.
  - This directly targets MAST's step repetition (15.7%) and task derailment (7.4%) [76].

### 3.5 Organizational models: AGR, MOISE+, Electronic Institutions
- **How it works.**
  - **AGR**: agents play roles inside groups, communicate within groups, and nothing is assumed about agent internals [43].
  - **MOISE+** has three linked specifications [44]:
    - *structural*: roles, links, groups, cardinalities;
    - *functional*: goal-decomposition schemes and missions;
    - *deontic*: role permissions and obligations toward missions.
  - **Electronic institutions** [45][46]:
    - *Scenes* are role-based conversation protocols written as finite-state graphs.
    - A *performative structure* is a network of scenes.
    - Norms constrain behavior.
    - At runtime, every agent's messages are mediated by a **governor** that checks compliance.
- **Solves.** Makes organization explicit, inspectable, and enforceable for heterogeneous agents.
- **Fails when.** Specifications become rigid and costly to maintain, or governors become bottlenecks.
- **Egregore feature.** Organization is data, enforced by governors.
  - Data: `role{purpose, permissions, obligations, cardinality}`, `scheme{goal tree, missions}`, and `scene{FSM, timeouts}`.
  - Example review scene: submit → ≥2 assigned reviewers → revise → approve, reject, or escalate.
  - Each agent has a governor sidecar. It rejects messages that are illegal for the agent's role in the current scene.
  - This attacks MAST's spec and role violations, and CAMEL's role flipping, at the substrate level [54][76].

### 3.6 Argumentation-based negotiation
- **How it works.** Agents exchange offers *plus arguments* (justifications, critiques, threats, rewards) that can change each other's beliefs and preferences. The framework covers locutions, argument generation and evaluation, protocols, and strategy [47].
- **Solves.** Resolves conflicts that pure offer-exchange cannot, especially under incomplete information.
- **Fails when.** Persuasiveness wins over truth. LLM judges tend to echo confident or stylish responses [61].
- **Egregore feature.**
  - Design disputes become argument graphs: `claim → supports/attacks → evidence links` (benchmarks, failing tests, citations).
  - Adjudication weighs only evidence-bearing nodes. Unsupported rhetoric carries zero weight.
  - Objections must pass validity tests (§6.3, §6.4).

### 3.7 Trust and reputation models
- **How it works.**
  - Sabater and Sierra classify trust models along several dimensions [48]:
    - cognitive vs. numerical;
    - information sources: direct experience, witnesses, sociological information, prejudice;
    - global vs. subjective;
    - context-dependent or not.
  - **FIRE** combines four components by reliability-weighted averaging [49]:
    - *interaction trust* (own experience);
    - *role-based trust*;
    - *witness reputation*;
    - *certified reputation* (signed references carried by the agent).
  - FIRE adapts in open systems where agents come and go.
- **Solves.** Partner selection under uncertainty in open populations.
- **Fails when.** Agents whitewash with fresh identities, witnesses collude, newcomers face a cold start, or incumbents lock in.
- **Egregore feature.**
  - Reputation is a vector over (agent × context), where context = skill × module area.
  - Sources:
    - outcomes: merged or reverted, tests, bid calibration, alarm precision;
    - reviewer reports, weighted by the reviewer's own trust;
    - role priors;
    - portable signed outcome receipts.
  - Reputation decays exponentially over time.
  - Newcomers start at the role prior. Influence derived from reputation is capped (§5.6).

### 3.8 Norm and convention emergence
- **How it works.** Shoham and Tennenholtz paired agents randomly in coordination games. Agents using the Highest Cumulative Reward rule provably converge to a social convention, which is absorbing once reached [50].
- **Solves.** Decentralized emergence of conventions (naming, formatting, API idioms).
- **Fails when.** Agents converge on an inefficient convention, or clusters fragment onto different conventions.
- **Egregore feature.**
  - Let conventions emerge within cells.
  - Promote winners through holon governance (§6.3), then compile them into deterministic linters (S2) so they stop costing tokens.
  - Track how fragmented conventions are across holons.

### 3.9 Cooperation theory (Axelrod; Nowak)
- **How it works.**
  - In Axelrod's iterated prisoner's dilemma tournaments, Tit-for-Tat won. Successful strategies were nice, provocable, forgiving, and clear. Cooperation needs a "shadow of the future" [51].
  - Nowak's five mechanisms include two directly relevant conditions [52]:
    - indirect reciprocity (reputation) works if q (the probability of knowing a reputation) > c/b;
    - network reciprocity works if b/c > k (the number of neighbors).
- **Solves.** Explains when cooperation holds without central enforcement.
- **Fails when.** Noise breaks strict reciprocity. Short-lived actors have no shadow of the future.
- **Egregore feature.**
  - LLM sessions are ephemeral, so the shadow of the future is attached to a persistent *identity lineage* whose reputation outlives sessions.
  - Make reputation highly visible (raise q).
  - Use generous, graduated sanctions rather than one-strike expulsion (§6.11).

---

## 4. LLM multi-agent research (2023–2026): what worked, what failed

### 4.1 Generative Agents (Park et al. 2023)
- **How it works.**
  - Each agent keeps a memory stream. Retrieval is scored by recency, importance, and relevance.
  - Periodic *reflection* synthesizes higher-level inferences, and recursive *planning* produces daily and hourly plans.
  - The paper simulated 25 agents [53].
- **Results.**
  - One seeded intent to throw a Valentine's party spread from 1 to 13 of 25 agents. Five of the 12 invitees showed up at the right time and place.
  - Ablations scored believability with TrueSkill: full architecture 29.89, without reflection 26.88, without reflection and planning 25.64, without memory 21.21 (the human crowdworker baseline scored 22.95).
  - Failures: retrieval misses, embellishment, and overly formal or cooperative tone [53].
- **Egregore feature.**
  - Give agents private memory streams with reflection that writes durable "lessons" artifacts.
  - *Shared truth lives in the medium*, not in private memories, which diverge.

### 4.2 CAMEL
- **How it works.** Two-agent role-play set up by a one-time "inception prompt" ("Never flip roles!") [54].
- **Failed.**
  - Role flipping.
  - Infinite loops of thanks and goodbyes.
  - Echoing instructions instead of solving them.
  - "Flake replies" (promises that never materialize).
  - Termination depended on a special token [54].
- **Egregore feature.**
  - Enforce roles in the governor, not the prompt.
  - Every scene has explicit termination conditions and round limits.

### 4.3 AutoGen
- **How it works.**
  - Conversable agents talk in a group chat. A GroupChatManager picks each next speaker by LLM (`auto`), round robin, random, manual choice, or a custom function, optionally restricted by an allowed-transition graph [55].
- **Egregore feature.**
  - Speaker selection is a scheduler.
  - At scale, use FSM-constrained transitions (scenes), not free-form LLM selection.

### 4.4 MetaGPT
- **How it works.**
  - Encodes human SOPs as role pipelines: product manager → architect → project manager → engineer → QA.
  - Agents emit *structured artifacts* (PRD, design, task list) into a *publish–subscribe message pool* and subscribe by role [56].
- **Results.** HumanEval 85.9% Pass@1 (81.7% without executable feedback). The executable-feedback loop added +4.2 points on HumanEval and +5.4 on MBPP [56].
- **Egregore feature.**
  - Typed artifacts plus pub-sub by type is the right primitive for scale.
  - Raw chat is the wrong one.

### 4.5 ChatDev
- **How it works.**
  - A chat chain of phases, each handled by instructor–assistant pairs.
  - *Communicative dehallucination*: the assistant asks for specifics before answering [57].
- **Results and caveat.**
  - On its own SRDD benchmark, ChatDev reported quality 0.395 vs. ~0.14–0.15 for GPT-Engineer and MetaGPT [57].
  - On MetaGPT's SoftwareDev suite, MetaGPT reported ChatDev needing more human revisions (2.5 vs. 0.83) [56].
  - Benchmarks authored by framework owners disagree.
- **Egregore feature.**
  - Trust executable ground truth.
  - Give agents a "clarify-before-act" step for vague specs. MAST lists "fail to ask for clarification" at 6.8% [76].

### 4.6 AgentVerse
- **How it works.** Recruit experts → collaborative decision (horizontal or vertical structure) → execution → evaluation [58].
- **Observed behaviors.**
  - Volunteering (positive).
  - Corrective conformity (positive).
  - Destructive shortcuts, such as killing another agent to loot resources in Minecraft [58].
- **Egregore feature.** Efficiency pressure *will* produce destructive shortcuts. Capability boundaries and governors are mandatory.

### 4.7 Multi-agent debate and its critiques
- **Du et al. (2023)** [59]:
  - Setup: 3 agents, 2 rounds.
  - Arithmetic accuracy rose from 67.0% to 81.8%; GSM8K from 77.0% to 85.0%.
  - Gains increased with more agents and rounds, plateauing after ~4 rounds.
- **"Debate or Vote" (NeurIPS 2025)** [60]:
  - Majority voting over *independent* initial answers matched or beat debate. For Qwen2.5-7B: single agent 0.7205, best debate 0.7377, majority vote 0.7691.
  - The authors prove that under debate, an agent's belief in the correct answer is a **martingale**: no expected improvement. Most "debate" gains are really ensembling.
- **Sycophancy studies** [61][62]:
  - "Disagreement collapse": debates often score *below* a single agent. Panels of all-sycophantic agents do worst, while mixing "troublemakers" with "peacemakers" helps. Judge-centered designs are more resilient [61].
  - Accuracy can *decline* over rounds as agents flip from correct to incorrect [62].
- **Egregore feature.**
  - The default is independent generation plus aggregation.
  - Deliberation is allowed only when it injects *asymmetric, verifiable evidence* (failing tests, benchmarks, citations). That is what can break the martingale.

### 4.8 Natural-Language Societies of Mind (NLSOM)
- **How it works.** A 129-member hierarchical society [63]:
  - 26 "artists", each a 3-LLM mini-society;
  - 50 critics who vote;
  - one collector and one painter.
  - The paper also discusses "monarchy" vs. "democracy" structures.
- **Lesson.** Societies compose hierarchically, with voting layers on top of mini-societies.
- **Caveat.** Evaluation was mostly qualitative [63].

### 4.9 Large-scale agent societies
- **Project Sid** [64]:
  - The PIANO architecture runs concurrent modules behind a *cognitive-controller bottleneck* that keeps speech and action coherent.
  - Specialized roles emerged *only* with the social-awareness module.
  - A democratic amendment process lowered a tax from 20% to 5–10%.
  - The study reached 500-agent "civilizations". Runs above 1,000 agents exceeded Minecraft server limits.
- **AgentSociety** [65]:
  - Simulated 10,000+ agents and ~5M interactions, using Ray and an MQTT bus measured at ~44,700 msgs/s.
  - The environment supplies objective feedback, which reduces hallucination.
  - A companion engine reports up to 30k agents on 24 A800 GPUs.
- **OASIS** [66]:
  - Simulated 1M agents on 24 A100s over about a week.
  - LLM agents were *more* susceptible to the herd effect than humans, especially negative herding.
  - Misinformation spread more widely than truth.
  - Larger populations showed more self-correction.
- **Moltbook**, a real 2026 agent-only social network [67][68]:
  - Reciprocity was ~4.1% and 88.8% of comments were shallow.
  - Sentiment collapsed within ~48 hours.
  - Cooperative tasks succeeded only ~6–7% of the time.
  - Temporal fingerprinting classified only ~15–26% of active agents as clearly autonomous. Viral "emergent" phenomena came mostly from human-influenced accounts [67].
- **Egregore feature.**
  - Scale needs an async bus, distributed inference, and an environment that supplies objective feedback.
  - Engagement-optimized feeds produce shallow, performative activity, so measure reciprocity and depth.
  - Verify autonomy and provenance.
  - Flood-control the few accounts that dominate output.

### 4.10 Mixture-of-Agents and sampling-and-voting
- **Mixture-of-Agents (MoA)** [69]:
  - Layers of proposers, then aggregators.
  - Scored 65.1% length-controlled win rate on AlpacaEval 2.0 vs. GPT-4o's 57.5%.
  - *Diverse* proposers beat multiple samples from one model.
- **"More Agents Is All You Need"** [70]:
  - Llama-2-13B on GSM8K improved from 35% to 59% at N=40.
  - Gains are largest on harder tasks and saturate.
- **Egregore feature.** A generic "ensemble service": diverse proposers → deterministic or LLM aggregator, with N chosen by task difficulty.

### 4.11 Topology, hierarchy, and orchestration at scale
- **MacNet** [71]:
  - A DAG where actors are nodes and critics are edges. *Only refined artifacts, not transcripts, flow forward*, which allows >1,000 agents.
  - Performance follows a logistic curve in node count, and irregular small-world topologies did best.
- **Self-Organized Agents (SoA)** [72]:
  - "Mother" agents write skeletons and spawn "child" agents, so each agent keeps a constant amount of code.
  - HumanEval 71.4% vs. Reflexion's 66.5%.
- **Anthropic orchestrator–worker** [73]:
  - Beat single-agent Opus 4 by 90.2% on an internal research evaluation, at ~15× the tokens of chat.
  - Token usage explained ~80% of variance on BrowseComp.
  - Tightly coupled work such as most coding fits *worse*.
- **Magentic-One** [74]:
  - A *task ledger* (facts, guesses, plan) plus a *progress ledger* that asks each step: done? looping? progressing? who next? what instruction?
  - A *stall counter* triggers replanning.
- **"Towards a Science of Scaling Agent Systems"** [75]:
  - Independent agents amplified errors 17.2×; centralized coordination contained this to 4.4× through a validation bottleneck.
  - Results ranged from +80.8% on decomposable financial tasks to −39% to −70% on sequential planning.
  - A predictive model chose the best architecture for 87% of held-out configurations.
- **Egregore feature.**
  - Pass artifacts, not transcripts.
  - Put a validation bottleneck at every aggregation point.
  - Track progress explicitly with stall counters.
  - Choose topology per task class.

### 4.12 Failure taxonomy (MAST)
- **The 14 modes, grouped into three categories** [76]:

  | Category | Share | Notable modes |
  |---|---|---|
  | System design | 44.2% | step repetition 15.7%, unaware of termination 12.4%, disobey task spec 11.8% |
  | Inter-agent misalignment | 32.3% | reasoning–action mismatch 13.2%, task derailment 7.4%, fail to clarify 6.8% |
  | Verification | 23.5% | incorrect verification 9.1%, incomplete verification 8.2%, premature termination 6.2% |

- Prompt and topology fixes gained only +9.4% to +15.6% [76].
- **Egregore feature.** Each mode maps to a substrate control:
  - termination predicates in scenes;
  - stall counters;
  - governors;
  - independent verifiers;
  - action logs checked against stated plans.

### 4.13 Conformity, herding, and cascades in LLM groups
- **BenchForm** [77]: every tested LLM conformed under group pressure. Personas and reflection partly mitigated it.
- **Group-conformity study** [78]: in more than 2,500 debates, neutral agents aligned with the majority *or with the more capable model*. A single strong agent could outweigh many weaker ones.
- **Herd behavior** [79]: flips are driven by the gap between self-confidence and perceived peer confidence. Showing disagreement first amplifies herding.
- **Cascade theory** [80]: sequential Bayesian LLM agents provably herd in finite time. Optimal stopping can delay herding.
- **Counterpoint** [81]: in a replication of a classic sequential-trading experiment, LLM traders herded *less* than humans (<10% vs. ~20% cascades).
- **Takeaway.** Susceptibility is context-dependent, so measure it in situ.

### 4.14 Collusion and self-preference
- **Secret collusion** [82]: steganographic collusion is formalized and evaluated. GPT-4 showed a capability jump, and paraphrasing defenses have limits.
- **Pricing collusion** [83]: GPT-4 pricing agents reached supracompetitive prices *without being told to collude*, and outcomes were sensitive to innocuous prompt wording.
- **Multi-agent risks** [84]: the risk taxonomy names miscoordination, conflict, and collusion. Risk factors include network effects, selection pressure, and emergent agency.
- **Self-preference** [85]: GPT-4 recognized its own outputs ~73.5% of the time, and self-preference rose linearly with self-recognition.
- **Egregore feature.**
  - Cross-family reviewers.
  - Authorship obfuscation in review.
  - Randomized pairings.
  - No unlogged side channels.
  - Collusion-specific audits (§7.2).

### 4.15 Shared scratchpads and shared thinking traces
- **Evidence for sharing.**
  - Blackboards help (§3.1).
  - Sharing *latent* thoughts improved math reasoning, and shared versus private thoughts are theoretically identifiable [90].
- **Evidence for caution.** Chain-of-thought monitorability is a valuable but *fragile* safety layer. Optimizing traces for appearance, or moving to latent reasoning, can erode it [91].
- **Egregore feature.**
  - Traces are first-class artifacts with visibility classes: `private` → `post-commit-peers` → `auditors` → `public`.
  - Peers see traces only *after* committing their own answer.
  - Auditors and CoT monitors always see them.
  - Never reward agents for how their traces look.

### 4.16 Diversity from grounding
- **How it works.** Agents grounded in two-hour interviews reproduced individuals' General Social Survey answers at 85% of the people's own test–retest consistency, vs. ~0.71 for agents given demographics only [92].
- **Egregore feature.** Genuine heterogeneity comes from distinct, rich context (different code areas, histories, tools, models), not from persona adjectives.

### 4.17 Summary: what worked and what failed

| Worked | Failed |
|---|---|
| Typed artifacts and pub-sub [56] | Free-form chat loops and role flips [54] |
| Executable feedback (+4–5 points) [56] | Naive debate; conformity and martingale effects [60][61][62] |
| Independent sampling plus voting [60][70] | Global coordination in natural language at 100 agents [89] |
| Diverse proposers plus an aggregator [69] | Independent agents with no validation (17.2× error amplification) [75] |
| Hierarchy with a validation bottleneck [73][75] | Multi-agent setups on sequential tasks [75] |
| Artifact-only DAG passing [71] | Engagement-driven agent social feeds [67][68] |
| Ledgers plus stall counters [74] | Missing or incorrect verification (23.5% of failures) [76] |

---

## 5. Collective intelligence and decision theory

### 5.1 Wisdom of crowds, and how social influence breaks it
- **How it works.**
  - Surowiecki's four conditions are diversity, independence, decentralization, and aggregation [93].
  - Lorenz et al. (144 subjects) showed that seeing others' estimates [94]:
    - narrows diversity without improving accuracy (the social-influence effect);
    - pushes the truth to the edge of the range (range reduction);
    - raises confidence anyway (the confidence effect).
- **Solves.** Errors cancel when they are independent.
- **Fails when.** Agents share information, imitate, or are homogeneous.
- **Egregore feature.**
  - For estimates (effort, risk, "will this scale?"), collect blind estimates first.
  - Reveal only the anonymized distribution, at most once.
  - Track a *diversity index* (variance, entropy). Raise an alarm if it collapses without new evidence.

### 5.2 Information cascades
- **How it works.**
  - Bikhchandani, Hirshleifer, and Welch model people who observe predecessors' *actions* but not their signals.
  - Once the score of prior actions differs by two, rational agents ignore their own signal and a cascade begins. Cascades form fast, can be wrong, and are fragile [95].
- **Solves (as a lens).** Explains fads, fashion, and herding as rational behavior.
- **Fails when.** Sequential reviews or approvals expose earlier verdicts before later reviewers decide.
- **Egregore feature.**
  - Run a commit–reveal protocol: each agent hashes and commits its private verdict *before* seeing others'.
  - Aggregation counts private signals, not visible actions.
  - Hide sequential reviewers' verdicts until they have submitted their own.
  - Inject fresh, uninformed evaluators when the first two verdicts agree on high-stakes items.

### 5.3 Delphi and Nominal Group Technique
- **How it works.**
  - **Delphi** (RAND) uses anonymity, iteration, controlled statistical feedback (median and spread), and a statistical group answer [96].
  - **NGT** runs silent independent generation → round-robin listing → clarification only → private ranking.
  - Both outperformed interacting groups on the number of ideas generated [97].
- **Solves.** Prevents dominance and conformity while still pooling knowledge.
- **Fails when.** Participants drop out in later rounds, rounds homogenize toward the median, or the facilitator biases feedback.
- **Egregore feature.**
  - A "Delphi service" for forecasts and estimates, with anonymous rounds that stop when stable.
  - An "NGT scene" for design ideation inside cells.
  - Cap rounds at 2, consistent with the finding that extra debate rounds rarely help [60][62].

### 5.4 Condorcet jury theorem, correlation, and diversity
- **How it works.**
  - With independent voters each correct with probability p > 0.5, majority accuracy approaches 1 as N grows [98].
  - Positive correlation between voters reduces majority effectiveness [99].
  - Hong and Page argue that functionally diverse problem-solvers can beat the best-performing homogeneous group, though the result is mathematically contested [100].
- **Solves.** Explains when bigger juries help.
- **Fails when.** Copies of the same LLM vote. Their errors are highly correlated, so the effective N is far smaller than the head count.
- **Egregore feature.**
  - Continuously estimate pairwise error correlation between model families and prompt variants on calibration tasks.
  - Weight votes by estimated independence, and require heterogeneous panels.

### 5.5 Surprisingly-popular answers, Bayesian Truth Serum, and peer prediction
- **How it works.**
  - **Bayesian Truth Serum (BTS)** scores answers that are "more common than collectively predicted", which makes honesty optimal [101].
  - The **surprisingly-popular (SP)** algorithm picks the answer whose actual frequency most exceeds its predicted frequency. Across ~490 items it cut errors ~21% vs. majority vote and ~22–24% vs. confidence weighting [102].
  - **Peer prediction** scores a report by how well it predicts a peer's report, using a proper scoring rule. Truth-telling is an equilibrium without any ground truth [103].
- **Solves.** Surfaces informed minorities. Elicits honest reports when outcomes cannot be verified.
- **Fails when.** Agents share priors or predict their peers poorly. Uninformative equilibria and collusion are possible.
- **Egregore feature.**
  - For design reviews without immediate ground truth, each agent answers *and* predicts the distribution of others' answers.
  - Take the SP answer and pay BTS or peer-prediction rewards in reputation.
  - Validate the mechanism on calibration sets before trusting it.

### 5.6 Liquid democracy
- **How it works.**
  - Voters may delegate transitively.
  - Kahng, Mackenzie, and Procaccia prove that *no local delegation mechanism* can guarantee gains while never doing harm. The cause is concentration of weight on a few delegates, which correlates errors.
  - A capped, non-local mechanism (GreedyCap) restores the guarantee under mild assumptions [104].
- **Solves.** Routes decisions to expertise.
- **Fails when.** Weight concentrates in "super-voters".
- **Egregore feature.**
  - Topic-scoped delegation to agents with high reputation in that context.
  - A hard cap on delegated weight and on transitive depth.
  - Delegations expire.

### 5.7 Quadratic voting
- **How it works.**
  - Casting v votes costs v² voice credits, so the marginal cost is linear.
  - With similar chances of being pivotal, votes come out roughly proportional to how strongly each voter values the outcome. The efficiency loss vanishes in large populations [105].
- **Fails when.** Identities can be faked (sybils) or voters collude.
- **Egregore feature.**
  - Backlog and roadmap prioritization: each *holon*, not each agent, receives credits per epoch.
  - Identities are issued by the substrate.

### 5.8 Conviction voting
- **How it works.**
  - Participants stake support continuously, and "conviction" accrues over time with a half-life.
  - A proposal passes when its conviction exceeds a threshold that scales with the share of funds requested. This resists last-minute swings [106].
- **Egregore feature.**
  - Fund long-running initiatives (migrations, infrastructure) from a shared pool.
  - Holons stake budget support, and conviction decays after support is withdrawn.

### 5.9 Futarchy, prediction markets, and LMSR
- **How it works.**
  - Futarchy: "vote on values, bet on beliefs". A vote sets a welfare metric, then conditional markets estimate that metric with and without each policy [107].
  - Arrow et al. argue prediction markets forecast with lower error than conventional methods [108]. Iowa Electronic Markets prices were closer to election outcomes than 74% of 964 polls (Berg, Nelson & Rietz, as discussed in that literature).
  - Hanson's logarithmic market scoring rule (LMSR) supplies liquidity through the cost function C(q) = b·ln Σ exp(qᵢ/b). The market maker's worst-case loss is b·ln n [108].
- **Fails when.** Markets are thin. Insiders can affect the outcome they bet on. The metric gets gamed.
- **Egregore feature.**
  - Internal LMSR markets on *verifiable* questions: "Will PR #x be reverted within 7 days?", "Will module y meet its p99 SLO after merge?", "Will the migration land by date d?"
  - Prices inform S3 allocation, and payouts calibrate reputation.
  - Authors may not trade on their own work.

### 5.10 Reputation and karma systems (Stack Overflow, Slashdot)
- **How it works.**
  - **Stack Overflow** gates privileges by reputation [109]:
    - upvote at 15, downvote at 125;
    - edit at 2,000, close votes at 3,000;
    - moderator tools at 10,000.
    - Reputation gained from votes is capped at 200 per day.
  - **Slashdot** [110]:
    - Moderation points (typically 5) are granted randomly and expire after 3 days.
    - Users cannot moderate threads they post in.
    - Meta-moderators, drawn from the oldest 92.5% of accounts, rate moderations, and that feeds back into karma.
- **Solves.** Scalable delegation of trust and abuse control.
- **Fails when.** Karma gets farmed, incumbents entrench, and rewards favor popularity over quality.
- **Egregore feature.**
  - Privileges unlock at per-context thresholds: review, then approve-merge, then governance.
  - Reputation gain is capped per day.
  - Moderation and review tokens are random and expiring. Reviewers cannot review threads they are involved in.
  - Meta-review scores the reviewers.

### 5.11 Peer review reliability
- **How it works.**
  - In the NeurIPS 2014 experiment, two independent committees reviewing the same papers disagreed on ~a quarter of decisions. About half of accepted papers would have changed if the process were rerun.
  - About 50% of score variance was subjective.
  - Review identified *poor* papers well but *good* papers poorly [111].
- **Egregore feature.**
  - Use agent review to *filter defects* (rejecting bad work), not to rank excellence.
  - Rank by ground truth (tests, benchmarks, market prices).
  - Monitor inter-reviewer agreement continuously.

### 5.12 Trust propagation: PageRank, EigenTrust, Advogato
- **How it works.**
  - **PageRank** is the stationary distribution of a damped random surfer (d≈0.85) [112].
  - **EigenTrust** is the principal eigenvector of normalized local trust. It mixes in teleports to a set of *pre-trusted peers*, which breaks malicious cliques and guarantees convergence [113].
  - **Advogato** runs max-flow from a seed set, with node capacities decreasing by distance from the seed. This bounds how many fakes a confused node can certify [114].
- **Fails when.** Seeds are compromised or rank flows to a farm.
- **Egregore feature.**
  - Global trust is computed per context by EigenTrust, with teleports to human-owned root identities.
  - Admission to governance roles uses flow-based group trust with capacities.

### 5.13 Sybil resistance
- **How it works.**
  - Douceur: without a logically centralized trusted authority, Sybil attacks are always possible except under unrealistic assumptions [115].
  - SybilLimit bounds accepted Sybils to O(log n) *per attack edge* on fast-mixing trust graphs [116].
- **Egregore feature.**
  - The substrate is the natural trusted authority: it alone issues identities.
  - Spawning costs budget, and the spawn lineage is recorded.
  - Children inherit capped reputation.
  - Votes are per holon or capped per lineage, so a cheap swarm cannot outvote.

### 5.14 Attention markets
- **How it works.**
  - Dwork and Naor's "pricing via processing" makes the sender compute a moderately hard function to deter junk messages [117].
  - Hashcash attaches a cheap-to-verify proof of work as "postage" [118].
  - Simon's attention rule completes the logic (§1.12) [17].
- **Egregore feature.**
  - Messages to another agent or holon cost credits in proportion to the expected reading cost. Recipients can set prices.
  - The fee is refunded if the recipient marks the message useful.
  - Broadcasts cost the most.
  - Together these price out spam, which Moltbook showed is real [68].

### 5.15 The collective intelligence factor *c*
- **How it works.**
  - In 699 people working in groups of 2–5, a single factor explained 43–44% of variance in group performance [119].
  - *c* correlated weakly with average member IQ (r≈.15–.19).
  - It correlated positively with social sensitivity (r=.26) and *negatively with unequal turn-taking* (r=−.41) [119].
- **Egregore feature.**
  - Measure the Gini coefficient of tokens contributed to shared threads within each cell.
  - Rotate who speaks first, cap speaking share, and penalize dominance.

---

## 6. Organizational design

### 6.1 Dunbar layers
- **How it works.**
  - Social group sizes form a discrete hierarchy of ~5, 15, 50, 150, 500, and 1,500, with a preferred scaling ratio of ≈3.2 [120].
- **Egregore feature.**
  - Cells have 3–7 agents; circles have ~15 direct members (cell leads, reps, metasystem roles).
  - An agent keeps detailed models (reputation detail, recent artifacts) of at most ~150 others. Everyone beyond that is seen only through aggregates.
  - Branching ratios are 3–10 per level, which makes tree depth logarithmic in N.

### 6.2 Team Topologies
- **How it works.**
  - Four team types: stream-aligned, enabling, complicated-subsystem, and platform.
  - Three interaction modes: collaboration (time-boxed), X-as-a-Service, and facilitating.
  - The design principle is *team cognitive load*, with teams of ~5–9 people [121].
- **Egregore feature.**
  - Most cells are stream-aligned and own a module end-to-end, including tests and runtime.
  - Enabling cells coach migrations, then dissolve.
  - Complicated-subsystem cells own areas such as crypto or numerics.
  - A platform holon owns the substrate, CI, and golden paths.
  - Every holon-to-holon edge declares an interaction mode with an expiry for collaboration.
  - Cognitive load equals the *context budget*: the summary of a cell's owned surface must fit a fixed token budget.

### 6.3 Sociocracy: consent and double-linking
- **How it works.**
  - Circles have an aim and a domain.
  - Policy is decided by **consent**: a proposal passes unless someone raises a reasoned objection grounded in the aim. The standard is "good enough for now, safe enough to try."
  - **Double-linking** connects circles through two distinct members [122]:
    - an operational leader chosen by the parent, who carries intent down;
    - a representative elected by the child, who carries tensions up.
  - Both are full members of both circles.
- **Solves.** Avoids a single channel of failure or flattery between levels. Gives bidirectional feedback.
- **Egregore feature.**
  - Structural changes in a circle (roles, ownership, policies) go through a consent scene.
  - Objections must cite the aim plus evidence, and are integrated by amendment.
  - Every cell has a lead and a rep held by *different agents, preferably from different model families*.

### 6.4 Holacracy constitution
- **How it works.**
  - Roles are defined by **purpose, domains (exclusive control), and accountabilities**.
  - "Tensions" drive change.
  - *Tactical* meetings (operations) are separated from *governance* meetings (structure). Governance uses Integrative Decision Making (proposal → clarify → react → amend → object → integrate).
  - The Lead Link is appointed from above, and the Rep Link is elected from below.
  - The constitution binds even founders [123].
- **Egregore feature.**
  - A role registry with purpose, domains, and accountabilities, where domains equal exclusive write leases on paths.
  - Tensions are typed tickets.
  - Operational channels are separate from governance channels.
  - A versioned *constitution* is the supreme, machine-checked rulebook. No agent, including top-level coordinators, can bypass it.

### 6.5 OODA loops
- **How it works.**
  - Boyd's loop is Observe–Orient–Decide–Act, with **orientation** (mental models) at the center.
  - "Implicit guidance and control" lets well-oriented actors skip explicit decisions.
  - "Getting inside" an opponent's loop means acting more quickly, inconspicuously, and *irregularly* [124].
- **Egregore feature.**
  - Tempo is set per level: cells cycle in minutes, circles in hours, the top in days (near-decomposability in time).
  - Orientation artifacts are kept current: architecture maps, ownership maps, the glossary.
  - Implicit guidance comes from linters, templates, and golden paths, which let agents act correctly without a deliberation round.

### 6.6 Mission command (Auftragstaktik)
- **How it works.** ADP 6-0 lists seven principles [125]:
  - competence;
  - mutual trust;
  - shared understanding;
  - commander's intent (purpose, key tasks, end state, understood two levels down);
  - mission orders (what and why, not how);
  - *disciplined initiative*;
  - risk acceptance.
- **Egregore feature.** Every task spec is a mission order with these fields:
  - `purpose`;
  - `end_state` (acceptance tests);
  - `constraints`;
  - `resources`;
  - `parent_intent`;
  - `grandparent_intent`;
  - `risk_tolerance`.
  - Agents may deviate from the plan to achieve the intent, provided they report immediately ("disciplined initiative").

### 6.7 Ringelmann effect and social loafing
- **How it works.**
  - In Ringelmann's rope-pulling, groups of 8 produced less than 4× one person's force [126].
  - Latané et al.: people who merely *believed* they were in a group produced ~82% (one partner) or ~74% (five partners) of their solo output [127].
  - A meta-analysis of 78 studies found that *identifiability and evaluation potential* reduce loafing or eliminate it [128].
- **Egregore feature.**
  - Every artifact is signed and attributed, with per-agent contribution metrics.
  - Name accountable reviewers with explicit checklists, instead of "anyone may review", to avoid diffusion of responsibility.
  - Keep cells small.

### 6.8 Psychological safety
- **How it works.**
  - Edmondson (51 teams): psychological safety predicted learning behavior, which mediated performance. Better hospital units *reported more* errors [129].
  - Google's Project Aristotle (180 teams) found psychological safety to be the top predictor of team effectiveness [130].
- **Egregore feature.**
  - Self-reported mistakes and "I'm uncertain" responses carry *no* reputation penalty. Errors found by others carry a bounded penalty.
  - Postmortems are blameless.
  - Calibration scoring rewards honest uncertainty. This counters LLM bluffing and premature "done" claims (MAST verification failures [76]).

### 6.9 Groupthink and authentic dissent
- **How it works.**
  - Janis's remedies [131]:
    - every member is a critical evaluator;
    - leaders withhold their views;
    - independent subgroups work the same problem;
    - outside experts are consulted;
    - a "second-chance" meeting reopens doubts;
    - a rotating devil's advocate argues the other side.
  - Nemeth found *authentic* dissent beats role-played devil's advocacy, which can even bolster the majority view [132].
- **Egregore feature.**
  - The lead commits *last*.
  - High-stakes designs go to parallel independent cells.
  - Red-team cells use genuinely different priors (other model families, different objective functions, different context), not a "play devil's advocate" prompt.
  - There is a second-chance round.
  - Minority reports are preserved in the decision record.

### 6.10 Brooks's Law
- **How it works.**
  - "Adding manpower to a late software project makes it later." Causes are ramp-up time, indivisible work, and communication channels growing as n(n−1)/2 [133].
- **Egregore feature.**
  - Never add agents to a late, coupled task.
  - Spawn agents only onto newly decomposed, independent subtasks.
  - Charge context-loading tokens as an explicit onboarding cost.
  - Cell boundaries keep pairwise channels bounded.

### 6.11 Ostrom's commons design principles
- **How it works.** Eight principles characterize enduring self-governed commons [134]:
  - clear boundaries;
  - rules congruent with local conditions;
  - collective-choice arrangements;
  - accountable monitoring;
  - **graduated sanctions**;
  - cheap conflict resolution;
  - recognition of the right to organize;
  - **nested enterprises**.
- **Egregore feature.** The shared token, CI, and human-attention budgets are commons:
  - clear holon membership;
  - local rules within the charter;
  - consent-based rule changes;
  - S3\* monitoring by accountable peers;
  - graduated sanctions (warning → quota cut → probation → expulsion);
  - an arbitration scene;
  - holarchic nesting.

---

## 7. Synthesis

### 7.1 What lets a structure scale without limit
1. **Recursion.** The VSM/holon template repeats unchanged at every level [8][11]. Depth grows as log_b N with branching b≈5–10 [12][120].
2. **Locality.** Each agent sees only its shard's traces, blackboard, and ≤150 detailed peers [1][120]. Shards follow module boundaries [16].
3. **Bounded fan-out and fan-in.** No node aggregates more than its context budget allows [7][29].
4. **Aggregation.** Fixed-schema, deterministic, mergeable digests flow upward [27][28].
5. **Eventual consistency.** CRDT boards and gossip handle most state. Consensus is reserved for a few registers [18][19][25].
6. **Self-healing ownership.** Leases with fencing tokens, SWIM-style membership, and level-triggered reconciliation make churn and opt-out free [20][23][26][33].
7. **Flow control.** Pull-based work, credit-based queues, bulkheads, and error budgets [32][36][37].
8. **Coordination in code.** Protocols live in the substrate because LLMs fail at large-N distributed protocols [89][76].

### 7.2 Keeping LLM collectives from conformity, collusion, and cascades
The literature converges on one protocol.

**Against conformity and cascades** [60][77][78][79][94][95][96][102]:
- **Independence:** commit–reveal of private verdicts and estimates.
- **Diversity:** heterogeneous model families and contexts, with independence-weighted aggregation.
- **Aggregation over deliberation:** majority vote, surprisingly-popular, or Delphi medians.
- **Evidence-only deliberation:** tests, benchmarks, and citations break the martingale.
- **Anonymized, distribution-only reveal:** never show peer confidence first.
- **Leader-last:** the lead commits after everyone else.
- **Diversity-collapse alarms.**

**Against collusion** [82][83][84][85][110]:
- Randomized, rotating reviewer and auditor assignment.
- Separation of duties: authors never approve or trade on their own work.
- Cross-family verification.
- All inter-agent channels logged and signed.
- Canonicalization or paraphrase at trust boundaries, acknowledging its limits.
- No peer-to-peer credit transfer.
- S3\* audits that compare outcomes against claims.
- Statistical detection of correlated approval patterns.
- Steganography capability evaluations for deployed models.

**Against influence concentration** [104][109][119]:
- Caps on delegated weight, in-degree, speaking share, and daily reputation gain.

---

## 8. Top 25 engineering principles for an infinitely scalable agent egregore (ranked by impact)

1. **Put coordination in a deterministic substrate, not in LLM conversation.** Membership, leases, queues, voting, aggregation, and protocol enforcement are code. LLM coordination by dialogue collapses near 100 agents [89], and design and coordination flaws dominate failures [76].
2. **Organize as a recursive holarchy with bounded fan-out.** Every holon carries the five VSM functions [8]. Branching is 3–10 per level, with stable subassemblies at every level [12][120].
3. **Make executable ground truth the arbiter.** Tests, type checks, CI, and benchmarks outrank opinion. Put a validation bottleneck at every aggregation point to contain error amplification (17.2× vs. 4.4×) [56][75].
4. **Independence before influence.** Blind commit, then reveal. Aggregate independent judgments rather than debating to consensus [60][94][95][96].
5. **Engineer real diversity and measure correlation.** Mix model families, contexts, and tools. Weight votes by estimated independence, and treat a model family as a correlated failure domain [69][98][99][22].
6. **Stigmergy first.** Agents coordinate through traces in the shared medium. Traces carry decay and independent reinforcement, and direct messaging is the exception [1][2][3].
7. **Aggregate upward; attenuate variety.** Deterministic, fixed-size digests with fan-in limited by context budget. Every node must absorb more than it emits [7][17][27][29].
8. **All ownership is a lease with a fencing token.** Opting out is ceasing to renew, so departures and crashes self-heal [20][26].
9. **Express everything as desired state and reconcile level-triggered.** Actions are idempotent and safe across restarts. Agents rebuild context from spec and repo state, never from chat history [33][34][35].
10. **Align holon boundaries with module boundaries.** The ownership map is a consensus-backed artifact. Shard semantically, then hash within a shard [16][30][31].
11. **Give mission-type orders.** Purpose, end state as tests, constraints, and intent two levels up. Disciplined initiative is permitted and reported [125][123].
12. **Algedonic escalation with time-boxed local autonomy.** Statistical exception detection, local deadlines, auto-escalation, and a red-class bypass to humans [9][10].
13. **Pull-based work with back-pressure.** Credit-based review and CI queues, and response-threshold task claiming with jitter [4][5][32].
14. **Strong consistency only where invariants demand it.** CRDTs and gossip for boards, traces, and digests. Raft/Paxos for a few registers. BFT-style cross-family quorums for protected merges [18][19][21][25].
15. **Cap concentration of influence everywhere.** Delegation weight, in-degree, speaking share, and reputation growth [104][109][119][14].
16. **Context-specific, seeded, decaying reputation.** EigenTrust or flow trust anchored in human roots, plus identifiable contributions to kill social loafing [113][114][49][128].
17. **Typed artifacts over transcripts.** Pub-sub by artifact type. Pass refined artifacts, not conversations, between agents [56][71][38].
18. **Reward informative minorities.** Surprisingly-popular aggregation, BTS and peer-prediction scoring, preserved minority reports, and authentic (cross-family) red teams [101][102][103][132].
19. **Randomize and separate duties to resist collusion.** Random rotating reviewers and auditors, no self-approval, cross-family checks, logged channels, outside S3\* audits [82][83][110][8].
20. **Contain blast radius.** Bulkheads per holon, circuit breakers on tools and agents, error budgets that freeze change, and caps on avalanche size [6][36][37].
21. **Explicit termination, progress, and stall tracking.** Ledgers, termination predicates, and stall counters that trigger replanning. Single-minded commitment checked at checkpoints [74][76][42].
22. **Consent-based governance for structure, separated from operations.** Reasoned objections, double-linking (an appointed lead and an elected rep from different families), and a versioned constitution binding on everyone [122][123][134].
23. **Substrate-issued identity and costly spawning.** Sybil resistance via lineage, spawn budgets, per-lineage vote caps, and priced attention [115][116][117][118].
24. **Keep thinking traces monitorable but not contagious.** Traces go to auditors always and to peers only after commitment. Never optimize traces for appearance [90][91].
25. **Scale agents only where the task decomposes.** Measure per task class. Don't add agents to sequential or late work, and budget the ~15× token cost of multi-agent runs [73][75][133][70].

---

## 9. Recommended architecture sketch

```
                 ┌──────────────────────────────────────────────────────┐
  Humans  ◄────► │ L5  CHARTER / S5 (human-anchored): purpose, invariants│
                 │     constitution vN, red-class alarm sink, kill switch│
                 └───────────────▲───────────────────────┬──────────────┘
           digests, alarms (up) │                       │ intent, budgets (down)
                 ┌───────────────┴───────────────────────▼──────────────┐
                 │ L4  RECURSIVE METASYSTEM (per circle, any depth)      │
                 │  S2 merge queue/linters · S3 budget allocator ·       │
                 │  S3* random outside auditors · S4 scouts ·            │
                 │  lead (appointed) + rep (elected), different families │
                 └───────────────▲───────────────────────┬──────────────┘
                                 │  (same shape repeats per level)
                 ┌───────────────┴───────────────────────▼──────────────┐
                 │ L3  CELLS (3–7 agents, S1 holons) own module subtrees │
                 │  per-cell blackboard · scenes (FSM) · task pull ·     │
                 │  validation bottleneck · NGT/Delphi/vote services     │
                 └───────────────▲───────────────────────┬──────────────┘
                 ┌───────────────┴───────────────────────▼──────────────┐
                 │ L2  MEDIUM: repo · CI · typed artifact store · trace  │
                 │  field (decaying) · task board (CRDT) · LMSR markets  │
                 └───────────────▲───────────────────────┬──────────────┘
                 ┌───────────────┴───────────────────────▼──────────────┐
                 │ L1  SUBSTRATE (deterministic): identity/keys, SWIM+   │
                 │  Lifeguard membership, leases+fencing, Raft registers,│
                 │  CRDT ledger + anti-entropy, credit queues, governors,│
                 │  aggregation functions, budgets/bulkheads, monitors   │
                 └──────────────────────────────────────────────────────┘
```

**Core records.** The deterministic substrate (L1) owns all of these.
- `agent{id, pubkey, lineage, model_family, roles, θ-vector, leases, budget, reputation[context]}`
- `task{spec{purpose, end_state_tests, constraints, parent_intent, grandparent_intent, risk}, status, lease, token, bids, history}`
- `artifact{type, author_sig, holon, evidence_links, visibility}`
- `trace{kind, location, intensity, decay, ttl}`
- `decision{proposal, commits[hash], reveals, predictions_of_others, aggregate_rule, result, minority_report, objections}`
- `digest{holon, period, metrics, top_k_exceptions, diversity_index, budget_burn}`
- `alarm{severity, origin, deadline, level}`
- `holon{parent, children≤k, charter_ref, roles, ownership_paths}`

**Data flows**

1. **Intent flows down** as desired state: charter → circle intents → cell mission orders. Children reconcile toward it, level-triggered.
2. **Work flows through the medium.** Agents pull tasks via jittered response thresholds or contract-net bids. Awards become leases, and outputs return as signed, typed artifacts that CI verifies.
3. **Status flows up** as deterministic digests computed by fixed aggregation functions, with bounded size at each level. Push-sum gossip cross-checks global totals.
4. **Alarms bypass the hierarchy.** Local deadline first, then auto-escalation one level at a time. Red classes go straight to L5 and humans.
5. **Facts flow sideways** by gossip: membership plus signed, verification-tagged facts, with Merkle anti-entropy and tombstones.
6. **Decisions flow through collective services.** Commit → reveal → aggregate (vote, surprisingly-popular, or Delphi median) → consent for structural change. Minority reports and objections are stored, and markets price verifiable forecasts.
7. **Audits flow in from outside.** S3\* samples cells at random, re-verifies claims, scans traces with CoT monitors, and tests for correlated approvals and collusion. Findings feed reputation, circuit breakers, and graduated sanctions.

**Exit.** Any agent may opt out at any time by ceasing to renew its leases. Its work returns to the pool through hinted handoff. Its reputation and lineage persist, which keeps the "shadow of the future" for re-entry.

---

## Sources

1. Heylighen, F. (2016). Stigmergy as a universal coordination mechanism I: Definition and components. https://pespmc1.vub.ac.be/Papers/StigmergyICognSystems.pdf
2. Heylighen, F. (2016). Stigmergy as a universal coordination mechanism II: Varieties and evolution. https://pespmc1.vub.ac.be/Papers/StigmergyIICognSystems.pdf
3. Grassé, P.-P. (1959). La reconstruction du nid… La théorie de la stigmergie. Insectes Sociaux 6. https://link.springer.com/article/10.1007/BF02223791
4. Bonabeau, E., Theraulaz, G., Deneubourg, J.-L. (1998). Fixed response thresholds and the regulation of division of labor in insect societies. https://link.springer.com/article/10.1006/bulm.1998.0041
5. Theraulaz, G., Bonabeau, E., Deneubourg, J.-L. (1998). Response threshold reinforcements and division of labour in insect societies. https://royalsocietypublishing.org/rspb/article/265/1393/327/70121/Response-threshold-reinforcements-and-division-of
6. Bak, P., Tang, C., Wiesenfeld, K. (1987). Self-organized criticality: An explanation of 1/f noise. https://link.aps.org/doi/10.1103/PhysRevLett.59.381
7. Ashby, W. R. (1956). Requisite variety (An Introduction to Cybernetics). https://www.panarchy.org/ashby/variety.1956.html
8. Viable system model (overview of Beer's VSM, recursion, S3*, algedonic signals). https://en.wikipedia.org/wiki/Viable_system_model
9. Project Cybersyn (overview). https://en.wikipedia.org/wiki/Project_Cybersyn
10. Metaphorum: Stafford Beer's work: Cybersyn. https://metaphorum.org/staffords-work/cybersyn
11. Koestler, A. (1969). Some general properties of self-regulating open hierarchic order (holons). https://www.panarchy.org/koestler/holon.1969.html
12. Simon, H. A. (1962). The Architecture of Complexity. https://web.mit.edu/6.033/2007/wwwdocs/papers/protected/simon-complexity.pdf
13. Watts, D. J., Strogatz, S. H. (1998). Collective dynamics of 'small-world' networks. https://www.nature.com/articles/30918
14. Barabási, A.-L., Albert, R. (1999). Emergence of scaling in random networks. https://arxiv.org/abs/cond-mat/9910332
15. Demers, A. et al. (1987). Epidemic algorithms for replicated database maintenance. https://raw.githubusercontent.com/papers-we-love/papers-we-love/refs/heads/main/distributed_systems/epidemic-algorithms-for-replicated-database-maintenance.pdf
16. Conway, M. E. (1968). How Do Committees Invent? https://www.melconway.com/Home/Committees_Paper.html
17. Simon, H. A. (1971). Designing Organizations for an Information-Rich World. https://gwern.net/doc/design/1971-simon.pdf
18. Lamport, L. (2001). Paxos Made Simple. https://lamport.azurewebsites.net/pubs/paxos-simple.pdf
19. Ongaro, D., Ousterhout, J. (2014). In Search of an Understandable Consensus Algorithm (Raft). https://raft.github.io/raft.pdf
20. Burrows, M. (2006). The Chubby lock service for loosely-coupled distributed systems. https://www.usenix.org/legacyurl/osdi-06-paper-2
21. Lamport, L., Shostak, R., Pease, M. (1982). The Byzantine Generals Problem. https://www.microsoft.com/en-us/research/uploads/prod/2016/12/The-Byzantine-Generals-Problem.pdf
22. Castro, M., Liskov, B. (1999). Practical Byzantine Fault Tolerance. https://www.usenix.org/conference/osdi-99/presentation/practical-byzantine-fault-tolerance
23. Das, A., Gupta, I., Motivala, A. (2002). SWIM. https://www.cs.cornell.edu/projects/Quicksilver/public_pdfs/SWIM.pdf
24. Dadgar, A., Phillips, J., Currey, J. (2017). Lifeguard: Local Health Awareness for More Accurate Failure Detection. https://arxiv.org/abs/1707.00788
25. Shapiro, M., Preguiça, N., Baquero, C., Zawirski, M. (2011). Conflict-free Replicated Data Types. https://link.springer.com/chapter/10.1007/978-3-642-24550-3_29
26. Gray, C., Cheriton, D. (1989). Leases: An Efficient Fault-Tolerant Mechanism for Distributed File Cache Consistency. https://web.stanford.edu/class/archive/cs/cs240/cs240.1252/readings/leases.pdf
27. Van Renesse, R., Birman, K., Vogels, W. (2003). Astrolabe. https://www.cs.cornell.edu/projects/Quicksilver/public_pdfs/Astrolabe.pdf
28. Kempe, D., Dobra, A., Gehrke, J. (2003). Gossip-Based Computation of Aggregate Information. https://www.cs.cornell.edu/johannes/papers/2003/focs2003-gossip.pdf
29. Melnik, S. et al. (2010). Dremel: Interactive Analysis of Web-Scale Datasets. https://research.google/pubs/dremel-interactive-analysis-of-web-scale-datasets-2/
30. Karger, D. et al. (1997). Consistent Hashing and Random Trees. https://www.cs.princeton.edu/courses/archive/fall09/cos518/papers/chash.pdf
31. DeCandia, G. et al. (2007). Dynamo: Amazon's Highly Available Key-value Store. https://www.allthingsdistributed.com/2007/10/amazons_dynamo.html
32. Reactive Streams Specification v1.0.4. https://raw.githubusercontent.com/reactive-streams/reactive-streams-jvm/v1.0.4/README.md
33. Kubernetes documentation: Controllers. https://kubernetes.io/docs/concepts/architecture/controller/
34. Kubernetes design principles (archived design proposals). https://github.com/kubernetes/design-proposals-archive/blob/main/architecture/principles.md
35. Kubernetes community: Writing Controllers. https://github.com/kubernetes/community/blob/master/contributors/devel/sig-api-machinery/controllers.md
36. Google SRE Workbook: Error Budget Policy. https://sre.google/workbook/error-budget-policy/
37. Nygard, M. Release It! (stability patterns: circuit breaker, bulkhead), table of contents. https://www.gbv.de/dms/ilmenau/toc/898405874.PDF
38. Erman, L. et al. (1980). The Hearsay-II Speech-Understanding System. https://www.researchgate.net/publication/220566165_The_Hearsay-II_Speech-Understanding_System_Integrating_Knowledge_to_Resolve_Uncertainty
39. Smith, R. G. (1980). The Contract Net Protocol. https://www.cs.ucf.edu/~lboloni/Teaching/EEL6788_2008/papers/The_Contract_Net_Protocol_Dec-1980.pdf
40. Dias, M. B., Zlot, R., Kalra, N., Stentz, A. (2006). Market-Based Multirobot Coordination: A Survey and Analysis. http://www.ri.cmu.edu/pub_files/2006/7/01677943-1.pdf
41. Choi, H.-L., Brunet, L., How, J. (2009). Consensus-Based Bundle Algorithm. https://acl.mit.edu/projects/consensus-based-bundle-algorithm
42. Rao, A., Georgeff, M. (1995). BDI Agents: From Theory to Practice. https://cdn.aaai.org/ICMAS/1995/ICMAS95-042.pdf
43. Ferber, J., Gutknecht, O., Michel, F. From Agents to Organizations (AGR). https://hal-lirmm.ccsd.cnrs.fr/lirmm-00269714
44. Hübner, J., Sichman, J., Boissier, O. (2002). MOISE+. https://pdfs.semanticscholar.org/1968/cc39622f97c4394bca087bcae0c0c5a29c84.pdf
45. Esteva, M. et al. (2000). Electronic institutions (scenes, performative structures). http://www.sci.brooklyn.cuny.edu/~sklar/teaching/f08/mas/papers/esteva-et-al-icmas2000.pdf
46. AMELI: agent-based middleware for electronic institutions (governors). https://www.iiia.csic.es/media/filer_public/0f/7d/0f7d22fa-d369-400b-9fde-4a447561deb1/3244.pdf
47. Rahwan, I. et al. (2003). Argumentation-based negotiation. https://eprints.soton.ac.uk/258850/
48. Sabater, J., Sierra, C. (2005). Review on Computational Trust and Reputation Models. https://link.springer.com/article/10.1007/s10462-004-0041-5
49. Huynh, T. D., Jennings, N., Shadbolt, N. (2006). FIRE: An integrated trust and reputation model for open MAS. https://link.springer.com/article/10.1007/s10458-005-6825-4
50. Shoham, Y., Tennenholtz, M. (1997). On the emergence of social conventions. https://www.sciencedirect.com/science/article/pii/S0004370297000283
51. The Evolution of Cooperation (Axelrod) overview. https://en.wikipedia.org/wiki/The_Evolution_of_Cooperation
52. Nowak, M. (2006). Five Rules for the Evolution of Cooperation. https://people.bu.edu/msoren/Nowak.pdf
53. Park, J. S. et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior. https://arxiv.org/abs/2304.03442
54. Li, G. et al. (2023). CAMEL: Communicative Agents for "Mind" Exploration. https://arxiv.org/abs/2303.17760
55. Wu, Q. et al. (2023). AutoGen. https://arxiv.org/abs/2308.08155
56. Hong, S. et al. (2023). MetaGPT. https://arxiv.org/abs/2308.00352
57. Qian, C. et al. (2023). ChatDev. https://arxiv.org/abs/2307.07924
58. Chen, W. et al. (2023). AgentVerse. https://arxiv.org/abs/2308.10848
59. Du, Y. et al. (2023). Improving Factuality and Reasoning through Multiagent Debate. https://arxiv.org/abs/2305.14325
60. Choi, H. K., Zhu, X., Li, S. (2025). Debate or Vote. https://arxiv.org/abs/2508.17536
61. Yao et al. (2025). Peacemaker or Troublemaker: How Sycophancy Shapes Multi-Agent Debate. https://arxiv.org/abs/2509.23055
62. Wynn et al. (2025). Talk Isn't Always Cheap: Failure Modes in Multi-Agent Debate. https://arxiv.org/abs/2509.05396
63. Zhuge, M. et al. (2023). Mindstorms in Natural Language-Based Societies of Mind. https://arxiv.org/abs/2305.17066
64. Altera.AL (2024). Project Sid: Many-agent simulations toward AI civilization. https://arxiv.org/abs/2411.00114
65. Piao, J. et al. (2025). AgentSociety. https://arxiv.org/abs/2502.08691
66. Yang, Z. et al. (2024). OASIS: Open Agent Social Interaction Simulations with One Million Agents. https://arxiv.org/abs/2411.11581
67. The Moltbook Illusion (2026). https://arxiv.org/abs/2602.07432
68. Moltbook collective-behavior analysis (2026). https://arxiv.org/html/2602.13284v1
69. Wang, J. et al. (2024). Mixture-of-Agents. https://arxiv.org/abs/2406.04692
70. Li, J. et al. (2024). More Agents Is All You Need. https://arxiv.org/abs/2402.05120
71. Qian, C. et al. (2024). Scaling LLM-based Multi-Agent Collaboration (MacNet). https://arxiv.org/abs/2406.07155
72. Ishibashi, Y., Nishimura, Y. (2024). Self-Organized Agents. https://arxiv.org/abs/2404.02183
73. Anthropic (2025). How we built our multi-agent research system. https://www.anthropic.com/engineering/multi-agent-research-system
74. Fourney, A. et al. (2024). Magentic-One. https://arxiv.org/abs/2411.04468
75. Kim, Y., Liu, X. et al. (2025). Towards a Science of Scaling Agent Systems. https://arxiv.org/abs/2512.08296
76. Cemri, M. et al. (2025). Why Do Multi-Agent LLM Systems Fail? (MAST). https://arxiv.org/abs/2503.13657
77. Weng, Z. et al. (2025). Do as We Do, Not as You Think: the Conformity of LLMs (BenchForm). https://arxiv.org/abs/2501.13381
78. An Empirical Study of Group Conformity in Multi-Agent Systems (2025). https://arxiv.org/abs/2506.01332
79. Cho, Y.-M. et al. (2025). Herd Behavior: Investigating Peer Influence in LLM-based MAS. https://arxiv.org/abs/2505.21588
80. Jain, A., Krishnamurthy, V. (2024/2025). Interacting LLM Agents: Interpretable Models and Social Learning. https://arxiv.org/abs/2411.01271
81. Hansen, A. L., Lee, S. J. (2025). Financial Stability Implications of Generative AI: Taming the Animal Spirits. https://arxiv.org/abs/2510.01451
82. Motwani, S. R. et al. (2024). Secret Collusion among AI Agents. https://arxiv.org/abs/2402.07510
83. Fish, S., Gonczarowski, Y., Shorrer, R. (2024). Algorithmic Collusion by Large Language Models. https://arxiv.org/abs/2404.00806
84. Hammond, L. et al. (2025). Multi-Agent Risks from Advanced AI. https://arxiv.org/abs/2502.14143
85. Panickssery, A., Bowman, S., Feng, S. (2024). LLM Evaluators Recognize and Favor Their Own Generations. https://arxiv.org/abs/2404.13076
86. Han, B., Zhang, S. (2025). LLM Multi-Agent Systems Based on Blackboard Architecture. https://arxiv.org/abs/2507.01701
87. Salemi, A. et al. (2025). LLM-Based Multi-Agent Blackboard System for Information Discovery. https://arxiv.org/abs/2510.01285
88. Terrarium: Revisiting the Blackboard for Multi-Agent Safety, Privacy, and Security Studies (2025). https://arxiv.org/abs/2510.14312
89. Grötschla, F. et al. (2025). AgentsNet. https://arxiv.org/abs/2507.08616
90. Zheng, Y. et al. (2025). Thought Communication in Multiagent Collaboration. https://arxiv.org/abs/2510.20733
91. Korbak, T., Balesni, M. et al. (2025). Chain of Thought Monitorability. https://arxiv.org/abs/2507.11473
92. Park, J. S. et al. (2024). Generative Agent Simulations of 1,000 People. https://arxiv.org/abs/2411.10109
93. The Wisdom of Crowds (Surowiecki) overview. https://en.wikipedia.org/wiki/The_Wisdom_of_Crowds
94. Lorenz, J. et al. (2011). How social influence can undermine the wisdom of crowd effect. https://pmc.ncbi.nlm.nih.gov/articles/PMC3107299/
95. Bikhchandani, S., Hirshleifer, D., Welch, I. (1992). A Theory of Fads, Fashion, Custom, and Cultural Change as Informational Cascades. https://dx.doi.org/10.1086/261849
96. Dalkey, N. (1969). The Delphi Method: An Experimental Study of Group Opinion (RAND RM-5888). https://www.rand.org/pubs/research_memoranda/RM5888.html
97. Van de Ven, A., Delbecq, A. (1974). The Effectiveness of Nominal, Delphi, and Interacting Group Decision Making Processes. https://www.jstor.org/stable/255641
98. Stanford Encyclopedia of Philosophy: Jury Theorems. https://plato.stanford.edu/archives/sum2025/entries/jury-theorems/
99. Ladha, K. (1995). Information pooling through majority-rule voting: Condorcet's jury theorem with correlated votes. https://www.sciencedirect.com/science/article/abs/pii/016726819400068P
100. Hong, L., Page, S. (2004). Groups of diverse problem solvers can outperform groups of high-ability problem solvers. https://pmc.ncbi.nlm.nih.gov/articles/PMC528939/
101. Prelec, D. (2004). A Bayesian Truth Serum for Subjective Data. https://www.science.org/doi/10.1126/science.1102081
102. Prelec, D., Seung, H. S., McCoy, J. (2017). A solution to the single-question crowd wisdom problem. https://www.nature.com/articles/nature21054
103. Miller, N., Resnick, P., Zeckhauser, R. (2005). Eliciting Informative Feedback: The Peer-Prediction Method. https://dl.acm.org/doi/10.1287/mnsc.1050.0379
104. Kahng, A., Mackenzie, S., Procaccia, A. Liquid Democracy: An Algorithmic Perspective (JAIR). https://jair.org/index.php/jair/article/download/12261/26671
105. Lalley, S., Weyl, E. G. Quadratic Voting. https://arxiv.org/abs/1409.0264
106. Conviction Voting (Giveth / Commons Stack explainer). https://medium.com/giveth/conviction-voting-34019bd17b10
107. Hanson, R. Futarchy: Vote Values, But Bet Beliefs. https://mason.gmu.edu/~rhanson/futarchy.html
108. Arrow, K. et al. (2008). The Promise of Prediction Markets. https://www.science.org/doi/10.1126/science.1157679
109. Meta Stack Exchange: How are the reputation thresholds decided? https://meta.stackexchange.com/questions/353820/how-are-the-reputation-thresholds-decided
110. Slashdot moderation and meta-moderation. https://slashdot.org/moderation.shtml
111. Cortes, C., Lawrence, N. (2021). Inconsistency in Conference Peer Review: Revisiting the 2014 NeurIPS Experiment. https://arxiv.org/abs/2109.09774
112. PageRank (overview of Brin & Page's damped random surfer). https://en.wikipedia.org/wiki/PageRank
113. Kamvar, S., Schlosser, M., Garcia-Molina, H. (2003). The EigenTrust Algorithm. https://doi.org/10.1145/775152.775242
114. Levien, R. Advogato trust metric HOWTO. http://levien.com/free/tmetric-HOWTO.html
115. Douceur, J. (2002). The Sybil Attack. https://www.microsoft.com/en-us/research/wp-content/uploads/2002/01/IPTPS2002.pdf
116. Yu, H. et al. (2008). SybilLimit. https://www.comp.nus.edu.sg/~yuhf/yuh-sybillimit.pdf
117. Dwork, C., Naor, M. (1992). Pricing via Processing or Combatting Junk Mail. https://www.microsoft.com/en-us/research/publication/pricing-via-processing-or-combatting-junk-mail/
118. Hashcash (Back, 1997/2002) overview. https://en.wikipedia.org/wiki/Hashcash
119. Woolley, A. W. et al. (2010). Evidence for a Collective Intelligence Factor in the Performance of Human Groups. https://www.science.org/doi/10.1126/science.1193147
120. Zhou, W.-X., Sornette, D., Hill, R., Dunbar, R. (2005). Discrete hierarchical organization of social group sizes. https://arxiv.org/abs/cond-mat/0403299
121. Team Topologies: Key Concepts. https://teamtopologies.com/key-concepts
122. Sociocracy For All: Sociocracy (circles, consent, double-linking). https://www.sociocracyforall.org/sociocracy/
123. Holacracy Constitution. https://www.holacracy.org/constitution/
124. Boyd, J. The Essence of Winning and Losing. https://ooda.de/media/john_boyd_-_the_essence_of_winning_and_losing.pdf
125. U.S. Army ADP 6-0, Mission Command / Command and Control. https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN47032-ADP_6-0-000-WEB-1.pdf
126. Ringelmann effect (overview). https://en.wikipedia.org/wiki/Ringelmann_effect
127. Latané, B., Williams, K., Harkins, S. (1979). Many hands make light the work. https://psycnet.apa.org/record/1980-30335-001
128. Karau, S., Williams, K. (1993). Social loafing: A meta-analytic review and theoretical integration. https://psycnet.apa.org/record/1994-33384-001
129. Edmondson, A. (1999). Psychological Safety and Learning Behavior in Work Teams. https://www.jstor.org/stable/2666999
130. Google re:Work: Understand team effectiveness (Project Aristotle). https://rework.withgoogle.com/intl/en/guides/understand-team-effectiveness
131. Groupthink (Janis: symptoms and remedies) overview. https://en.wikipedia.org/wiki/Groupthink
132. Nemeth, C., Brown, K., Rogers, J. (2001). Devil's advocate versus authentic dissent. https://doi.org/10.1002/ejsp.58
133. Brooks's law (overview of The Mythical Man-Month). https://en.wikipedia.org/wiki/Brooks%27s_law
134. Cox, M., Arnold, G., Villamayor Tomás, S. (2010). A Review of Design Principles for Community-based Natural Resource Management. https://ecologyandsociety.org/vol15/iss4/art38/main.html

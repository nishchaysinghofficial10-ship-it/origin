# ORIGIN Research Timeline

Question: Which single-source shortest-path method wins on which graph topology at the tested sizes, does the machine-independent relaxation count agree with the wall-clock ranking, and where is the BFS candidate actually correct?

DAY 1 — 13:23:20  [init]
    Research project initialized: Which single-source shortest-path method wins on which graph topology at the tested sizes, does the machine-independent relaxation count agree with the wall-clock ranking, and where is the BFS candidate actually correct?

DAY 1 — 13:23:20  [transition]
    CREATED -> VALIDATING

DAY 1 — 13:23:20  [transition]
    VALIDATING -> PLANNING (mission spec validated)

DAY 1 — 13:23:20  [heartbeat]
    step 0 phase PLANNING | hyp 0 exp 0 evd 0 fail 0 | budget exp 0/40 compute 0.0s retries 0/8

DAY 1 — 13:23:20  [seeded]
    prior complexity results recorded as FACT with an explicit constant-factor caveat

DAY 1 — 13:23:20  [planned]
    Question decomposed into research tree; prior knowledge seeded

DAY 1 — 13:23:20  [transition]
    PLANNING -> FORMING_HYPOTHESES

DAY 1 — 13:23:20  [heartbeat]
    step 0 phase FORMING_HYPOTHESES | hyp 0 exp 0 evd 0 fail 0 | budget exp 0/40 compute 0.0s retries 0/8

DAY 1 — 13:23:20  [hypothesis]
    hyp_f3a5a9f693: Dijkstra with a binary heap is fastest on sparse random graphs at the tested sizes.

DAY 1 — 13:23:20  [hypothesis]
    hyp_6076ea0451: The array-scan Dijkstra beats the heap variant on dense graphs, where the scan cost is amortised.

DAY 1 — 13:23:20  [hypothesis]
    hyp_96edc044f0: Bellman-Ford performs the most edge relaxations of any candidate on every tested topology.

DAY 1 — 13:23:20  [hypothesis]
    hyp_e6bc85dbcd: SPFA performs fewer relaxations than Bellman-Ford on sparse random graphs.

DAY 1 — 13:23:20  [hypothesis]
    hyp_0eae29898f: The BFS candidate returns correct distances on unit-weight graphs and incorrect distances on every weighted topology.

DAY 1 — 13:23:20  [experiment_proposal]
    prop_e31021938f: candidate design accepted (algorithms=['dijkstra_heap', 'dijkstra_array', 'bellman_ford', 'spfa', 'bfs_unit'], regimes=['sparse_random', 'dense_random']); ORIGIN sets seed, timeout and scope at execution time

DAY 1 — 13:23:20  [counterargument]
    prop_8abe6e9c96 against hyp_f3a5a9f693: Timing rankings at these sizes may be dominated by interpreter overhead rather than algorithmic behaviour.

DAY 1 — 13:23:20  [knowledge_gap]
    prop_a466f66485: Comparison and move counts are not measured, so rankings cannot be separated from constant factors.

DAY 1 — 13:23:20  [proposals_reviewed]
    3 accepted, 0 rejected from mock; full audit in logs/proposals.jsonl

DAY 1 — 13:23:20  [transition]
    FORMING_HYPOTHESES -> SELECTING_NEXT_ACTION

DAY 1 — 13:23:20  [heartbeat]
    step 0 phase SELECTING_NEXT_ACTION | hyp 5 exp 0 evd 0 fail 0 | budget exp 0/40 compute 0.0s retries 0/8

DAY 1 — 13:23:20  [transition]
    SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT

DAY 1 — 13:23:20  [decision]
    [select_investigation] chose: hyp_0eae29898f — highest expected information gain per unit cost; experiment co-tests 5 hypothesis(es)

DAY 1 — 13:23:20  [transition]
    DESIGNING_EXPERIMENT -> EXECUTING

DAY 1 — 13:23:20  [experiment_started]
    exp_de9672a659: Benchmark round 1 covering 5 hypothesis(es)

DAY 1 — 13:23:24  [experiment_completed]
    exp_de9672a659 completed in 3.8s (40 measurements)

DAY 1 — 13:23:24  [transition]
    EXECUTING -> ANALYZING

DAY 1 — 13:23:24  [correctness_boundary]
    bfs_unit is INCORRECT on 'dense_random'; it is excluded from rankings there

DAY 1 — 13:23:24  [correctness_boundary]
    bfs_unit is INCORRECT on 'grid_2d'; it is excluded from rankings there

DAY 1 — 13:23:24  [correctness_boundary]
    bfs_unit is INCORRECT on 'sparse_random'; it is excluded from rankings there

DAY 1 — 13:23:24  [analysis]
    exp_de9672a659 analyzed; regime winners: {'sparse_random': 'spfa', 'dense_random': 'dijkstra_heap', 'grid_2d': 'spfa', 'unit_weight': 'spfa'}

DAY 1 — 13:23:24  [transition]
    ANALYZING -> UPDATING_KNOWLEDGE

DAY 1 — 13:23:24  [transition]
    UPDATING_KNOWLEDGE -> SELECTING_NEXT_ACTION

DAY 1 — 13:23:24  [heartbeat]
    step 0 phase SELECTING_NEXT_ACTION | hyp 5 exp 1 evd 6 fail 3 | budget exp 1/40 compute 3.8s retries 0/8

DAY 1 — 13:23:24  [transition]
    SELECTING_NEXT_ACTION -> CRITICIZING (no pending hypotheses remain)

DAY 1 — 13:23:24  [heartbeat]
    step 1 phase CRITICIZING | hyp 5 exp 1 evd 6 fail 3 | budget exp 1/40 compute 3.8s retries 0/8

DAY 1 — 13:23:24  [decision]
    [critic_replication] chose: hyp_96edc044f0 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 13:23:24  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 13:23:24  [experiment_started]
    exp_80c64940b6: Replication of hyp_96edc044f0

DAY 1 — 13:23:27  [experiment_completed]
    exp_80c64940b6 completed in 2.9s (20 measurements)

DAY 1 — 13:23:27  [replicated]
    hyp_96edc044f0 survived independent replication

DAY 1 — 13:23:27  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 13:23:27  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:23:27  [heartbeat]
    step 2 phase CRITICIZING | hyp 5 exp 2 evd 7 fail 3 | budget exp 2/40 compute 6.7s retries 0/8

DAY 1 — 13:23:27  [decision]
    [critic_replication] chose: hyp_e6bc85dbcd — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 13:23:27  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 13:23:27  [experiment_started]
    exp_3079fc8021: Replication of hyp_e6bc85dbcd

DAY 1 — 13:23:30  [experiment_completed]
    exp_3079fc8021 completed in 3.0s (20 measurements)

DAY 1 — 13:23:30  [replicated]
    hyp_e6bc85dbcd survived independent replication

DAY 1 — 13:23:30  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 13:23:30  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:23:30  [heartbeat]
    step 3 phase CRITICIZING | hyp 5 exp 3 evd 8 fail 3 | budget exp 3/40 compute 9.7s retries 0/8

DAY 1 — 13:23:30  [decision]
    [critic_replication] chose: hyp_0eae29898f — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 13:23:30  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 13:23:30  [experiment_started]
    exp_6bd2d789f8: Replication of hyp_0eae29898f

DAY 1 — 13:23:33  [experiment_completed]
    exp_6bd2d789f8 completed in 3.1s (20 measurements)

DAY 1 — 13:23:33  [replicated]
    hyp_0eae29898f survived independent replication

DAY 1 — 13:23:33  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 13:23:33  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:23:33  [heartbeat]
    step 4 phase CRITICIZING | hyp 5 exp 4 evd 10 fail 3 | budget exp 4/40 compute 12.8s retries 0/8

DAY 1 — 13:23:33  [falsification]
    hyp_96edc044f0: no probeable predictions for this hypothesis (its prediction types cannot be evaluated at boundary/unseen conditions)

DAY 1 — 13:23:33  [heartbeat]
    step 5 phase CRITICIZING | hyp 5 exp 4 evd 10 fail 3 | budget exp 4/40 compute 12.8s retries 0/8

DAY 1 — 13:23:33  [decision]
    [critic_falsification] chose: hyp_e6bc85dbcd — falsification probes: boundary:sparse_random, scope:long_chain, scope:scale_free

DAY 1 — 13:23:33  [transition]
    CRITICIZING -> FALSIFYING

DAY 1 — 13:23:33  [experiment_started]
    exp_42efd0db8f: Falsification probe of hyp_e6bc85dbcd

DAY 1 — 13:23:34  [experiment_completed]
    exp_42efd0db8f completed in 1.1s (15 measurements)

DAY 1 — 13:23:34  [falsification]
    hyp_e6bc85dbcd probe survived: [boundary:sparse_random] confirmed: spfa performed 9,907 relaxations vs bellman_ford 42,980 on 'sparse_random' (+77%); exact counts, machine-independent [n=1024

DAY 1 — 13:23:34  [transition]
    FALSIFYING -> UPDATING_KNOWLEDGE

DAY 1 — 13:23:34  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:23:34  [heartbeat]
    step 6 phase CRITICIZING | hyp 5 exp 5 evd 10 fail 3 | budget exp 5/40 compute 13.9s retries 0/8

DAY 1 — 13:23:34  [decision]
    [critic_falsification] chose: hyp_0eae29898f — falsification probes: boundary:unit_weight, scope:long_chain, scope:scale_free

DAY 1 — 13:23:34  [transition]
    CRITICIZING -> FALSIFYING

DAY 1 — 13:23:34  [experiment_started]
    exp_31f8e1690f: Falsification probe of hyp_0eae29898f

DAY 1 — 13:23:35  [experiment_completed]
    exp_31f8e1690f completed in 1.0s (15 measurements)

DAY 1 — 13:23:35  [falsification]
    hyp_0eae29898f probe survived: [boundary:unit_weight] confirmed: bfs_unit on 'unit_weight' returned correct distances [n=1024, 5 trials] | [scope:long_chain] refuted: bfs_unit on 'long_chain'

DAY 1 — 13:23:35  [transition]
    FALSIFYING -> UPDATING_KNOWLEDGE

DAY 1 — 13:23:35  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:23:35  [heartbeat]
    step 7 phase CRITICIZING | hyp 5 exp 6 evd 10 fail 3 | budget exp 6/40 compute 14.8s retries 0/8

DAY 1 — 13:23:35  [accepted]
    hyp_e6bc85dbcd ACCEPTED_WITH_SCOPE — holds at n<=2x tested sizes on its original topology; extends to ['long_chain', 'scale_free']

DAY 1 — 13:23:35  [accepted]
    hyp_0eae29898f ACCEPTED_WITH_SCOPE — holds at n<=2x tested sizes on its original topology; does NOT extend to ['long_chain', 'scale_free']

DAY 1 — 13:23:35  [critic_review]
    Critic pass complete: 6 assumptions on record, 17 cautions, 6 recommended follow-ups

DAY 1 — 13:23:35  [heartbeat]
    step 8 phase CRITICIZING | hyp 5 exp 6 evd 10 fail 3 | budget exp 6/40 compute 14.8s retries 0/8

DAY 1 — 13:23:35  [synthesis]
    Research dossier and timeline written to reports/

DAY 1 — 13:23:35  [transition]
    CRITICIZING -> COMPLETED (no high-value next experiment remained)

DAY 1 — 13:23:35  [stopped]
    Mission COMPLETED: no high-value next experiment remained

DAY 1 — 13:23:35  [heartbeat]
    step 9 phase COMPLETED | hyp 5 exp 6 evd 10 fail 3 | budget exp 6/40 compute 14.8s retries 0/8

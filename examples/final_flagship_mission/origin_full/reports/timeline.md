# ORIGIN Research Timeline

Question: Which single-source shortest-path method wins on which graph topology at n<=512, does the machine-independent relaxation count agree with the wall-clock ranking, and under what precondition is the BFS candidate correct?

DAY 1 — 13:31:45  [init]
    Research project initialized: Which single-source shortest-path method wins on which graph topology at n<=512, does the machine-independent relaxation count agree with the wall-clock ranking, and under what precondition is the BFS candidate correct?

DAY 1 — 13:31:45  [transition]
    CREATED -> VALIDATING

DAY 1 — 13:31:45  [transition]
    VALIDATING -> PLANNING (mission spec validated)

DAY 1 — 13:31:45  [heartbeat]
    step 0 phase PLANNING | hyp 0 exp 0 evd 0 fail 0 | budget exp 0/40 compute 0.0s retries 0/8

DAY 1 — 13:31:45  [seeded]
    prior complexity results recorded as FACT with an explicit constant-factor caveat

DAY 1 — 13:31:45  [planned]
    Question decomposed into research tree; prior knowledge seeded

DAY 1 — 13:31:45  [transition]
    PLANNING -> FORMING_HYPOTHESES

DAY 1 — 13:31:45  [heartbeat]
    step 1 phase FORMING_HYPOTHESES | hyp 0 exp 0 evd 0 fail 0 | budget exp 0/40 compute 0.0s retries 0/8

DAY 1 — 13:31:45  [hypothesis]
    hyp_47f59f38cd: Dijkstra with a binary heap is fastest on sparse random graphs at the tested sizes.

DAY 1 — 13:31:45  [hypothesis]
    hyp_df0b968ddf: The array-scan Dijkstra beats the heap variant on dense graphs, where the scan cost is amortised.

DAY 1 — 13:31:45  [hypothesis]
    hyp_a155973991: Bellman-Ford performs the most edge relaxations of any candidate on every tested topology.

DAY 1 — 13:31:45  [hypothesis]
    hyp_ff3e742ca3: SPFA performs fewer relaxations than Bellman-Ford on sparse random graphs.

DAY 1 — 13:31:45  [hypothesis]
    hyp_dfa38e8bf8: The BFS candidate returns correct distances on unit-weight graphs and incorrect distances on every weighted topology.

DAY 1 — 13:31:45  [experiment_proposal]
    prop_e31021938f: candidate design accepted (algorithms=['dijkstra_heap', 'dijkstra_array', 'bellman_ford', 'spfa', 'bfs_unit'], regimes=['sparse_random', 'dense_random']); ORIGIN sets seed, timeout and scope at execution time

DAY 1 — 13:31:45  [counterargument]
    prop_39c13e9d1b against hyp_47f59f38cd: Timing rankings at these sizes may be dominated by interpreter overhead rather than algorithmic behaviour.

DAY 1 — 13:31:45  [knowledge_gap]
    prop_a466f66485: Comparison and move counts are not measured, so rankings cannot be separated from constant factors.

DAY 1 — 13:31:45  [proposals_reviewed]
    3 accepted, 0 rejected from mock; full audit in logs/proposals.jsonl

DAY 1 — 13:31:45  [transition]
    FORMING_HYPOTHESES -> SELECTING_NEXT_ACTION

DAY 1 — 13:31:45  [heartbeat]
    step 2 phase SELECTING_NEXT_ACTION | hyp 5 exp 0 evd 0 fail 0 | budget exp 0/40 compute 0.0s retries 0/8

DAY 1 — 13:31:45  [transition]
    SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT

DAY 1 — 13:31:45  [decision]
    [select_investigation] chose: hyp_dfa38e8bf8 — highest expected information gain per unit cost; experiment co-tests 5 hypothesis(es)

DAY 1 — 13:31:45  [transition]
    DESIGNING_EXPERIMENT -> EXECUTING

DAY 1 — 13:31:45  [experiment_started]
    exp_f6219e9785: Benchmark round 1 covering 5 hypothesis(es)

DAY 1 — 13:31:48  [experiment_completed]
    exp_f6219e9785 completed in 2.9s (40 measurements)

DAY 1 — 13:31:48  [transition]
    EXECUTING -> ANALYZING

DAY 1 — 13:31:48  [correctness_boundary]
    bfs_unit is INCORRECT on 'dense_random'; it is excluded from rankings there

DAY 1 — 13:31:48  [correctness_boundary]
    bfs_unit is INCORRECT on 'grid_2d'; it is excluded from rankings there

DAY 1 — 13:31:48  [correctness_boundary]
    bfs_unit is INCORRECT on 'sparse_random'; it is excluded from rankings there

DAY 1 — 13:31:48  [analysis]
    exp_f6219e9785 analyzed; regime winners: {'sparse_random': 'spfa', 'dense_random': 'dijkstra_heap', 'grid_2d': 'spfa', 'unit_weight': 'spfa'}

DAY 1 — 13:31:48  [transition]
    ANALYZING -> UPDATING_KNOWLEDGE

DAY 1 — 13:31:48  [transition]
    UPDATING_KNOWLEDGE -> SELECTING_NEXT_ACTION

DAY 1 — 13:31:48  [heartbeat]
    step 3 phase SELECTING_NEXT_ACTION | hyp 5 exp 1 evd 6 fail 5 | budget exp 1/40 compute 2.9s retries 0/8

DAY 1 — 13:31:48  [transition]
    SELECTING_NEXT_ACTION -> CRITICIZING (no pending hypotheses remain)

DAY 1 — 13:31:48  [heartbeat]
    step 4 phase CRITICIZING | hyp 5 exp 1 evd 6 fail 5 | budget exp 1/40 compute 2.9s retries 0/8

DAY 1 — 13:31:48  [decision]
    [critic_replication] chose: hyp_a155973991 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 13:31:48  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 13:31:48  [experiment_started]
    exp_5ddb272042: Replication of hyp_a155973991

DAY 1 — 13:31:50  [experiment_completed]
    exp_5ddb272042 completed in 2.7s (20 measurements)

DAY 1 — 13:31:50  [replicated]
    hyp_a155973991 survived independent replication

DAY 1 — 13:31:50  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 13:31:50  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:31:50  [heartbeat]
    step 5 phase CRITICIZING | hyp 5 exp 2 evd 7 fail 5 | budget exp 2/40 compute 5.6s retries 0/8

DAY 1 — 13:31:50  [decision]
    [critic_replication] chose: hyp_ff3e742ca3 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 13:31:50  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 13:31:50  [experiment_started]
    exp_4ef2060bc4: Replication of hyp_ff3e742ca3

DAY 1 — 13:31:53  [experiment_completed]
    exp_4ef2060bc4 completed in 2.7s (20 measurements)

DAY 1 — 13:31:53  [replicated]
    hyp_ff3e742ca3 survived independent replication

DAY 1 — 13:31:53  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 13:31:53  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:31:53  [heartbeat]
    step 6 phase CRITICIZING | hyp 5 exp 3 evd 8 fail 5 | budget exp 3/40 compute 8.3s retries 0/8

DAY 1 — 13:31:53  [decision]
    [critic_replication] chose: hyp_dfa38e8bf8 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 13:31:53  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 13:31:53  [experiment_started]
    exp_e36d780531: Replication of hyp_dfa38e8bf8

DAY 1 — 13:31:56  [experiment_completed]
    exp_e36d780531 completed in 2.6s (20 measurements)

DAY 1 — 13:31:56  [replicated]
    hyp_dfa38e8bf8 survived independent replication

DAY 1 — 13:31:56  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 13:31:56  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:31:56  [heartbeat]
    step 7 phase CRITICIZING | hyp 5 exp 4 evd 10 fail 5 | budget exp 4/40 compute 10.8s retries 0/8

DAY 1 — 13:31:56  [falsification]
    hyp_a155973991: no probeable predictions for this hypothesis (its prediction types cannot be evaluated at boundary/unseen conditions)

DAY 1 — 13:31:56  [heartbeat]
    step 8 phase CRITICIZING | hyp 5 exp 4 evd 10 fail 5 | budget exp 4/40 compute 10.8s retries 0/8

DAY 1 — 13:31:56  [decision]
    [critic_falsification] chose: hyp_ff3e742ca3 — falsification probes: boundary:sparse_random, scope:long_chain, scope:scale_free

DAY 1 — 13:31:56  [transition]
    CRITICIZING -> FALSIFYING

DAY 1 — 13:31:56  [experiment_started]
    exp_549fb806e7: Falsification probe of hyp_ff3e742ca3

DAY 1 — 13:31:57  [experiment_completed]
    exp_549fb806e7 completed in 1.0s (15 measurements)

DAY 1 — 13:31:57  [falsification]
    hyp_ff3e742ca3 probe survived: [boundary:sparse_random] confirmed: spfa performed 9,907 relaxations vs bellman_ford 42,980 on 'sparse_random' (+77%); exact counts, machine-independent [n=1024

DAY 1 — 13:31:57  [transition]
    FALSIFYING -> UPDATING_KNOWLEDGE

DAY 1 — 13:31:57  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:31:57  [heartbeat]
    step 9 phase CRITICIZING | hyp 5 exp 5 evd 10 fail 5 | budget exp 5/40 compute 11.8s retries 0/8

DAY 1 — 13:31:57  [decision]
    [critic_falsification] chose: hyp_dfa38e8bf8 — falsification probes: boundary:unit_weight, scope:long_chain, scope:scale_free

DAY 1 — 13:31:57  [transition]
    CRITICIZING -> FALSIFYING

DAY 1 — 13:31:57  [experiment_started]
    exp_9b2777924f: Falsification probe of hyp_dfa38e8bf8

DAY 1 — 13:31:58  [experiment_completed]
    exp_9b2777924f completed in 1.0s (15 measurements)

DAY 1 — 13:31:58  [falsification]
    hyp_dfa38e8bf8 probe survived: [boundary:unit_weight] confirmed: bfs_unit on 'unit_weight' returned correct distances [n=1024, 5 trials] | [scope:long_chain] refuted: bfs_unit on 'long_chain'

DAY 1 — 13:31:58  [transition]
    FALSIFYING -> UPDATING_KNOWLEDGE

DAY 1 — 13:31:58  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 13:31:58  [heartbeat]
    step 10 phase CRITICIZING | hyp 5 exp 6 evd 10 fail 5 | budget exp 6/40 compute 12.8s retries 0/8

DAY 1 — 13:31:58  [accepted]
    hyp_ff3e742ca3 ACCEPTED_WITH_SCOPE — holds at n<=2x tested sizes on its original topology; extends to ['long_chain', 'scale_free']

DAY 1 — 13:31:58  [accepted]
    hyp_dfa38e8bf8 ACCEPTED_WITH_SCOPE — holds at n<=2x tested sizes on its original topology; does NOT extend to ['long_chain', 'scale_free']

DAY 1 — 13:31:58  [critic_review]
    Critic pass complete: 6 assumptions on record, 9 cautions, 4 recommended follow-ups

DAY 1 — 13:31:58  [heartbeat]
    step 11 phase CRITICIZING | hyp 5 exp 6 evd 10 fail 5 | budget exp 6/40 compute 12.8s retries 0/8

DAY 1 — 13:31:58  [synthesis]
    Research dossier and timeline written to reports/

DAY 1 — 13:31:58  [transition]
    CRITICIZING -> COMPLETED (no high-value next experiment remained)

DAY 1 — 13:31:58  [stopped]
    Mission COMPLETED: no high-value next experiment remained

DAY 1 — 13:31:58  [heartbeat]
    step 12 phase COMPLETED | hyp 5 exp 6 evd 10 fail 5 | budget exp 6/40 compute 12.8s retries 0/8

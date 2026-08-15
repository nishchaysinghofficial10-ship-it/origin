# ORIGIN Research Timeline

Question: Which comparison-sort strategy is most efficient across input regimes (random, nearly-sorted, reversed, few-unique) in pure Python at n<=1600, and can a hybrid synthesized from the evidence beat the base algorithms?

DAY 1 — 12:07:29  [init]
    Research project initialized: Which comparison-sort strategy is most efficient across input regimes (random, nearly-sorted, reversed, few-unique) in pure Python at n<=1600, and can a hybrid synthesized from the evidence beat the base algorithms?

DAY 1 — 12:07:29  [planned]
    Question decomposed into research tree; prior knowledge seeded

DAY 1 — 12:07:29  [hypothesis]
    hyp_d4e20c8a29: Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes.

DAY 1 — 12:07:29  [hypothesis]
    hyp_e8add5b17c: Merge sort is the fastest pure-Python candidate on random input.

DAY 1 — 12:07:29  [hypothesis]
    hyp_c8cb718328: Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input.

DAY 1 — 12:07:29  [hypothesis]
    hyp_a2e585909f: Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.

DAY 1 — 12:07:29  [decision]
    [select_investigation] chose: hyp_d4e20c8a29 — highest expected information gain per unit cost; experiment co-tests 4 hypothesis(es)

DAY 1 — 12:07:29  [experiment_started]
    exp_defeaebae2: Benchmark round 1 covering 4 hypothesis(es)

DAY 1 — 12:07:29  [experiment_completed]
    exp_defeaebae2 completed in 0.6s (32 measurements)

DAY 1 — 12:07:29  [hypothesis_generated]
    New candidate synthesized from evidence: hyp_7850a311fa (hybrid_sort)

DAY 1 — 12:07:29  [analysis]
    exp_defeaebae2 analyzed; regime winners: {'random': 'quick_sort', 'nearly_sorted': 'insertion_sort', 'reversed': 'quick_sort', 'few_unique': 'quick_sort'}

DAY 1 — 12:07:29  [decision]
    [select_investigation] chose: hyp_7850a311fa — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)

DAY 1 — 12:07:29  [experiment_started]
    exp_dfae537d8f: Benchmark round 2 covering 1 hypothesis(es)

DAY 1 — 12:07:30  [experiment_completed]
    exp_dfae537d8f completed in 0.6s (40 measurements)

DAY 1 — 12:07:30  [analysis]
    exp_dfae537d8f analyzed; regime winners: {'random': 'hybrid_sort', 'nearly_sorted': 'insertion_sort', 'reversed': 'quick_sort', 'few_unique': 'hybrid_sort'}

DAY 1 — 12:07:30  [decision]
    [critic_replication] chose: hyp_d4e20c8a29 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 12:07:30  [experiment_started]
    exp_d6590ff7d6: Replication of hyp_d4e20c8a29

DAY 1 — 12:07:30  [experiment_completed]
    exp_d6590ff7d6 completed in 0.5s (16 measurements)

DAY 1 — 12:07:30  [replicated]
    hyp_d4e20c8a29 survived independent replication

DAY 1 — 12:07:30  [decision]
    [critic_replication] chose: hyp_c8cb718328 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 12:07:30  [experiment_started]
    exp_21ee7d3058: Replication of hyp_c8cb718328

DAY 1 — 12:07:31  [experiment_completed]
    exp_21ee7d3058 completed in 0.5s (16 measurements)

DAY 1 — 12:07:31  [replicated]
    hyp_c8cb718328 survived independent replication

DAY 1 — 12:07:31  [decision]
    [critic_replication] chose: hyp_a2e585909f — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 12:07:31  [experiment_started]
    exp_89bfcf883b: Replication of hyp_a2e585909f

DAY 1 — 12:07:31  [experiment_completed]
    exp_89bfcf883b completed in 0.5s (16 measurements)

DAY 1 — 12:07:31  [decision]
    [critic_replication] chose: hyp_7850a311fa — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 12:07:31  [experiment_started]
    exp_03c68e9b8c: Replication of hyp_7850a311fa

DAY 1 — 12:07:32  [experiment_completed]
    exp_03c68e9b8c completed in 0.5s (20 measurements)

DAY 1 — 12:07:32  [replicated]
    hyp_7850a311fa survived independent replication

DAY 1 — 12:07:32  [critic_review]
    Critic pass complete: 5 assumptions on record, 2 cautions, 6 recommended follow-ups

DAY 1 — 12:07:32  [synthesis]
    Research dossier and timeline written to reports/

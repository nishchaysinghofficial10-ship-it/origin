# ORIGIN Research Timeline

Question: Which sorting strategy wins under which input regime, and what does the published literature claim about those tradeoffs?

DAY 1 — 20:49:33  [init]
    Research project initialized: Which sorting strategy wins under which input regime, and what does the published literature claim about those tradeoffs?

DAY 1 — 20:49:33  [retrieval]
    https://fixtures.invalid/adaptive-sorting → 200 text/plain 265B sha256:382f1a33ea66412f in 0.00s via fixture [robots: not_checked] (content treated as UNTRUSTED)

DAY 1 — 20:49:33  [source_ingested]
    src_b2481390ad: Adaptive Sorting Notes (https://fixtures.invalid/adaptive-sorting) — reliability 0.25 from 4 recorded reason(s); content is UNTRUSTED

DAY 1 — 20:49:33  [claim_extracted]
    clm_9ba0267aea [comparative, SPECULATION, conf 0.25] from src_b2481390ad@24: Insertion sort is faster than merge sort on nearly-sorted input because the number of inve

DAY 1 — 20:49:33  [claim_extracted]
    clm_cdef10f89c [descriptive, SPECULATION, conf 0.25] from src_b2481390ad@163: Merge sort is a stable comparison sort with guaranteed n log n behaviour on every input di

DAY 1 — 20:49:33  [retrieval_failed]
    RetrievalError for https://fixtures.invalid/intermittent: TimeoutError fetching https://fixtures.invalid/intermittent: simulated transient failure 1/2

DAY 1 — 20:49:33  [transition]
    CREATED -> VALIDATING

DAY 1 — 20:49:33  [transition]
    VALIDATING -> PLANNING (mission spec validated)

DAY 1 — 20:49:33  [heartbeat]
    step 0 phase PLANNING | hyp 0 exp 0 evd 0 fail 0 | budget exp 0/8 compute 0.0s retries 0/8

DAY 1 — 20:49:33  [planned]
    Question decomposed into research tree; prior knowledge seeded

DAY 1 — 20:49:33  [transition]
    PLANNING -> FORMING_HYPOTHESES

DAY 1 — 20:49:33  [heartbeat]
    step 0 phase FORMING_HYPOTHESES | hyp 0 exp 0 evd 0 fail 0 | budget exp 0/8 compute 0.0s retries 0/8

DAY 1 — 20:49:33  [retrieval_failed]
    RetrievalError for https://fixtures.invalid/intermittent: TimeoutError fetching https://fixtures.invalid/intermittent: simulated transient failure 2/2

DAY 1 — 20:49:33  [hypothesis]
    hyp_48de48fcea: Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes.

DAY 1 — 20:49:33  [hypothesis]
    hyp_fc15d13b1b: Merge sort is the fastest pure-Python candidate on random input.

DAY 1 — 20:49:33  [hypothesis]
    hyp_2be7e87921: Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input.

DAY 1 — 20:49:33  [hypothesis]
    hyp_db14df8458: Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.

DAY 1 — 20:49:33  [transition]
    FORMING_HYPOTHESES -> SELECTING_NEXT_ACTION

DAY 1 — 20:49:33  [heartbeat]
    step 0 phase SELECTING_NEXT_ACTION | hyp 4 exp 0 evd 0 fail 0 | budget exp 0/8 compute 0.0s retries 0/8

DAY 1 — 20:49:33  [retrieval]
    https://fixtures.invalid/intermittent → 200 text/plain 265B sha256:382f1a33ea66412f in 0.00s via fixture [robots: not_checked] (content treated as UNTRUSTED)

DAY 1 — 20:49:33  [ingest_skipped]
    https://fixtures.invalid/intermittent duplicates src_b2481390ad by content hash 382f1a33ea66412f

DAY 1 — 20:49:33  [transition]
    SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT

DAY 1 — 20:49:33  [decision]
    [select_investigation] chose: hyp_48de48fcea — highest expected information gain per unit cost; experiment co-tests 4 hypothesis(es)

DAY 1 — 20:49:33  [transition]
    DESIGNING_EXPERIMENT -> EXECUTING

DAY 1 — 20:49:33  [experiment_started]
    exp_066779c791: Benchmark round 1 covering 4 hypothesis(es)

DAY 1 — 20:49:33  [experiment_completed]
    exp_066779c791 completed in 0.1s (40 measurements)

DAY 1 — 20:49:33  [transition]
    EXECUTING -> ANALYZING

DAY 1 — 20:49:33  [hypothesis_generated]
    New candidate synthesized from evidence: hyp_5542e8d61c (hybrid_sort)

DAY 1 — 20:49:33  [analysis]
    exp_066779c791 analyzed; regime winners: {'random': 'quick_sort', 'nearly_sorted': 'insertion_sort', 'reversed': 'quick_sort', 'few_unique': 'shell_sort'}

DAY 1 — 20:49:33  [transition]
    ANALYZING -> UPDATING_KNOWLEDGE

DAY 1 — 20:49:33  [transition]
    UPDATING_KNOWLEDGE -> SELECTING_NEXT_ACTION

DAY 1 — 20:49:33  [heartbeat]
    step 0 phase SELECTING_NEXT_ACTION | hyp 5 exp 1 evd 7 fail 1 | budget exp 1/8 compute 0.1s retries 0/8

DAY 1 — 20:49:33  [transition]
    SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT

DAY 1 — 20:49:33  [decision]
    [select_investigation] chose: hyp_5542e8d61c — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)

DAY 1 — 20:49:33  [transition]
    DESIGNING_EXPERIMENT -> EXECUTING

DAY 1 — 20:49:33  [experiment_started]
    exp_a582f67436: Benchmark round 2 covering 1 hypothesis(es)

DAY 1 — 20:49:33  [experiment_completed]
    exp_a582f67436 completed in 0.1s (48 measurements)

DAY 1 — 20:49:33  [transition]
    EXECUTING -> ANALYZING

DAY 1 — 20:49:33  [analysis]
    exp_a582f67436 analyzed; regime winners: {'random': 'quick_sort', 'nearly_sorted': 'insertion_sort', 'reversed': 'quick_sort', 'few_unique': 'shell_sort'}

DAY 1 — 20:49:33  [transition]
    ANALYZING -> UPDATING_KNOWLEDGE

DAY 1 — 20:49:33  [transition]
    UPDATING_KNOWLEDGE -> SELECTING_NEXT_ACTION

DAY 1 — 20:49:33  [heartbeat]
    step 1 phase SELECTING_NEXT_ACTION | hyp 5 exp 2 evd 9 fail 1 | budget exp 2/8 compute 0.1s retries 0/8

DAY 1 — 20:49:33  [transition]
    SELECTING_NEXT_ACTION -> CRITICIZING (no pending hypotheses remain)

DAY 1 — 20:49:33  [heartbeat]
    step 2 phase CRITICIZING | hyp 5 exp 2 evd 9 fail 1 | budget exp 2/8 compute 0.1s retries 0/8

DAY 1 — 20:49:33  [critic_review]
    Critic pass complete: 5 assumptions on record, 10 cautions, 9 recommended follow-ups

DAY 1 — 20:49:33  [heartbeat]
    step 3 phase CRITICIZING | hyp 5 exp 2 evd 9 fail 1 | budget exp 2/8 compute 0.1s retries 0/8

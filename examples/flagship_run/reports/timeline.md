# ORIGIN Research Timeline

Question: Under what input distributions and sizes does a hybrid merge/insertion sorting strategy outperform predefined baselines without violating correctness, and what insertion cutoff is optimal per regime?

DAY 1 — 19:51:05  [init]
    Research project initialized: Under what input distributions and sizes does a hybrid merge/insertion sorting strategy outperform predefined baselines without violating correctness, and what insertion cutoff is optimal per regime?

DAY 1 — 19:51:05  [transition]
    CREATED -> VALIDATING

DAY 1 — 19:51:05  [transition]
    VALIDATING -> PLANNING (mission spec validated)

DAY 1 — 19:51:05  [heartbeat]
    step 0 phase PLANNING | hyp 0 exp 0 evd 0 fail 0 | budget exp 0/100 compute 0.0s retries 0/8

DAY 1 — 19:51:05  [planned]
    Question decomposed into research tree; prior knowledge seeded

DAY 1 — 19:51:05  [transition]
    PLANNING -> FORMING_HYPOTHESES

DAY 1 — 19:51:05  [heartbeat]
    step 1 phase FORMING_HYPOTHESES | hyp 0 exp 0 evd 0 fail 0 | budget exp 0/100 compute 0.0s retries 0/8

DAY 1 — 19:51:05  [hypothesis]
    hyp_dbe5f386a7: Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes.

DAY 1 — 19:51:05  [hypothesis]
    hyp_fa035de7df: Merge sort is the fastest pure-Python candidate on random input.

DAY 1 — 19:51:05  [hypothesis]
    hyp_cae1c60f85: Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input.

DAY 1 — 19:51:05  [hypothesis]
    hyp_ad33a3dcb5: Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.

DAY 1 — 19:51:05  [hypothesis]
    hyp_40df9834c7 (llm_proposed, validated): Shell sort beats insertion sort on random input but not on nearly-sorted input at the tested sizes.

DAY 1 — 19:51:05  [hypothesis]
    hyp_f1699d47b3 (llm_proposed, validated): Heap sort beats shell sort on reversed input at the tested sizes.

DAY 1 — 19:51:05  [experiment_proposal]
    prop_68ed269780: candidate design accepted (algorithms=['insertion_sort', 'merge_sort', 'quick_sort', 'heap_sort', 'shell_sort'], regimes=['random', 'nearly_sorted']); ORIGIN sets seed, timeout and scope at execution time

DAY 1 — 19:51:05  [counterargument]
    prop_ae9b78e435 against hyp_dbe5f386a7: Timing rankings at these sizes may be dominated by interpreter overhead rather than algorithmic behaviour.

DAY 1 — 19:51:05  [knowledge_gap]
    prop_a466f66485: Comparison and move counts are not measured, so rankings cannot be separated from constant factors.

DAY 1 — 19:51:05  [proposals_reviewed]
    5 accepted, 0 rejected from mock; full audit in logs/proposals.jsonl

DAY 1 — 19:51:05  [transition]
    FORMING_HYPOTHESES -> SELECTING_NEXT_ACTION

DAY 1 — 19:51:05  [heartbeat]
    step 2 phase SELECTING_NEXT_ACTION | hyp 6 exp 0 evd 0 fail 0 | budget exp 0/100 compute 0.0s retries 0/8

DAY 1 — 19:51:05  [transition]
    SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT

DAY 1 — 19:51:05  [decision]
    [select_investigation] chose: hyp_dbe5f386a7 — highest expected information gain per unit cost; experiment co-tests 4 hypothesis(es)

DAY 1 — 19:51:05  [transition]
    DESIGNING_EXPERIMENT -> EXECUTING

DAY 1 — 19:51:05  [experiment_started]
    exp_c512323528: Benchmark round 1 covering 4 hypothesis(es)

DAY 1 — 19:51:17  [experiment_completed]
    exp_c512323528 completed in 12.0s (60 measurements)

DAY 1 — 19:51:17  [transition]
    EXECUTING -> ANALYZING

DAY 1 — 19:51:17  [hypothesis_generated]
    New candidate synthesized from evidence: hyp_38e7e1fe16 (hybrid_sort)

DAY 1 — 19:51:17  [analysis]
    exp_c512323528 analyzed; regime winners: {'random': 'quick_sort', 'nearly_sorted': 'insertion_sort', 'reversed': 'quick_sort', 'few_unique': 'quick_sort'}

DAY 1 — 19:51:17  [transition]
    ANALYZING -> UPDATING_KNOWLEDGE

DAY 1 — 19:51:17  [transition]
    UPDATING_KNOWLEDGE -> SELECTING_NEXT_ACTION

DAY 1 — 19:51:17  [heartbeat]
    step 3 phase SELECTING_NEXT_ACTION | hyp 7 exp 1 evd 7 fail 2 | budget exp 1/100 compute 12.0s retries 0/8

DAY 1 — 19:51:17  [transition]
    SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT

DAY 1 — 19:51:17  [decision]
    [select_investigation] chose: hyp_38e7e1fe16 — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)

DAY 1 — 19:51:17  [transition]
    DESIGNING_EXPERIMENT -> EXECUTING

DAY 1 — 19:51:17  [experiment_started]
    exp_48613ed686: Benchmark round 2 covering 1 hypothesis(es)

DAY 1 — 19:51:30  [experiment_completed]
    exp_48613ed686 completed in 12.3s (72 measurements)

DAY 1 — 19:51:30  [transition]
    EXECUTING -> ANALYZING

DAY 1 — 19:51:30  [hypothesis_generated]
    Parameter-sweep hypothesis pre-registered: hyp_bf17e1f36c

DAY 1 — 19:51:30  [analysis]
    exp_48613ed686 analyzed; regime winners: {'random': 'quick_sort', 'nearly_sorted': 'insertion_sort', 'reversed': 'quick_sort', 'few_unique': 'quick_sort'}

DAY 1 — 19:51:30  [transition]
    ANALYZING -> UPDATING_KNOWLEDGE

DAY 1 — 19:51:30  [transition]
    UPDATING_KNOWLEDGE -> SELECTING_NEXT_ACTION

DAY 1 — 19:51:30  [heartbeat]
    step 4 phase SELECTING_NEXT_ACTION | hyp 8 exp 2 evd 9 fail 2 | budget exp 2/100 compute 24.3s retries 0/8

DAY 1 — 19:51:30  [transition]
    SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT

DAY 1 — 19:51:30  [decision]
    [select_investigation] chose: hyp_bf17e1f36c — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)

DAY 1 — 19:51:30  [transition]
    DESIGNING_EXPERIMENT -> EXECUTING

DAY 1 — 19:51:30  [experiment_started]
    exp_42d46105c8: Benchmark round 3 covering 1 hypothesis(es)

DAY 1 — 19:51:30  [experiment_completed]
    exp_42d46105c8 completed in 0.8s (16 measurements)

DAY 1 — 19:51:30  [transition]
    EXECUTING -> ANALYZING

DAY 1 — 19:51:30  [analysis]
    Sweep exp_42d46105c8: cutoff optima random=16, nearly_sorted=64, reversed=8, few_unique=16

DAY 1 — 19:51:30  [analysis]
    exp_42d46105c8 analyzed; regime winners: {'random': 'cutoff 16', 'nearly_sorted': 'cutoff 64', 'reversed': 'cutoff 8', 'few_unique': 'cutoff 16'}

DAY 1 — 19:51:30  [transition]
    ANALYZING -> UPDATING_KNOWLEDGE

DAY 1 — 19:51:30  [transition]
    UPDATING_KNOWLEDGE -> SELECTING_NEXT_ACTION

DAY 1 — 19:51:30  [heartbeat]
    step 5 phase SELECTING_NEXT_ACTION | hyp 8 exp 3 evd 11 fail 2 | budget exp 3/100 compute 25.1s retries 0/8

DAY 1 — 19:51:30  [transition]
    SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT

DAY 1 — 19:51:30  [experiment_proposal_used]
    candidate design prop_68ed269780 instantiated for hyp_40df9834c7 with ORIGIN-controlled seed/timeout

DAY 1 — 19:51:30  [decision]
    [select_investigation] chose: hyp_40df9834c7 — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)

DAY 1 — 19:51:30  [transition]
    DESIGNING_EXPERIMENT -> EXECUTING

DAY 1 — 19:51:30  [experiment_started]
    exp_2593d8e300: Benchmark round 5 covering 1 hypothesis(es)

DAY 1 — 19:51:31  [experiment_completed]
    exp_2593d8e300 completed in 0.4s (20 measurements)

DAY 1 — 19:51:31  [transition]
    EXECUTING -> ANALYZING

DAY 1 — 19:51:31  [analysis]
    exp_2593d8e300 analyzed; regime winners: {'random': 'quick_sort', 'nearly_sorted': 'insertion_sort'}

DAY 1 — 19:51:31  [transition]
    ANALYZING -> UPDATING_KNOWLEDGE

DAY 1 — 19:51:31  [transition]
    UPDATING_KNOWLEDGE -> SELECTING_NEXT_ACTION

DAY 1 — 19:51:31  [heartbeat]
    step 6 phase SELECTING_NEXT_ACTION | hyp 8 exp 4 evd 12 fail 2 | budget exp 4/100 compute 25.5s retries 0/8

DAY 1 — 19:51:31  [transition]
    SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT

DAY 1 — 19:51:31  [decision]
    [select_investigation] chose: hyp_f1699d47b3 — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)

DAY 1 — 19:51:31  [transition]
    DESIGNING_EXPERIMENT -> EXECUTING

DAY 1 — 19:51:31  [experiment_started]
    exp_409be65fa9: Benchmark round 1 covering 1 hypothesis(es)

DAY 1 — 19:51:43  [experiment_completed]
    exp_409be65fa9 completed in 12.1s (60 measurements)

DAY 1 — 19:51:43  [transition]
    EXECUTING -> ANALYZING

DAY 1 — 19:51:43  [analysis]
    exp_409be65fa9 analyzed; regime winners: {'random': 'quick_sort', 'nearly_sorted': 'insertion_sort', 'reversed': 'quick_sort', 'few_unique': 'quick_sort'}

DAY 1 — 19:51:43  [transition]
    ANALYZING -> UPDATING_KNOWLEDGE

DAY 1 — 19:51:43  [transition]
    UPDATING_KNOWLEDGE -> SELECTING_NEXT_ACTION

DAY 1 — 19:51:43  [heartbeat]
    step 7 phase SELECTING_NEXT_ACTION | hyp 8 exp 5 evd 13 fail 3 | budget exp 5/100 compute 37.6s retries 0/8

DAY 1 — 19:51:43  [transition]
    SELECTING_NEXT_ACTION -> CRITICIZING (no pending hypotheses remain)

DAY 1 — 19:51:43  [heartbeat]
    step 8 phase CRITICIZING | hyp 8 exp 5 evd 13 fail 3 | budget exp 5/100 compute 37.6s retries 0/8

DAY 1 — 19:51:43  [decision]
    [critic_replication] chose: hyp_dbe5f386a7 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 19:51:43  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 19:51:43  [experiment_started]
    exp_dac3afe6aa: Replication of hyp_dbe5f386a7

DAY 1 — 19:51:55  [experiment_completed]
    exp_dac3afe6aa completed in 11.6s (20 measurements)

DAY 1 — 19:51:55  [replicated]
    hyp_dbe5f386a7 survived independent replication

DAY 1 — 19:51:55  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 19:51:55  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 19:51:55  [heartbeat]
    step 9 phase CRITICIZING | hyp 8 exp 6 evd 15 fail 3 | budget exp 6/100 compute 49.3s retries 0/8

DAY 1 — 19:51:55  [decision]
    [critic_replication] chose: hyp_cae1c60f85 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 19:51:55  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 19:51:55  [experiment_started]
    exp_ac020259d2: Replication of hyp_cae1c60f85

DAY 1 — 19:52:06  [experiment_completed]
    exp_ac020259d2 completed in 11.1s (20 measurements)

DAY 1 — 19:52:06  [replicated]
    hyp_cae1c60f85 survived independent replication

DAY 1 — 19:52:06  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 19:52:06  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 19:52:06  [heartbeat]
    step 10 phase CRITICIZING | hyp 8 exp 7 evd 17 fail 3 | budget exp 7/100 compute 60.4s retries 0/8

DAY 1 — 19:52:06  [decision]
    [critic_replication] chose: hyp_40df9834c7 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 19:52:06  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 19:52:06  [experiment_started]
    exp_13f5f8410a: Replication of hyp_40df9834c7

DAY 1 — 19:52:17  [experiment_completed]
    exp_13f5f8410a completed in 11.4s (20 measurements)

DAY 1 — 19:52:17  [replicated]
    hyp_40df9834c7 survived independent replication

DAY 1 — 19:52:17  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 19:52:17  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 19:52:17  [heartbeat]
    step 11 phase CRITICIZING | hyp 8 exp 8 evd 18 fail 3 | budget exp 8/100 compute 71.7s retries 0/8

DAY 1 — 19:52:17  [decision]
    [critic_replication] chose: hyp_38e7e1fe16 — critic refuses single-experiment support; independent replication with new seeds

DAY 1 — 19:52:17  [transition]
    CRITICIZING -> REPLICATING

DAY 1 — 19:52:17  [experiment_started]
    exp_1351d074bc: Replication of hyp_38e7e1fe16

DAY 1 — 19:52:28  [experiment_completed]
    exp_1351d074bc completed in 11.4s (24 measurements)

DAY 1 — 19:52:28  [replicated]
    hyp_38e7e1fe16 survived independent replication

DAY 1 — 19:52:28  [transition]
    REPLICATING -> UPDATING_KNOWLEDGE

DAY 1 — 19:52:28  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 19:52:28  [heartbeat]
    step 12 phase CRITICIZING | hyp 8 exp 9 evd 20 fail 3 | budget exp 9/100 compute 83.1s retries 0/8

DAY 1 — 19:52:28  [decision]
    [critic_falsification] chose: hyp_dbe5f386a7 — falsification probes: boundary:nearly_sorted, scope:sawtooth, scope:organ_pipe, boundary:random, scope:sawtooth, scope:organ_pipe

DAY 1 — 19:52:28  [transition]
    CRITICIZING -> FALSIFYING

DAY 1 — 19:52:28  [experiment_started]
    exp_9c23de511f: Falsification probe of hyp_dbe5f386a7

DAY 1 — 19:53:03  [experiment_completed]
    exp_9c23de511f completed in 34.7s (20 measurements)

DAY 1 — 19:53:03  [falsification]
    hyp_dbe5f386a7 probe survived: [boundary:nearly_sorted] confirmed: fastest_on on 'nearly_sorted' is insertion_sort (1.0 ms, margin 805% over quick_sort, separation 8.04 ms > required 1.07 ms)

DAY 1 — 19:53:03  [transition]
    FALSIFYING -> UPDATING_KNOWLEDGE

DAY 1 — 19:53:03  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 19:53:03  [heartbeat]
    step 13 phase CRITICIZING | hyp 8 exp 10 evd 20 fail 3 | budget exp 10/100 compute 117.9s retries 0/8

DAY 1 — 19:53:03  [decision]
    [critic_falsification] chose: hyp_cae1c60f85 — falsification probes: boundary:random, scope:sawtooth, scope:organ_pipe, boundary:reversed, scope:sawtooth, scope:organ_pipe

DAY 1 — 19:53:03  [transition]
    CRITICIZING -> FALSIFYING

DAY 1 — 19:53:03  [experiment_started]
    exp_98238f5fae: Falsification probe of hyp_cae1c60f85

DAY 1 — 19:53:59  [experiment_completed]
    exp_98238f5fae completed in 56.3s (20 measurements)

DAY 1 — 19:53:59  [falsification]
    hyp_cae1c60f85 probe survived: [boundary:random] confirmed: quick_sort is 0% off best on 'random' (limit 25%, uncertainty ±22%) [n=8192, 7 trials] | [scope:sawtooth] confirmed: quick_sort is 

DAY 1 — 19:53:59  [transition]
    FALSIFYING -> UPDATING_KNOWLEDGE

DAY 1 — 19:53:59  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 19:53:59  [heartbeat]
    step 14 phase CRITICIZING | hyp 8 exp 11 evd 20 fail 3 | budget exp 11/100 compute 174.1s retries 0/8

DAY 1 — 19:53:59  [decision]
    [critic_falsification] chose: hyp_40df9834c7 — falsification probes: boundary:random, scope:sawtooth, scope:organ_pipe

DAY 1 — 19:53:59  [transition]
    CRITICIZING -> FALSIFYING

DAY 1 — 19:53:59  [experiment_started]
    exp_6590a2f6db: Falsification probe of hyp_40df9834c7

DAY 1 — 19:54:34  [experiment_completed]
    exp_6590a2f6db completed in 34.7s (15 measurements)

DAY 1 — 19:54:34  [falsification]
    hyp_40df9834c7 probe survived: [boundary:random] confirmed: shell_sort vs insertion_sort on 'random': +2964% (needs >= 0.0%, decisive: gap 1526.07 ms > required 29.67 ms) [n=8192, 7 trials] |

DAY 1 — 19:54:34  [transition]
    FALSIFYING -> UPDATING_KNOWLEDGE

DAY 1 — 19:54:34  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 19:54:34  [heartbeat]
    step 15 phase CRITICIZING | hyp 8 exp 12 evd 20 fail 3 | budget exp 12/100 compute 208.9s retries 0/8

DAY 1 — 19:54:34  [decision]
    [critic_falsification] chose: hyp_38e7e1fe16 — falsification probes: boundary:random, scope:sawtooth, scope:organ_pipe, boundary:nearly_sorted, scope:sawtooth, scope:organ_pipe

DAY 1 — 19:54:34  [transition]
    CRITICIZING -> FALSIFYING

DAY 1 — 19:54:34  [experiment_started]
    exp_20b306145c: Falsification probe of hyp_38e7e1fe16

DAY 1 — 19:55:09  [experiment_completed]
    exp_20b306145c completed in 35.2s (24 measurements)

DAY 1 — 19:55:09  [falsification]
    hyp_38e7e1fe16 probe survived: [boundary:random] confirmed: hybrid_sort vs merge_sort on 'random': +50% (needs >= 5%, decisive: gap 7.07 ms > required 1.59 ms) [n=8192, 7 trials] | [scope:saw

DAY 1 — 19:55:09  [transition]
    FALSIFYING -> UPDATING_KNOWLEDGE

DAY 1 — 19:55:09  [transition]
    UPDATING_KNOWLEDGE -> CRITICIZING

DAY 1 — 19:55:09  [heartbeat]
    step 16 phase CRITICIZING | hyp 8 exp 13 evd 20 fail 3 | budget exp 13/100 compute 244.1s retries 0/8

DAY 1 — 19:55:09  [accepted]
    hyp_dbe5f386a7 ACCEPTED_WITH_SCOPE — holds at n<=2x tested sizes on its original regime(s); does NOT extend to ['organ_pipe', 'sawtooth']

DAY 1 — 19:55:09  [accepted]
    hyp_cae1c60f85 ACCEPTED_WITH_SCOPE — holds at n<=2x tested sizes on its original regime(s); extends to ['organ_pipe', 'sawtooth']

DAY 1 — 19:55:09  [accepted]
    hyp_40df9834c7 ACCEPTED_WITH_SCOPE — holds at n<=2x tested sizes on its original regime(s); extends to ['organ_pipe', 'sawtooth']

DAY 1 — 19:55:09  [accepted]
    hyp_38e7e1fe16 ACCEPTED_WITH_SCOPE — holds at n<=2x tested sizes on its original regime(s); extends to ['organ_pipe', 'sawtooth']

DAY 1 — 19:55:09  [critic_review]
    Critic pass complete: 5 assumptions on record, 2 cautions, 8 recommended follow-ups

DAY 1 — 19:55:09  [heartbeat]
    step 17 phase CRITICIZING | hyp 8 exp 13 evd 20 fail 3 | budget exp 13/100 compute 244.1s retries 0/8

DAY 1 — 19:55:09  [synthesis]
    Research dossier and timeline written to reports/

DAY 1 — 19:55:09  [transition]
    CRITICIZING -> COMPLETED (no high-value next experiment remained)

DAY 1 — 19:55:09  [stopped]
    Mission COMPLETED: no high-value next experiment remained

DAY 1 — 19:55:09  [heartbeat]
    step 18 phase COMPLETED | hyp 8 exp 13 evd 20 fail 3 | budget exp 13/100 compute 244.1s retries 0/8

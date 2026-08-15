# ORIGIN Research Timeline

Question: What source-backed conditions are commonly associated with algorithmic performance tradeoffs, and which of those claims can ORIGIN test in its own controlled benchmark domain?

DAY 1 — 13:00:54  [init]
    Research project initialized: What source-backed conditions are commonly associated with algorithmic performance tradeoffs, and which of those claims can ORIGIN test in its own controlled benchmark domain?

DAY 1 — 13:00:55  [retrieval]
    https://raw.githubusercontent.com/python/cpython/main/Objects/listsort.txt → 200 text/plain 44051B sha256:674d514b968e2a9b in 1.14s via https [robots: absent] (content treated as UNTRUSTED)

DAY 1 — 13:00:55  [source_ingested]
    src_17018df8e4: Intro (https://raw.githubusercontent.com/python/cpython/main/Objects/listsort.txt) — reliability 0.45 from 5 recorded reason(s); content is UNTRUSTED

DAY 1 — 13:00:55  [claim_extracted]
    clm_d489588de1 [descriptive, SPECULATION, conf 0.25] from src_17018df8e4@0: It has supernatural performance on many
kinds of partially ordered arrays (less than lg(N!

DAY 1 — 13:00:55  [claim_extracted]
    clm_0c6ffe35fb [descriptive, SPECULATION, conf 0.25] from src_17018df8e4@334: In a nutshell, the main routine marches over the array once, left to right,
alternately id

DAY 1 — 13:00:55  [claim_extracted]
    clm_5b231232f4 [descriptive, SPECULATION, conf 0.25] from src_17018df8e4@334: Everything else is complication for speed, and some
hard-won measure of memory efficiency.

DAY 1 — 13:00:55  [claim_extracted]
    clm_cb1e8fa367 [descriptive, SPECULATION, conf 0.25] from src_17018df8e4@598: Comparison with Python's Samplesort Hybrid
------------------------------------------
+ ti

DAY 1 — 13:00:55  [claim_extracted]
    clm_8529c70fc7 [descriptive, SPECULATION, conf 0.25] from src_17018df8e4@598: It can be
  expected to require a temp array this large when sorting random data; on
  dat

DAY 1 — 13:00:56  [retrieval]
    https://raw.githubusercontent.com/python/cpython/main/Doc/howto/sorting.rst → 200 text/plain 14563B sha256:69254a51e3b70df1 in 0.98s via https [robots: absent] (content treated as UNTRUSTED)

DAY 1 — 13:00:56  [source_ingested]
    src_32c45cedaa: .. _sortinghowto: (https://raw.githubusercontent.com/python/cpython/main/Doc/howto/sorting.rst) — reliability 0.45 from 5 recorded reason(s); content is UNTRUSTED

DAY 1 — 13:00:56  [claim_extracted]
    clm_e6bbe45bb1 [descriptive, SPECULATION, conf 0.25] from src_32c45cedaa@58: Python lists have a built-in :meth:`list.sort` method that modifies the list
in-place.

DAY 1 — 13:00:56  [claim_extracted]
    clm_4c61ec43a9 [descriptive, SPECULATION, conf 0.25] from src_32c45cedaa@58: There is also a :func:`sorted` built-in function that builds a new
sorted list from an ite

DAY 1 — 13:00:56  [claim_extracted]
    clm_3e714d60d6 [descriptive, SPECULATION, conf 0.25] from src_32c45cedaa@360: A simple ascending sort is very easy: just call the :func:`sorted` function.

DAY 1 — 13:00:56  [claim_extracted]
    clm_d56eda771a [descriptive, SPECULATION, conf 0.25] from src_32c45cedaa@535: You can also use the :meth:`list.sort` method.

DAY 1 — 13:00:56  [claim_extracted]
    clm_488f4d0cfc [descriptive, SPECULATION, conf 0.25] from src_32c45cedaa@868: Another difference is that the :meth:`list.sort` method is only defined for
lists.

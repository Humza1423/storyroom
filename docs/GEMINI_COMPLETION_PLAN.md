# Gemini-first visual-search completion

Approved 2026-10-25. Implement sequentially; measure before promoting defaults.

1. Correct the 12-video/40-query development baseline without modifying its
   historical answer key. Trace retrieval, grouping, shortlist, semantic rejection,
   and boundary errors. Preserve separate evaluation commits and PR #5.
2. Add an opt-in Gemini grounding path: one bounded request verifies meaning and
   proposes frame ranges. Expand continuous activities in cached 30-second chunks
   with four-second overlap in the persistent worker. Broad queries return one
   activity and a coherent suggested five-second cut; specific moves preserve
   visible preparation/follow-through; explicit durations override the default.
   Do not pad or merge through another action. Do not add Qwen or ANN.
3. Integrate activity review, exact selected-cut persistence, and inspection status.
   Freeze the implementation, prepare eight fresh licensed videos/24 queries,
   run the actual application workflow and Resolve handoff, and publish the
   measured result, including misses and provider limits.

Optional activity fields must preserve existing start/end selection frames and
legacy search. Incomplete inspection never means the activity is complete.
Use current unpaid Gemini first; no billing changes. Any paid experiment requires
the creator's decision and an estimated cost within the approved US$5 ceiling.

Release gates: >=95% returned-first precision; >=90% positive top-five moment
recall; no fixed hard-negative false matches; median discrete-action boundary
error <=1 second. Report continuous-shot usefulness, duration fulfillment,
requests/retries/video seconds, and cold/cache latency separately. Fake-provider
tests establish contracts, not live model accuracy. Stop prompt tuning after the
frozen validation and identify the measured next decision if gates fail.

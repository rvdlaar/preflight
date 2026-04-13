# Preflight — EA intake and pre-assessment tool
"""
Data model design principles (from first principles + second-order + inversion):

1. STORE THE SIGNAL, DISCARD NOTHING
   Every board override, every retrospective outcome, every persona calibration
   data point is the fuel for the meta features. Without it from day one,
   you can't build them later.

2. GRAPH, NOT TABLES
   Assessments link to vendors. Vendors link to previous assessments.
   Those link to regulations. Regulations link to ZiRA principles.
   These are not separate查询 — they're traversals. Model as a graph
   from day one, even if stored in PostgreSQL.

3. IMMUTABLE ASSESSMENT HISTORY
   Assessments are append-only. When a delta re-assessment happens,
   v1 is NOT modified — v2 is created with a parent pointer.
   This enables: diff view, drift detection, reproducibility (MDR).

4. EVERY ENTITY HAS A SOURCE
   Every finding cites its source (persona or knowledge chunk).
   Every board decision records who decided and why.
   Every calibration records the data it was based on.
   Traceability is not optional — it's the product.

5. PERSONA VERSIONS ARE FIRST-CLASS
   When personas are calibrated (Phase 5), previous assessment results
   MUST be reproducible. This requires storing which persona version
   produced which finding. MDR traceability demands this.

6. DESIGN FOR QUERIES THAT DON'T EXIST YET
   "Show me every proposal Victor blocked where the board overrode him
    and the system is now in production without incident."
   If the schema can't answer that, the schema is wrong.
"""

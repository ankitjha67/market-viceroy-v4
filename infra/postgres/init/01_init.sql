-- Market Viceroy v4 — PostgreSQL bootstrap (Phase 0).
--
-- Phase 0 only stands the database up and enables extensions the
-- relational model will need. The relational schema itself (instrument,
-- source, strategy, decision, journal, attribution, ... — PRD §6.1) is
-- introduced in the phases that own those entities, via migrations, not
-- pre-built here. Keeping this minimal avoids fabricating later-phase
-- detail before it is informed.

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- digests for the hash-chained journal (Phase 1+)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- primary keys

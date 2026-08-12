# Media Music: deterministic command engine

## Goal
Build a deterministic music command system that does not depend on LLM interpretation for normal playback commands.

Primary objectives:
- Predictable behavior.
- Lower latency and operational cost.
- Simple, testable rules for command resolution.
- Keep AI only as optional fallback.

## High-level architecture
1. Data sync layer:
- Extract catalogs from Jellyfin/Mopidy (tracks, artists, albums, genres, relations).
- Persist in local SQLite.
- Keep a lightweight sync process (full + incremental when possible).

2. Query layer (deterministic parser + resolver):
- Parse commands using fixed syntax with prefix "pon".
- Resolve intent with strict priority rules.
- Return explicit action plan (play one track vs queue many).

3. Playback layer:
- Execute selected URIs through Mopidy.
- Keep queue semantics explicit and stable.

4. Optional AI fallback:
- Only used if deterministic resolver cannot classify/resolve.
- Never first path for operational commands.

## SQLite model proposal
Core entities:
- artists(id, name, name_norm, name_phonetic)
- albums(id, name, name_norm, year, artist_id)
- tracks(id, uri, title, title_norm, album_id, year, duration_ms)
- genres(id, name, name_norm)

Relations:
- track_artists(track_id, artist_id, role)
- track_genres(track_id, genre_id)

Indexes:
- idx_artists_name_norm
- idx_albums_name_norm
- idx_tracks_title_norm
- idx_genres_name_norm
- idx_tracks_year
- relation table composite indexes by foreign keys

Optional search support:
- FTS5 virtual tables for artists/albums/tracks.
- Additional phonetic columns for fuzzy fallback.

## Normalization strategy
Store normalized text fields to make matching consistent:
- Lowercase.
- Strip accents/diacritics.
- Collapse repeated whitespace.
- Remove punctuation noise.

Example transformations:
- "Parchís" -> "parchis"
- "  New   Age " -> "new age"

## Fixed command grammar
Prefix command family:
- "pon musica <genre_query>"
- "pon <query>"

Meaning:
- "pon musica xxx" => interpret xxx as genre first.
- "pon yyy" => classify yyy in ordered resolver pipeline.

## Resolver priority for "pon <query>"
Given query Q:
1. Artist exact match.
2. Album exact match.
3. Track exact match.
4. Artist partial/fuzzy match.
5. Album partial/fuzzy match.
6. Track partial/fuzzy match.

If no confident match:
- Return compact clarification with up to 3 best options.

## Matching policy
Use staged matching with score thresholds:
1. Exact normalized equality.
2. Prefix match.
3. Contains/token overlap.
4. Fuzzy scoring.

Recommended fuzzy stack:
- Jaro-Winkler or Levenshtein distance on normalized strings.
- Double Metaphone for phonetic fallback.

Note:
- Do not rely on Soundex only; it is weak for Spanish names and mixed-language catalogs.

## Playback semantics (deterministic)
Default behavior:
- Artist/album/genre intent => queue multiple tracks (for example up to 20) and play.
- Unique track intent => queue single track and play.

Ambiguity handling:
- If multiple candidates are similarly strong, ask short clarification.
- Avoid silent random picks when ambiguity is high.

## Queue policy
Define explicit queue modes:
- play: clear queue, add selection, start playback.
- add: append selection without interrupting current playback.

## Sync strategy
Initial approach:
- Full sync command to rebuild DB from source.
- Periodic incremental refresh by changed/updated timestamps when available.

Safety:
- Keep source URI as stable primary external reference.
- Track deleted items and prune stale DB rows.

## Integration plan
Phase 1:
- Implement SQLite schema and normalization utilities.
- Add sync script from Mopidy/Jellyfin.

Phase 2:
- Implement deterministic parser and resolver service.
- Wire play/add execution through existing Mopidy RPC methods.

Phase 3:
- Add fuzzy fallback and confidence thresholds.
- Add compact clarification responses.

Phase 4:
- Add optional AI fallback behind feature flag.

## Testing checklist
Resolver tests:
- "pon musica new age" resolves genre intent.
- "pon enya" resolves artist intent.
- "pon the emancipatio of mimi" fuzzy resolves album typo.
- "pon water shows the hidden heart" resolves unique track intent.

Behavior tests:
- Genre/artist/album commands queue multiple tracks.
- Unique track command queues one track.
- Ambiguous commands produce clarification, not arbitrary selection.

Data tests:
- Multi-genre tracks remain multi-valued.
- Year/album/artist metadata are preserved after sync.

## Operational notes
- Keep this deterministic engine as primary path.
- Keep LLM out of core operational semantics.
- Expose debug logs showing: parsed intent, matched entity type, confidence, selected URIs, queue size.

from typing import Any, Dict, List
import json
import os
import re
import random
import logging
import unicodedata
import urllib.request
import urllib.error

from aikit.core.service_contract import ServiceContract, MethodSchema


class Service(ServiceContract):
    name = "music"
    description = "Music control service backed by Mopidy JSON-RPC."

    def __init__(self):
        self._mopidy_url = os.getenv("MOPIDY_URL", "http://127.0.0.1:6680/mopidy/rpc")
        self._rpc_id = 0
        self._logger = logging.getLogger("aikit.music")

    def list_methods(self) -> List[MethodSchema]:
        return [
            MethodSchema(
                name="search_tracks",
                description="Search tracks by structured fields (title and optional artist/album).",
                params_schema={
                    "title": {
                        "type": "string",
                        "description": "Track title or free text title query.",
                    },
                    "artist": {
                        "type": "string",
                        "description": "Optional artist filter.",
                    },
                    "album": {
                        "type": "string",
                        "description": "Optional album filter.",
                    },
                },
                required_params=["title"],
                returns_schema={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "uri": {"type": "string"},
                            "name": {"type": "string"},
                            "artists": {"type": "array", "items": {"type": "string"}},
                            "album": {"type": "string"},
                            "length_ms": {"type": "integer"},
                        },
                    },
                },
            ),
            MethodSchema(
                name="search_artists",
                description="Search artists by name and return possible matches.",
                params_schema={
                    "name": {
                        "type": "string",
                        "description": "Artist name query.",
                    }
                },
                required_params=["name"],
                returns_schema={
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                        },
                    },
                },
            ),
            MethodSchema(
                name="play_query",
                description="Replace current queue with matching tracks and start playback from the first one.",
                params_schema={
                    "query": {
                        "type": "string",
                        "description": "Track query to search and play.",
                    }
                },
                returns_schema={
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "queued_count": {"type": "integer"},
                        "first_track": {"type": "object"},
                    },
                },
            ),
            MethodSchema(
                name="play_track",
                description="Replace current queue and play matches for title, optionally constrained by artist/album.",
                params_schema={
                    "title": {
                        "type": "string",
                        "description": "Track title or title query.",
                    },
                    "artist": {
                        "type": "string",
                        "description": "Optional artist filter.",
                    },
                    "album": {
                        "type": "string",
                        "description": "Optional album filter.",
                    },
                },
                required_params=["title"],
                returns_schema={
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "queued_count": {"type": "integer"},
                        "first_track": {"type": "object"},
                    },
                },
            ),
            MethodSchema(
                name="play_uri",
                description="Replace queue with one URI and start playback immediately.",
                params_schema={
                    "uri": {
                        "type": "string",
                        "description": "Mopidy track URI to play.",
                    }
                },
                returns_schema={
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "uri": {"type": "string"},
                    },
                },
            ),
            MethodSchema(
                name="add_query",
                description="Search matching tracks and append them at the end of the current queue without interrupting playback.",
                params_schema={
                    "query": {
                        "type": "string",
                        "description": "Track query to search and append.",
                    }
                },
                returns_schema={
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "queued_count": {"type": "integer"},
                        "first_track": {"type": "object"},
                    },
                },
            ),
            MethodSchema(
                name="add_track",
                description="Append matching tracks for title, optionally filtered by artist/album, to current queue.",
                params_schema={
                    "title": {
                        "type": "string",
                        "description": "Track title or title query.",
                    },
                    "artist": {
                        "type": "string",
                        "description": "Optional artist filter.",
                    },
                    "album": {
                        "type": "string",
                        "description": "Optional album filter.",
                    },
                },
                required_params=["title"],
                returns_schema={
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "queued_count": {"type": "integer"},
                        "first_track": {"type": "object"},
                    },
                },
            ),
            MethodSchema(
                name="add_uri",
                description="Append a specific Mopidy URI at the end of the current queue without clearing it.",
                params_schema={
                    "uri": {
                        "type": "string",
                        "description": "Mopidy track URI to append.",
                    }
                },
                returns_schema={
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "uri": {"type": "string"},
                    },
                },
            ),
            MethodSchema(
                name="pause",
                description="Pause playback.",
                params_schema={},
                returns_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
            ),
            MethodSchema(
                name="resume",
                description="Resume playback.",
                params_schema={},
                returns_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
            ),
            MethodSchema(
                name="next_track",
                description="Skip to next track.",
                params_schema={},
                returns_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
            ),
            MethodSchema(
                name="previous_track",
                description="Go to previous track.",
                params_schema={},
                returns_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
            ),
            MethodSchema(
                name="set_volume",
                description="Set playback volume in range 0..100.",
                params_schema={
                    "volume": {
                        "type": "integer",
                        "description": "Volume percentage from 0 to 100.",
                    }
                },
                returns_schema={
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "volume": {"type": "integer"},
                    },
                },
            ),
            MethodSchema(
                name="get_status",
                description="Get current playback state, track and volume.",
                params_schema={},
                returns_schema={
                    "type": "object",
                    "properties": {
                        "state": {"type": "string"},
                        "volume": {"type": "integer"},
                        "track": {"type": "object"},
                    },
                },
            ),
        ]

    def _rpc(self, method: str, params: Dict[str, Any] | None = None) -> Any:
        self._rpc_id += 1
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._rpc_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._mopidy_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = resp.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Mopidy connection error: {exc}") from exc

        parsed = json.loads(body)
        if parsed.get("error"):
            raise RuntimeError(f"Mopidy RPC error: {parsed['error']}")
        return parsed.get("result")

    def _track_to_dict(self, track: Dict[str, Any]) -> Dict[str, Any]:
        artists = [a.get("name", "") for a in (track.get("artists") or []) if a.get("name")]
        album_name = ""
        album = track.get("album")
        if isinstance(album, dict):
            album_name = album.get("name", "")
        return {
            "uri": track.get("uri", ""),
            "name": track.get("name", ""),
            "artists": artists,
            "album": album_name,
            "length_ms": track.get("length") or 0,
        }

    def _track_matches_metadata(
        self,
        track: Dict[str, Any],
        album_filter: str,
    ) -> bool:
        if album_filter:
            album_name = ""
            album_data = track.get("album")
            if isinstance(album_data, dict) and isinstance(album_data.get("name"), str):
                album_name = album_data.get("name", "")
            if album_name:
                if album_filter not in self._fold_text(album_name):
                    return False
            else:
                return False

        return True

    def _get_volume(self) -> int:
        # Mopidy moderno expone volumen en core.mixer.
        # Mantenemos fallback para compatibilidad con otras versiones/backends.
        try:
            value = self._rpc("core.mixer.get_volume")
            if value is None:
                return 0
            return int(value)
        except Exception:
            value = self._rpc("core.playback.get_volume")
            if value is None:
                return 0
            return int(value)

    def _set_volume(self, volume: int) -> None:
        try:
            self._rpc("core.mixer.set_volume", {"volume": volume})
            return
        except Exception:
            self._rpc("core.playback.set_volume", {"volume": volume})

    def _lookup_tracks_by_uri(self, uri: str) -> List[Dict[str, Any]]:
        looked_up = self._rpc("core.library.lookup", {"uris": [uri]})
        if not isinstance(looked_up, dict):
            return []
        tracks = looked_up.get(uri)
        if not isinstance(tracks, list):
            return []
        return [t for t in tracks if isinstance(t, dict)]

    def _enrich_track_from_lookup(self, track: Dict[str, Any]) -> Dict[str, Any]:
        uri = str(track.get("uri", "")).strip()
        if not uri:
            return track

        looked_up_tracks = self._lookup_tracks_by_uri(uri)
        if not looked_up_tracks:
            return track

        full_track = None
        for candidate in looked_up_tracks:
            if str(candidate.get("uri", "")).strip() == uri:
                full_track = candidate
                break
        if full_track is None:
            full_track = looked_up_tracks[0]

        merged = dict(track)

        if (not isinstance(merged.get("artists"), list) or not merged.get("artists")) and isinstance(full_track.get("artists"), list):
            merged["artists"] = full_track.get("artists")

        album_data = merged.get("album")
        album_name = ""
        if isinstance(album_data, dict) and isinstance(album_data.get("name"), str):
            album_name = album_data.get("name", "")
        if (not album_name.strip()) and isinstance(full_track.get("album"), dict):
            merged["album"] = full_track.get("album")

        if (not isinstance(merged.get("length"), int) or merged.get("length", 0) <= 0) and isinstance(full_track.get("length"), int):
            merged["length"] = full_track.get("length", 0)

        return merged

    def _is_playable_uri(self, uri: str) -> bool:
        clean = (uri or "").strip()
        if not clean:
            return False
        if clean.endswith(":search"):
            return False
        return True

    def _normalize_query(self, query: str) -> str:
        text = (query or "").strip()
        if not text:
            return ""

        # Limpia prefijos operativos para buscar solo termino musical.
        text = re.sub(r"^\s*musica\s*:\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(
            r"^\s*(pon|poner|ponme|reproduce|reproducir|play|resume|reanuda)\b[\s:,-]*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text.strip()

    def _fold_text(self, text: str) -> str:
        base = unicodedata.normalize("NFD", text or "")
        base = "".join(ch for ch in base if unicodedata.category(ch) != "Mn")
        base = re.sub(r"[^a-zA-Z0-9\s]", " ", base)
        base = re.sub(r"\s+", " ", base)
        return base.casefold().strip()

    def _extract_artist_names(self, entry: Dict[str, Any]) -> List[str]:
        names: List[str] = []

        artists = entry.get("artists") or []
        if isinstance(artists, list):
            for artist in artists:
                if isinstance(artist, dict) and isinstance(artist.get("name"), str):
                    names.append(artist["name"])

        tracks = entry.get("tracks") or []
        if isinstance(tracks, list):
            for track in tracks:
                if not isinstance(track, dict):
                    continue
                for artist in track.get("artists") or []:
                    if isinstance(artist, dict) and isinstance(artist.get("name"), str):
                        names.append(artist["name"])

        return names

    def _artist_exists(self, artist_name: str) -> bool:
        candidate = self._fold_text(artist_name)
        if not candidate:
            return False

        candidate_tokens = [t for t in candidate.split(" ") if t]
        is_multiword_candidate = len(candidate_tokens) >= 2

        result = self._rpc("core.library.search", {"query": {"any": [artist_name]}, "exact": False})
        entries = result if isinstance(result, list) else [result]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for found in self._extract_artist_names(entry):
                folded_found = self._fold_text(found)
                if not folded_found:
                    continue
                if folded_found == candidate:
                    return True
                if is_multiword_candidate and candidate in folded_found:
                    return True
        return False

    def _list_candidate_artist_names(self, query: str) -> List[str]:
        result = self._rpc("core.library.search", {"query": {"any": [query]}, "exact": False})
        entries = result if isinstance(result, list) else [result]
        names: List[str] = []
        seen = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for found in self._extract_artist_names(entry):
                folded = self._fold_text(found)
                if not folded or folded in seen:
                    continue
                seen.add(folded)
                names.append(found)
        return names

    def _detect_artist_filter(self, cleaned_query: str) -> Dict[str, str]:
        # 1) Forma explícita: "<titulo> de <artista>"
        explicit = re.split(r"\s+de\s+", cleaned_query, maxsplit=1, flags=re.IGNORECASE)
        if len(explicit) == 2:
            title_candidate = explicit[0].strip()
            artist_candidate = explicit[1].strip()
            if artist_candidate and self._artist_exists(artist_candidate):
                return {"title": title_candidate, "artist": artist_candidate}
            # Si no es artista válido, tratamos toda la frase como título.
            return {"title": cleaned_query, "artist": ""}

        # 2) Fallback: si el modelo transformó "<titulo> de <artista>" a
        # "<titulo> <artista>", intentamos detectar artista en el sufijo.
        tokens = [t for t in re.split(r"\s+", cleaned_query) if t]
        for size in range(min(4, len(tokens) - 1), 0, -1):
            artist_candidate = " ".join(tokens[-size:]).strip()
            title_candidate = " ".join(tokens[:-size]).strip()
            if not title_candidate:
                continue
            if self._artist_exists(artist_candidate):
                return {"title": title_candidate, "artist": artist_candidate}

        return {"title": cleaned_query, "artist": ""}

    def _split_title_artist(self, query: str) -> Dict[str, str]:
        cleaned = self._normalize_query(query)
        if not cleaned:
            return {"title": "", "artist": ""}
        return self._detect_artist_filter(cleaned)

    def _score_track_match(self, track: Dict[str, Any], title_hint: str, artist_hint: str) -> float:
        title = self._fold_text(str(track.get("name", "")))
        artists = " ".join(self._fold_text(a) for a in track.get("artists", []) if isinstance(a, str))

        wanted_title = self._fold_text(title_hint)
        wanted_artist = self._fold_text(artist_hint)

        score = 0.0

        if wanted_title:
            if title == wanted_title:
                score += 120.0
            elif wanted_title in title:
                score += 80.0
            elif title and title in wanted_title:
                score += 45.0

            wanted_tokens = [t for t in wanted_title.split(" ") if t]
            title_tokens = set(t for t in title.split(" ") if t)
            if wanted_tokens:
                overlap = sum(1 for t in wanted_tokens if t in title_tokens)
                score += 40.0 * (overlap / len(wanted_tokens))

        if wanted_artist:
            if wanted_artist in artists:
                score += 70.0
            else:
                score -= 25.0

        return score

    def _pick_best_track(self, tracks: List[Dict[str, Any]], query: str) -> Dict[str, Any] | None:
        if not tracks:
            return None
        hints = self._split_title_artist(query)
        ranked = sorted(
            tracks,
            key=lambda t: self._score_track_match(t, hints["title"], hints["artist"]),
            reverse=True,
        )
        return ranked[0] if ranked else None

    def _pick_unique_title_match(self, tracks: List[Dict[str, Any]], title_hint: str) -> Dict[str, Any] | None:
        wanted = self._fold_text(title_hint)
        if not wanted:
            return None

        exact_matches: List[Dict[str, Any]] = []
        partial_matches: List[Dict[str, Any]] = []
        for track in tracks:
            name = self._fold_text(str(track.get("name", "")))
            if not name:
                continue
            if name == wanted:
                exact_matches.append(track)
            elif wanted in name:
                partial_matches.append(track)

        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(partial_matches) == 1:
            return partial_matches[0]
        return None

    def _is_specific_title_hint(self, title_hint: str) -> bool:
        folded = self._fold_text(title_hint)
        if not folded:
            return False
        tokens = [t for t in folded.split(" ") if t]
        # Consideramos "titulo especifico" cuando la consulta es suficientemente
        # descriptiva; evita tratar "new age" como titulo unico.
        if len(tokens) >= 3:
            return True
        if len(folded) >= 16 and len(tokens) >= 2:
            return True
        return False

    def _build_search_terms(self, query: str, artist_filter: str = "") -> List[str]:
        cleaned = self._normalize_query(query)

        # Si ya tenemos filtro de artista explícito, no intentamos inferir artista
        # de nuevo en el título para evitar perder términos relevantes.
        if artist_filter:
            title_for_search = cleaned
        else:
            if not cleaned:
                return []
            parsed = self._detect_artist_filter(cleaned)
            title_for_search = parsed["title"] or cleaned

        if not title_for_search:
            return []

        # Busca principalmente por título; el artista (si es válido) se aplica como filtro.
        parts = re.split(r"\s+de\s+", title_for_search, maxsplit=1, flags=re.IGNORECASE)
        terms: List[str] = []
        if len(parts) == 2:
            title = parts[0].strip()
            if title:
                terms.append(title)
        else:
            terms.append(title_for_search)

        # Fallback extra: dividir por palabras solo en consultas cortas y utiles,
        # para evitar busquedas excesivamente amplias con muchas palabras vacias.
        if len(terms) == 1:
            tokens = [t for t in re.split(r"\s+", terms[0]) if t]
            useful_tokens = [
                t for t in tokens
                if len(t) >= 4
            ]
            if 1 < len(useful_tokens) <= 4:
                terms.extend(useful_tokens)

        # Deduplicado preservando orden.
        unique_terms: List[str] = []
        seen = set()
        for term in terms:
            key = term.casefold()
            if key in seen:
                continue
            seen.add(key)
            unique_terms.append(term)
        return unique_terms

    def _track_matches_artist(self, track: Dict[str, Any], artist_filter: str) -> bool:
        wanted = self._fold_text(artist_filter)
        if not wanted:
            return True
        for artist in track.get("artists", []):
            current_name = ""
            if isinstance(artist, str):
                current_name = artist
            elif isinstance(artist, dict) and isinstance(artist.get("name"), str):
                current_name = artist.get("name", "")
            if not current_name:
                continue

            current = self._fold_text(current_name)
            if not current:
                continue
            if current == wanted or wanted in current:
                return True
        return False

    def search_tracks(
        self,
        title: str = "",
        artist: str = "",
        limit: int = 10,
        album: str = "",
    ) -> List[Dict[str, Any]]:
        cleaned_title = self._normalize_query(title)

        artist_filter = artist.strip() if isinstance(artist, str) else ""
        if artist_filter and not self._artist_exists(artist_filter):
            artist_filter = ""

        album_filter = self._fold_text(album) if isinstance(album, str) and album.strip() else ""

        if not cleaned_title and not artist_filter and not album_filter:
            self._logger.debug("search_tracks empty query and artist")
            return []

        search_base = cleaned_title or album or artist_filter
        search_terms = self._build_search_terms(search_base, artist_filter)
        if album_filter and isinstance(album, str) and album.strip():
            search_terms.append(album.strip())

        # Dedup tras añadir términos de metadatos.
        dedup_terms: List[str] = []
        seen_terms = set()
        for term in search_terms:
            key = term.casefold()
            if key in seen_terms:
                continue
            seen_terms.add(key)
            dedup_terms.append(term)
        search_terms = dedup_terms

        if not search_terms:
            self._logger.debug("search_tracks no terms title=%s artist=%s", cleaned_title, artist_filter)
            return []

        self._logger.debug(
            "search_tracks request title=%s artist=%s terms=%s limit=%s",
            cleaned_title,
            artist_filter,
            search_terms,
            limit,
        )

        result = self._rpc("core.library.search", {"query": {"any": search_terms}, "exact": False})
        tracks: List[Dict[str, Any]] = []

        # Dependiendo del backend/version de Mopidy, core.library.search puede
        # devolver:
        # - dict con clave "tracks"
        # - lista de resultados de busqueda (cada uno con "tracks")
        if isinstance(result, dict):
            maybe_tracks = result.get("tracks")
            if isinstance(maybe_tracks, list):
                tracks = [t for t in maybe_tracks if isinstance(t, dict)]
        elif isinstance(result, list):
            lookup_budget = max(20, limit * 4)
            for entry in result[:lookup_budget]:
                if not isinstance(entry, dict):
                    continue
                entry_tracks = entry.get("tracks")
                if isinstance(entry_tracks, list):
                    tracks.extend(t for t in entry_tracks if isinstance(t, dict))

                # Algunos backends (p.ej. Jellyfin) devuelven SearchResult con
                # artistas/albums, no pistas directas. Resolvemos a pistas reales,
                # pero con presupuesto de lookups para evitar latencias altas.
                if len(tracks) < (limit * 8):
                    albums = entry.get("albums") or []
                    if isinstance(albums, list):
                        for album in albums[:3]:
                            if not isinstance(album, dict):
                                continue
                            album_uri = album.get("uri", "")
                            if isinstance(album_uri, str) and album_uri.strip():
                                tracks.extend(self._lookup_tracks_by_uri(album_uri))

                    artists = entry.get("artists") or []
                    if isinstance(artists, list):
                        for artist in artists[:3]:
                            if not isinstance(artist, dict):
                                continue
                            artist_uri = artist.get("uri", "")
                            if isinstance(artist_uri, str) and artist_uri.strip():
                                tracks.extend(self._lookup_tracks_by_uri(artist_uri))

                # Solo tratamos como pista directa si parece realmente reproducible.
                entry_uri = entry.get("uri", "")
                if isinstance(entry_uri, str) and self._is_playable_uri(entry_uri) and (
                    entry.get("name") or entry.get("length")
                ):
                    tracks.append(entry)

        # Deduplicar por URI para evitar repeticiones tras resolver album+artist.
        unique_tracks: List[Dict[str, Any]] = []
        seen_uris = set()
        for t in tracks:
            if album_filter:
                t = self._enrich_track_from_lookup(t)
            uri = str(t.get("uri", "")).strip()
            if not self._is_playable_uri(uri):
                continue
            if artist_filter and not self._track_matches_artist(t, artist_filter):
                continue
            if not self._track_matches_metadata(t, album_filter):
                continue
            if uri in seen_uris:
                continue
            seen_uris.add(uri)
            unique_tracks.append(t)

        safe_limit = max(1, int(limit))
        selected_tracks = unique_tracks[:safe_limit]
        selected_tracks = [self._enrich_track_from_lookup(t) for t in selected_tracks]
        out = [self._track_to_dict(t) for t in selected_tracks]
        self._logger.debug(
            "search_tracks result_count=%s prefilter_count=%s artist_filter=%s",
            len(out),
            len(tracks),
            artist_filter,
        )
        return out

    def search_artists(self, name: str) -> List[Dict[str, str]]:
        if not isinstance(name, str) or not name.strip():
            return []
        return [{"name": n} for n in self._list_candidate_artist_names(name.strip())[:20]]

    def play_query(self, query: str) -> Dict[str, Any]:
        parsed = self._split_title_artist(query)
        return self.play_track(parsed.get("title", ""), parsed.get("artist", ""))

    def play_track(
        self,
        title: str,
        artist: str = "",
        album: str = "",
    ) -> Dict[str, Any]:
        clean_title = self._normalize_query(title)
        clean_artist = artist.strip() if isinstance(artist, str) else ""

        # Si el usuario dice "pon <artista>" (sin titulo explicito),
        # tratamos la entrada como peticion de reproducir varias canciones del artista.
        artist_only_mode = bool(clean_title and not clean_artist and self._artist_exists(clean_title))
        self._logger.debug(
            "play_track parsed title=%s artist=%s artist_only_mode=%s",
            clean_title,
            clean_artist,
            artist_only_mode,
        )

        effective_artist = clean_artist or (clean_title if artist_only_mode else "")
        effective_title = "" if artist_only_mode else clean_title
        tracks = self.search_tracks(
            effective_title,
            effective_artist,
            limit=50,
            album=album,
        )
        if not tracks:
            return {"ok": False, "error": "No tracks found"}

        if artist_only_mode:
            selected_tracks = tracks[:]
            random.shuffle(selected_tracks)
            selected_tracks = selected_tracks[:20]

            uris = [
                t.get("uri", "")
                for t in selected_tracks
                if isinstance(t.get("uri"), str) and self._is_playable_uri(t.get("uri", ""))
            ]
            if not uris:
                return {"ok": False, "error": "No playable tracks found"}

            self._rpc("core.tracklist.clear")
            added = self._rpc("core.tracklist.add", {"uris": uris})
            if not isinstance(added, list) or not added:
                return {"ok": False, "error": "Tracklist add failed"}

            self._rpc("core.playback.play")
            return {
                "ok": True,
                "queued_count": len(added),
                "first_track": selected_tracks[0],
                "user_message": "Reproduciendo.",
            }

        # Por defecto reproducimos varias pistas. Solo dejamos una si el
        # titulo identifica de forma unica una cancion concreta.
        unique_match = None
        if self._is_specific_title_hint(effective_title):
            unique_match = self._pick_unique_title_match(tracks, effective_title)

        if unique_match:
            selected_tracks = [unique_match]
        elif len(tracks) == 1:
            selected_tracks = tracks
        else:
            selected_tracks = tracks[:20]

        if not selected_tracks:
            return {"ok": False, "error": "No suitable track found"}

        uris = [
            t.get("uri", "")
            for t in selected_tracks
            if isinstance(t.get("uri"), str) and self._is_playable_uri(t.get("uri", ""))
        ]
        if not uris:
            return {"ok": False, "error": "No playable tracks found"}

        self._rpc("core.tracklist.clear")
        added = self._rpc("core.tracklist.add", {"uris": uris})
        if not isinstance(added, list) or not added:
            return {"ok": False, "error": "Tracklist add failed"}

        self._rpc("core.playback.play")
        return {
            "ok": True,
            "queued_count": len(added),
            "first_track": selected_tracks[0],
            "user_message": "Reproduciendo.",
        }

    def add_query(self, query: str) -> Dict[str, Any]:
        parsed = self._split_title_artist(query)
        return self.add_track(parsed.get("title", ""), parsed.get("artist", ""))

    def add_track(
        self,
        title: str,
        artist: str = "",
        album: str = "",
    ) -> Dict[str, Any]:
        tracks = self.search_tracks(title, artist, album=album)
        if not tracks:
            return {"ok": False, "error": "No tracks found"}

        uris = [t.get("uri", "") for t in tracks if isinstance(t.get("uri"), str) and self._is_playable_uri(t.get("uri", ""))]
        if not uris:
            return {"ok": False, "error": "No playable tracks found"}

        added = self._rpc("core.tracklist.add", {"uris": uris})
        if not isinstance(added, list) or not added:
            return {"ok": False, "error": "Tracklist add failed"}

        return {
            "ok": True,
            "queued_count": len(added),
            "first_track": tracks[0],
            "user_message": "Anadido a la cola.",
        }

    def play_uri(self, uri: str) -> Dict[str, Any]:
        if not self._is_playable_uri(uri):
            return {"ok": False, "error": f"Non-playable URI: {uri}"}

        self._rpc("core.tracklist.clear")
        added = self._rpc("core.tracklist.add", {"uris": [uri]})
        if not isinstance(added, list) or not added:
            return {"ok": False, "error": f"Tracklist add failed for URI: {uri}"}
        self._rpc("core.playback.play")
        return {"ok": True, "uri": uri, "user_message": "Reproduciendo."}

    def add_uri(self, uri: str) -> Dict[str, Any]:
        if not self._is_playable_uri(uri):
            return {"ok": False, "error": f"Non-playable URI: {uri}"}

        added = self._rpc("core.tracklist.add", {"uris": [uri]})
        if not isinstance(added, list) or not added:
            return {"ok": False, "error": f"Tracklist add failed for URI: {uri}"}
        return {"ok": True, "uri": uri, "user_message": "Anadido a la cola."}

    def pause(self) -> Dict[str, Any]:
        self._rpc("core.playback.pause")
        return {"ok": True, "user_message": "Pausado."}

    def resume(self) -> Dict[str, Any]:
        self._rpc("core.playback.play")
        return {"ok": True, "user_message": "Reproduciendo."}

    def next_track(self) -> Dict[str, Any]:
        self._rpc("core.playback.next")
        return {"ok": True, "user_message": "Siguiente pista."}

    def previous_track(self) -> Dict[str, Any]:
        self._rpc("core.playback.previous")
        return {"ok": True, "user_message": "Pista anterior."}

    def set_volume(self, volume: int) -> Dict[str, Any]:
        safe_volume = max(0, min(100, int(volume)))
        self._set_volume(safe_volume)
        return {"ok": True, "volume": safe_volume, "user_message": f"Volumen al {safe_volume}%."}

    def get_status(self) -> Dict[str, Any]:
        state = self._rpc("core.playback.get_state")
        volume = self._get_volume()
        current = self._rpc("core.playback.get_current_tl_track")
        track: Dict[str, Any] = {}
        if isinstance(current, dict) and isinstance(current.get("track"), dict):
            track = self._track_to_dict(current["track"])
        return {
            "state": state,
            "volume": volume,
            "track": track,
        }

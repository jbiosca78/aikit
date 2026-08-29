# ver playlist
mpc playlist

curl -s -X POST http://localhost:6680/mopidy/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"core.tracklist.get_tracks","params":{}}' \
  | python3 -m json.tool | head -60


# agregar música de un artista
mpc clear
mpc findadd artist "Air"
mpc play

# buscar música de un artista
curl -s -X POST http://localhost:6680/mopidy/rpc -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"core.library.search","params":{"query":{"artist":["Enya"]}}}' | jq




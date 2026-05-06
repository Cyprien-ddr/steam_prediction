#!/usr/bin/env sh
for dir in backups/*; do
  raw_name=$(basename "$dir")

  name=$(echo "$raw_name" | tr ' ' '_' | tr '-' '_')

  echo "Restoring $raw_name -> $name"

  docker exec mongodb mongorestore \
    --uri="mongodb://root:example@localhost:27017/" \
    --authenticationDatabase admin \
    --drop \
    --nsInclude="steam_prediction.*" \
    --db "$name" \
    "/backups/$raw_name/steam_prediction"

done
#!/bin/zsh
# ./publish.sh build   — zip the pack into dist/
# ./publish.sh         — zip it and upload it to Modrinth as the version in VERSION
#                        (set CHANGELOG="..." for the changelog)
set -euo pipefail
cd "${0:A:h}"

PROJECT=bedrock-breaking-animation
GAME_VERSION=26.3
VERSION=$(<VERSION)
ZIP="dist/Bedrock-Breaking-Animation-$VERSION.zip"

mkdir -p dist
rm -f "$ZIP"
(cd pack && zip -qrX "../$ZIP" . -x '.*')
echo "Built $ZIP"
[[ "${1:-}" == build ]] && exit 0

TOKEN=${MODRINTH_TOKEN:-$(tr -d ' \n\r' < ~/.config/modrinth/token)}
# The version endpoint wants the project's ID, not its slug.
PROJECT_ID=$(curl -sS -f -H "Authorization: $TOKEN" "https://api.modrinth.com/v2/project/$PROJECT" \
    | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["id"])')
DATA=$(python3 -I -c 'import json,sys; print(json.dumps({
    "project_id": sys.argv[1], "version_number": sys.argv[2], "name": f"{sys.argv[2]} for Minecraft {sys.argv[3]}",
    "changelog": sys.argv[4], "game_versions": [sys.argv[3]], "loaders": ["minecraft"], "version_type": "release",
    "featured": True, "dependencies": [], "file_parts": ["file"], "primary_file": "file"}))' \
    "$PROJECT_ID" "$VERSION" "$GAME_VERSION" "${CHANGELOG:-}")
DATA_FILE=$(mktemp)
trap 'rm -f "$DATA_FILE"' EXIT
print -r -- "$DATA" > "$DATA_FILE"
RESPONSE=$(curl -sS -X POST -H "Authorization: $TOKEN" -F "data=<$DATA_FILE" -F "file=@$ZIP;type=application/zip" \
    -w '\n%{http_code}' https://api.modrinth.com/v2/version)
STATUS=${RESPONSE##*$'\n'}
RESPONSE=${RESPONSE%$'\n'*}
if [[ $STATUS != 200 ]]; then
    echo "Upload failed (HTTP $STATUS): $RESPONSE" >&2
    exit 1
fi
ID=$(python3 -I -c 'import json,sys; print(json.loads(sys.argv[1])["id"])' "$RESPONSE")
echo "Uploaded version $VERSION as $ID: https://modrinth.com/resourcepack/$PROJECT/version/$ID"

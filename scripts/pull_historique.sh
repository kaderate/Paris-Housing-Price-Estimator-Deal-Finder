#!/usr/bin/env bash
# Récupère Data_Loyer_historique.csv avant de scraper, pour faire persister l'historique
# entre les runs de la routine cloud (chacun repart d'un clone neuf du dépôt).
# Priorité au Gist : c'est le palier d'écriture le plus permissif dans push_historique.sh,
# donc s'il existe c'est probablement la source la plus à jour. Sinon, repli sur la
# branche "data" (Data_Loyer_historique.csv est volontairement exclu du suivi sur main,
# cf. .gitignore, pour ne pas polluer son historique de commits).
# Ne touche jamais à la branche locale courante.
set -euo pipefail

FICHIER="Data_Loyer_historique.csv"
GIST_DESCRIPTION="paris-housing-historique-v1"

recuperer_depuis_gist() {
    local token gist_id contenu_url

    token="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
    if [ -z "$token" ]; then
        return 1
    fi

    gist_id=$(curl -sS -H "Authorization: Bearer $token" "https://api.github.com/gists" \
        | python3 -c "
import sys, json
for g in json.load(sys.stdin):
    if g.get('description') == '$GIST_DESCRIPTION':
        print(g['id']); break
" 2>/dev/null || echo "")

    if [ -z "$gist_id" ]; then
        return 1
    fi

    contenu_url=$(curl -sS -H "Authorization: Bearer $token" "https://api.github.com/gists/$gist_id" \
        | python3 -c "
import sys, json
print(json.load(sys.stdin)['files']['$FICHIER']['raw_url'])
" 2>/dev/null || echo "")

    if [ -z "$contenu_url" ]; then
        return 1
    fi

    curl -sS -H "Authorization: Bearer $token" "$contenu_url" > "$FICHIER"
    echo "Historique récupéré depuis le Gist $gist_id ($(($(wc -l < "$FICHIER") - 1)) annonces)."
}

recuperer_depuis_branche_data() {
    git fetch origin data 2>/dev/null || true
    if ! git rev-parse --verify origin/data >/dev/null 2>&1; then
        return 1
    fi
    git show "origin/data:$FICHIER" > "$FICHIER"
    echo "Historique récupéré depuis la branche 'data' ($(($(wc -l < "$FICHIER") - 1)) annonces)."
}

if recuperer_depuis_gist; then
    :
elif recuperer_depuis_branche_data; then
    :
else
    echo "Aucune source d'historique trouvée (ni Gist, ni branche 'data') — premier run, l'historique démarre vide."
fi

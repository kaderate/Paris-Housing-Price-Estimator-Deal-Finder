#!/usr/bin/env bash
# Publie Data_Loyer_historique.csv sur la branche "data" après un run.
# Contrepartie de pull_historique.sh : fait persister l'historique entre les runs de la
# routine cloud sans jamais committer de données sur main, et sans changer de branche
# locale (utilise la plomberie git bas niveau : hash-object/mktree/commit-tree).
set -euo pipefail

FICHIER="Data_Loyer_historique.csv"

if [ ! -f "$FICHIER" ]; then
    echo "Aucun $FICHIER à publier, on ne fait rien."
    exit 0
fi

BLOB=$(git hash-object -w "$FICHIER")
NOUVEL_ARBRE=$(printf "100644 blob %s\t%s\n" "$BLOB" "$FICHIER" | git mktree)

git fetch origin data 2>/dev/null || true
if git rev-parse --verify origin/data >/dev/null 2>&1; then
    COMMIT=$(echo "Mise à jour de l'historique ($(date -u +%Y-%m-%dT%H:%M:%SZ))" | git commit-tree "$NOUVEL_ARBRE" -p origin/data)
else
    COMMIT=$(echo "Initialise l'historique ($(date -u +%Y-%m-%dT%H:%M:%SZ))" | git commit-tree "$NOUVEL_ARBRE")
fi

git push origin "$COMMIT:refs/heads/data"
echo "Historique publié sur la branche 'data' ($COMMIT)."

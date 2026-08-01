#!/usr/bin/env bash
# Récupère Data_Loyer_historique.csv depuis la branche "data" avant de scraper.
# Sert à faire persister l'historique entre les runs de la routine cloud, qui repartent
# chacun d'un clone neuf du dépôt (Data_Loyer_historique.csv est volontairement exclu du
# suivi sur main, cf. .gitignore, pour ne pas polluer son historique de commits).
# Ne touche jamais à la branche locale courante.
set -euo pipefail

git fetch origin data 2>/dev/null || true

if git rev-parse --verify origin/data >/dev/null 2>&1; then
    git show origin/data:Data_Loyer_historique.csv > Data_Loyer_historique.csv
    echo "Historique récupéré depuis la branche 'data' ($(($(wc -l < Data_Loyer_historique.csv) - 1)) annonces)."
else
    echo "Branche 'data' introuvable — premier run, l'historique démarre vide."
fi

#!/usr/bin/env bash
# Installe l'environnement du projet en une seule commande déterministe :
# sélection d'un interpréteur Python compatible, venv, dépendances.
set -euo pipefail

echo "== Sélection d'un interpréteur Python >= 3.12 (requis par numpy==2.5.1) =="
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "ERREUR : aucun interpréteur Python >= 3.12 trouvé (testé : python3.13, python3.12, python3)." >&2
    echo "Installe Python 3.12+ avant de relancer, ou assouplis la version de numpy dans requirements.txt." >&2
    exit 1
fi
echo "Python retenu : $PYTHON_BIN ($("$PYTHON_BIN" --version))"

echo "== Création de l'environnement virtuel =="
rm -rf venv
"$PYTHON_BIN" -m venv venv
source venv/bin/activate

echo "== Installation des dépendances Python =="
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo "== Setup terminé : source venv/bin/activate puis python main.py =="

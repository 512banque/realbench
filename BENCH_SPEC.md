# Bench: comparer plusieurs coding agents CLI sur des tâches identiques

## Objectif

Construire un harness de benchmark qui compare ces trois coding agents CLI
dans leur configuration native :

1. **Claude Code** (`claude`) avec son modèle par défaut
2. **Codex CLI** (`codex`) avec son modèle par défaut
3. **Deep Code** (`deepcode`) avec DeepSeek V4 Pro

Chaque CLI parle à son propre backend, avec sa propre authentification déjà
configurée. Le harness ne touche pas aux clés API, ne lance pas de proxy. Il
ne fait qu'orchestrer des invocations en mode non-interactif et mesurer.

## Métriques collectées par run

- `success` : booléen, exit code de `verify.sh`
- `wall_time_sec` : temps réel d'exécution
- `agent_exit_code` : exit code du CLI lui-même (≠ verify)
- Tout ce que le CLI rapporte nativement en JSON, capturé brut dans un
  fichier annexe et parsé best-effort dans `runs.jsonl` (tokens, nombre de
  tours, modèle, etc.)

Pas de proxy HTTP. Pas de mesures uniformes inter-CLI. On accepte
l'hétérogénéité des métriques natives.

## Architecture
bench/
agents/
claude-code.sh
codex.sh
deepcode.sh
tasks/
001-fizzbuzz/
prompt.md
workspace/
verify.sh
_reference/         # solution de référence pour valider verify.sh
002-fix-bug/
...
003-implement-spec/
...
runner.py
analyze.py
results/
runs.jsonl
raw/<run_id>/         # stdout, stderr, json natif du CLI
workspaces/<run_id>/  # copie du workspace après le run, pour debug
README.md

## Étape 1 — Wrappers d'agents

Chaque wrapper `agents/<name>.sh` est un script bash qui prend deux
arguments : `<prompt_file>` et `<run_raw_dir>`. Il lance son CLI en mode
non-interactif dans le `cwd` courant, écrit la sortie native dans
`<run_raw_dir>/` (stdout, stderr, et un éventuel JSON natif), et exit avec
le code retour du CLI.

Le contrat précis :

- `cwd` : déjà positionné par le runner sur le workspace de la tâche
- Le prompt est dans le fichier `$1`, à lire avec `cat`
- Les outputs vont dans `$2/stdout.txt`, `$2/stderr.txt`, et si le CLI
  produit un JSON natif structuré, dans `$2/native.json` (ou .jsonl)
- Le script doit auto-approuver tous les outils/permissions (le CLI ne doit
  rien demander à l'utilisateur)
- Exit code du script = exit code du CLI

### agents/claude-code.sh

Utilise `claude -p` avec `--output-format json` et `--permission-mode acceptEdits`
(ou équivalent pour ne rien demander). Le JSON produit en stdout contient
tokens et métadonnées — c'est ce qu'on capture dans `native.json`.

Référence : `claude --help` et la doc Claude Code headless.

### agents/codex.sh

Utilise `codex exec --json --full-auto` (ou `--dangerously-bypass-approvals-and-sandbox`
selon ce que la version installée supporte, à vérifier avec `codex exec --help`).
Le `--json` produit un stream JSONL d'events — capturer brut dans
`native.jsonl`.

### agents/deepcode.sh

⚠ Deep Code (`@vegamo/deepcode-cli`) n'a pas de mode non-interactif documenté
à ma connaissance. Le wrapper doit :

1. D'abord faire `deepcode --help` et chercher une option type `-p`,
   `--print`, `--exec`, `--prompt`, ou un sous-commande `exec`/`run`.
2. Si rien de tel n'existe, **STOP et demande-moi**. Ne pas essayer de piper
   le prompt via stdin sauf si la doc le mentionne, parce qu'un TUI lancé
   sans TTY se comporte mal.

Tester l'invocation avant de la figer dans le wrapper.

**Vérification étape 1 :** pour chaque wrapper, créer un tmpdir vide,
écrire un prompt trivial du genre "crée un fichier hello.txt contenant le
mot 'hello'", appeler le wrapper, vérifier que `hello.txt` est bien créé.
Si un wrapper ne peut pas être validé (ex: deepcode sans mode headless),
le noter dans `README.md` et l'exclure des runs par défaut.

## Étape 2 — Les 3 tâches

Chaque tâche est un dossier avec :
- `prompt.md` : instruction concise, sans ambiguïté
- `workspace/` : état initial du repo
- `verify.sh` : script bash, exit 0 si réussi, ≠ 0 sinon. **Totalement
  déterministe.** Pas de jugement humain.
- `_reference/` : un workspace résolu (solution correcte) qui doit faire
  passer `verify.sh` à coup sûr

### Tâche 001 — fizzbuzz (smoke test)

But : valider le harness, pas l'intelligence.

`workspace/solution.py` : `def fizzbuzz(n): pass`
`workspace/test_solution.py` : pytest avec ~8 cas, dont les multiples de 3,
de 5, de 15, et des nombres non-divisibles.

`prompt.md` : « Implémente la fonction `fizzbuzz(n)` dans `solution.py`
pour que les tests dans `test_solution.py` passent. Ne modifie pas les
tests. »

`verify.sh` :
```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
# Vérifier que les tests n'ont pas été modifiés
if [ -f .test_hash ]; then
  current=$(sha256sum workspace/test_solution.py | awk '{print $1}')
  expected=$(cat .test_hash)
  [ "$current" = "$expected" ] || { echo "tests modifiés"; exit 2; }
fi
cd workspace && python -m pytest test_solution.py -q
```

(Le hash est calculé une fois à la création de la tâche et stocké dans
`.test_hash`.)

### Tâche 002 — fix-bug

But : corriger un bug dans du code multi-fichiers.

Implémenter un mini-projet de 3-4 fichiers Python avec un bug introduit
volontairement. Suggestion : une `WeightedAverage` ou un parser de dates
ISO qui foire sur les fuseaux horaires. Choisis et implémente.

Les tests dans `workspace/tests/` révèlent le bug (rouges au départ).

`prompt.md` : « Les tests dans `tests/` échouent. Identifie la cause et
corrige le code de production. Ne modifie pas les fichiers de test. »

`verify.sh` : vérifie hash des tests + lance pytest.

### Tâche 003 — implement-spec

But : implémenter à partir de tests.

`workspace/cache.py` : stub vide
`workspace/test_cache.py` : tests complets spécifiant une `TTLCache` avec
get/set/delete/size, éviction par TTL, et un cas multi-threadé optionnel.

`prompt.md` : « Implémente `TTLCache` dans `cache.py` pour que tous les
tests dans `test_cache.py` passent. Ne modifie pas les tests. »

`verify.sh` : pareil.

**Vérification étape 2 :** pour chaque tâche, vérifier que :
1. `verify.sh` lancé sur `workspace/` (initial) retourne ≠ 0
2. `verify.sh` lancé après avoir copié `_reference/` par-dessus retourne 0

Si l'un des deux échoue, la tâche est cassée. Corrige avant de continuer.

## Étape 3 — runner.py

Script Python, CLI :
python runner.py --agents claude-code,codex,deepcode 
--tasks 001,002,003 
--runs 2 
--timeout 600

Algo, pour chaque triplet (agent, task, run_index) :

1. Génère un `run_id` (uuid4 court)
2. Crée `results/workspaces/<run_id>/` et `results/raw/<run_id>/`
3. Copie `tasks/<task>/workspace/` dans le dossier de travail
4. Lance `agents/<agent>.sh <prompt_path> <raw_dir>` avec :
   - `cwd` = dossier de travail
   - timeout = `--timeout`
   - capture du temps réel (mesuré côté Python, pas du CLI)
5. Note l'exit code du wrapper
6. Lance `tasks/<task>/verify.sh` avec `cwd` = dossier de travail
7. Parse best-effort les métriques natives du CLI depuis `raw/<run_id>/` :
   - claude-code : `native.json` → champs `usage.input_tokens`,
     `usage.output_tokens`, `num_turns` si présents
   - codex : `native.jsonl` → somme des tokens des events `turn.completed`,
     compte des `item.*` par type
   - deepcode : à voir selon ce qui sort
   Si le parsing échoue, log l'erreur, mets `parsing_error: true`, mais
   ne fais pas planter le runner.
8. Append une ligne dans `results/runs.jsonl` :

```json
{
  "run_id": "abc123",
  "timestamp": "2026-05-23T14:30:00Z",
  "agent": "claude-code",
  "task": "002-fix-bug",
  "run_index": 1,
  "success": true,
  "wall_time_sec": 47.3,
  "agent_exit_code": 0,
  "verify_exit_code": 0,
  "native_metrics": {
    "input_tokens": 45000,
    "output_tokens": 3200,
    "num_turns": 8,
    "raw_format": "claude-json-v1"
  },
  "raw_dir": "results/raw/abc123/",
  "workspace_dir": "results/workspaces/abc123/"
}
```

Le runner doit :
- `--dry-run` : vérifie que tous les wrappers existent, exécutables, que
  toutes les tâches ont prompt+verify+_reference, sans rien lancer
- Progress bar (tqdm) : `[codex / 002-fix-bug / run 2/3] running...`
- Gestion timeout propre : kill le process si dépassé, log `timeout: true`
- Robuste aux échecs : si un run plante, log l'erreur, passe au suivant

**Vérification étape 3 :**
1. `python runner.py --dry-run` doit passer.
2. Smoke test : `python runner.py --agents claude-code --tasks 001 --runs 1`
   doit produire une ligne dans `runs.jsonl` avec `success: true`.
3. Faire le même smoke test pour chacun des autres agents disponibles.

## Étape 4 — analyze.py

Lit `runs.jsonl`, imprime un tableau markdown comparatif. Pour chaque
(agent, task) :
- taux de succès (X/N)
- temps médian
- tokens médian (input/output, quand dispo)
- exits non-zéro / timeouts

Sortie stdout. Trier les lignes par agent puis par tâche.

**Vérification étape 4 :** après avoir lancé une matrice complète
(`--runs 2`, tous agents disponibles, toutes tâches), `python analyze.py`
doit imprimer un tableau cohérent dont les chiffres correspondent grosso
modo à ce que chaque CLI a affiché en fin de session.

## Étape 5 — README.md

Mode d'emploi court :
- prérequis : Claude Code, Codex CLI, Deep Code installés et authentifiés
  (le harness ne s'occupe pas de l'auth)
- commande pour lancer un run
- comment ajouter une tâche
- comment ajouter un agent
- limitations connues (par exemple si deepcode n'a pas de mode headless)

## Règles importantes

- **Arrête-toi à chaque "Vérification" et confirme avec moi avant de passer
  à la suite.** Ne fais pas tout d'un coup.
- **Si quelque chose est ambigu ou ne marche pas comme la doc le dit,
  demande-moi** plutôt que d'inventer. En particulier pour les flags exacts
  de chaque CLI, vérifie avec `<cli> --help` sur la version installée.
- **Vérifie les versions installées des trois CLIs en début d'étape 1 :**
  `claude --version`, `codex --version`, `deepcode --version`. Logge les
  versions dans le README. Si un CLI n'est pas installé, dis-le moi.
- **N'hardcode jamais de clés API.** Chaque CLI a déjà sa propre auth
  configurée par l'utilisateur.
- **Chemins relatifs** au dossier `bench/`.
- **Pas de cleanup automatique** des `results/workspaces/<run_id>/` — l'user
  veut pouvoir aller voir ce que le CLI a fait après coup.

Démarre par l'étape 1.
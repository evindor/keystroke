# Smart Match runtime

The default is **Voice and text**, using **Small (2M)**. Settings are under
Keystroke Settings > Matching. **Only voice** leaves typed queries on the ordinary
matcher. **Off** terminates the helper (including an in-progress installation),
clears pending results and releases the model; downloaded files remain for reuse.
**Large (8M)** downloads once when selected and first used. Both models run on CPU.
An idle helper also exits after two minutes and reloads on the next eligible query.

Installation from `bin/keystroke install` prepares Small. A plugin installed through
Omarchy prepares the selected model lazily on its first eligible query. This needs
Python 3 and `uv`, plus network access for the first download. Setup runs outside
the shell UI process, under the user's account, with no system package changes.
A failed setup keeps lexical search working and adds a Retry Smart Match row to
the Matching settings screen. `bin/keystroke matching [small|large]` can prepare
models without enabling or restarting the plugin.

The runtime and model cache live in
`${XDG_DATA_HOME:-~/.local/share}/keystroke/matching/`. `requirements.lock` pins
Python dependencies and their hashes; model revisions are fixed in
`helpers/matching-worker.py`. The model cache contains only configuration,
tokenizer and safetensors files. Subsequent loading is local-only. No query or
catalog text is sent to a remote inference service or saved by the worker.
Dependencies are downloaded only during setup; no code is generated or evaluated.

A single JSON-lines worker keeps normalized static vectors in memory. Catalog
updates reuse unchanged vectors and evict removed documents. Requests contain
only stable IDs and metadata, not executable actions. Replies contain IDs and
similarity scores. The host filters availability and scope before sending metadata
and maps replies back onto fresh provider rows. Each query/catalog/model has its
own request key; old responses cannot populate a newer query. Only the latest
queued query is kept while a request is in flight.

The host retains exact matching, adds bounded typo recovery and a conditional
Chrome-to-Chromium alias, and then adds semantic suggestions above fallbacks but
below exact hits before applying learned query preferences. It filters negation, command family, volume/brightness direction,
start/stop and contradictory on/off setters. A toggle is still presented as a
**Toggle**: unknown current state is never treated as a guaranteed on/off setter.
Equivalent commands are deduplicated while retaining confirmations. Results never
run automatically. Whole spoken arithmetic is parsed separately using the existing
bounded calculator; ambiguous homophones and ordinary prose are not rewritten.

`descriptions.json` is the frozen GPT-5.6 Terra annotation pass: 618 one-sentence
intent descriptions, produced from installed metadata without access to the test
queries. `description-keys.json` binds the descriptions to their original titles
and fingerprints of action/target definitions. Changed/custom/absent entries fall back to live
metadata. App IDs accept the AppLibrary's optional `.desktop` suffix. Community
providers can supply a live `catalog(ctx)` and their own `intentDescription`.
The shipped map does not create or install its catalog's apps or hotkeys.

The default ~8 MB 2M model has 64-dimensional vectors; the ~31 MB 8M model has
256-dimensional vectors. Python runtime memory exceeds model size; the experiment
measured roughly 100/130 MiB peak process RSS respectively. Neither similarity nor
a fixed threshold proves intent; this remains a suggestions system with explicit
selection and existing confirmation rules.

Model2Vec and the POTION models are MIT licensed:
https://github.com/MinishLab/model2vec
https://huggingface.co/minishlab/potion-base-2M
https://huggingface.co/minishlab/potion-base-8M

Model revisions:
- small: `389b9f64be5aa4ae7a6bc6fe95ef20ce485ae5da`
- large: `bf8b056651a2c21b8d2565580b8569da283cab23`

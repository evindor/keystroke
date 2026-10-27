# Spell check

Check the spelling of one English word from the [Keystroke](../../README.md) command palette, the way KRunner's spell checker does. Type `spell tresspass` and, when the word is wrong, the palette offers suggestions to copy: `trespass`, `transgress`, `trespassed`, ... Pick one with Enter to copy it, or Ctrl+Enter to paste it straight into the window you were typing in. When the word is spelled correctly you get just that word with a check mark next to it.

Suggestions come from a bundled frequency list and, where it is not enough, from an online service that only ever sees the word itself.

## Turn it on

Extensions ship with Keystroke switched off. Type `ext`, open **Extensions → Spell check**, and confirm **Enabled** (or Keystroke Settings → Spell check → Enabled).

## Use

| Query | Result |
| --- | --- |
| `spell the` | the word itself, with a check: spelled correctly |
| `spell tresspass` | up to eight suggestions, the top one carrying a small *Did you mean* label; `Enter` copies the picked one |
| `spell recieve` | `receive` first (in the online list too): the classic rearrangement |
| `spell two words` | only the first word is checked (`two`); one word at a time |

`spell` is the extension's declared prefix: typing it shows *Check the spelling · word: the word you are not sure of* under the search field and the `<word>` placeholder after the caret, `/` lists it with every other command, and Settings → Spell check → **Prefix** renames it. The extension's own screen (open it from Extensions) is the same check without the prefix: type the word straight into it.

Where each answer comes from, in order:

1. **The word is in the bundled list.** One row: the word, a check mark, nothing else. No network call happens for a word the offline list knows.
2. **The word is not.** The online suggestions, debounced by the same 350 ms pause Translate uses and cached for the session, replace the offline ones as they arrive. The words that fail stay failed for thirty seconds before a retry; three failures in a row hold the service off for a minute.
3. **The online service is unreachable, or you turned it off.** The bundled list answers with its own suggestions, and a quiet row says it did.

Every row copies its word on Enter and pastes it into the previous window on Ctrl+Enter, whatever list it came from, so acting on a row while the online answer is still on its way is safe.

## Settings

Keystroke Settings → Spell check:

- **Use the online suggestions**: on by default. Off turns the extension fully offline: only the bundled list answers, and unknown words get no suggestions when the list has none for them.

## Limits and dependencies

- One word at a time; the first token of the query is the one checked.
- The bundled list is [SymSpell](https://github.com/wolfgarbe/SymSpell)'s `frequency_dictionary_en_82_765.txt` (the SymSpell source is MIT licensed; the list's frequencies come from Google Books corpora): 82,833 tokens of common English, appraised once when the extension turns on (about half a second). The check mark means the word is in this list, so a real but uncommon word may score without it when you are offline.
- The offline suggestions scan the words that share your word's first or second letter, within two characters of its length. A mistake that rewrites both of the first two characters (typing `lello` for `hello`) can go unsuggested; the online suggestions have no such restriction.
- Nothing writes to disk: the word cache and the failure bookkeeping live in memory for the session. There is no setup step.
- The online part runs `curl` (no key, no account) against `api.datamuse.com`; the typed word travels in the URL, the way any web address does. Turn it off in Settings to keep everything local.
- Like every extension, this one runs unsandboxed inside your shell with your permissions once you turn it on. `Service.qml` is short; read it first.

## Layout

- `extension.json`: name, version, description, icon, the `spell` command and its examples, readable without loading any code.
- `Service.qml`: the provider object, the dictionary file load, the curl processes, the caches and the backoff.
- `core/Spell.js`: the query parse, the dictionary parse, membership, the offline scorer and row building as pure functions.
- `tests/tst_spell.qml`: unit tests for all of it, run by `bin/keystroke check-extensions`. The last test also parses the shipped dictionary file itself; it needs `QML_XHR_ALLOW_FILE_READ=1` in the environment (Qt 6.12 blocks local file reads by default) and skips without it.

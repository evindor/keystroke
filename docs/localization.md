# Localization

Keystroke ships English and German catalogs and follows the platform's language. On Omarchy 4.5+, the `i18n/OmarchyTranslations.qml` bridge uses `Commons.Translations` and Omarchy's selected language, number formatting and direction. On older Omarchy 4.x, `i18n/Locale.qml` selects a catalog from the process's system locale (`LC_ALL`, then `LC_MESSAGES`, then `LANG`, with `Qt.locale()` as a fallback). The older path never reads the newer language-choice file. Its language changes when the shell starts with another system locale.

The bridge is loaded lazily after the translation API is detected at `<omarchyPath>/shell/Commons/Translations.qml`. Availability rather than a version subprocess also handles development checkouts and backports. The main palette, providers and ordinary UI components do not import the new types, so an older shell does not need `Commons.I18n`, `Commons.Translations` or newer directional-key helpers. The optional bridge is excluded from lint on shells without its API.

## Catalogs and coverage

Flat JSON catalogs live in `i18n/<language>.json`. Current Keystroke-owned messages use the English source phrase as the key; keep keys stable when adding translations. Catalogs fall back from a regional code to its base language, then English, then the key. Empty or invalid catalogs degrade to English. The legacy plural rules are vendored from Omarchy under its MIT license so catalogs use the same CLDR categories on both paths.

The initial English/German catalogs cover palette chrome, schema-generated settings, bundled provider navigation, common action verbs and Codex conversation controls. They do not translate application/extension names, filenames, clipboard or conversation content, queries, command prefixes, configuration keys, enum values, arbitrary provider output, or server/model errors. Third-party extension UI needs its own catalog; it is not translated automatically. This is a localization foundation, not a claim that every dynamic English message in every provider or bundled extension has been extracted.

## Owned messages

In `Keystroke.qml`, use `root.t("Search %1…", [title])`. A whole message is translated before substitution. `core/Locale.js` substitutes placeholders once, so a user value containing `%2` stays literal. Do not construct a sentence by concatenating translated fragments, translate a file path or put localized values into action payloads.

`root.tn("%1 extension", count)` selects a plural form and substitutes the locale-formatted count. Catalog values for plural messages are objects:

```json
{
  "%1 extension": { "one": "%1 extension", "other": "%1 extensions" }
}
```

German also uses `one` and `other`; additional languages need their appropriate CLDR forms. Use `host.formatNumber(value, decimals)` for displayed numbers and `Qt.locale(host.formatLocale)` for displayed dates. Keep machine-readable/copied values unchanged unless the feature explicitly offers localized output.

Bindings calling `t` update live on Omarchy 4.5. The palette also invalidates provider/Smart Match caches and the generated settings tree when the catalog changes. Settings retain their original English paths as search terms. Existing imperative status/error messages and third-party output can retain the language in which they were generated until that operation is run again.

`LayoutMirroring`, directional keys and navigation glyphs follow the language direction; user-entered and returned content remains literal. The shipped German strings are left-to-right. The Arabic-language fallback is tested for direction, but this does not constitute a reviewed Arabic translation or exhaustive RTL layout verification.

## Provider and extension API (optional API 1 additions)

Query/catalog contexts expose `language`, `formatLocale`, `t(key, args)`, `tn(key, count)` and `formatNumber(value, decimals)`. The same methods exist on `ctx.host`. `ctx.t` reads Keystroke's catalog and is useful for shared actions such as `Open`; private extension messages should use the extension's own catalog.

An enabled extension can create a translator without importing files outside its directory or requiring the new Omarchy types:

```qml
property var strings: null
function query(ctx) {
  if (!strings && typeof ctx.host.createTranslator === "function")
    strings = ctx.host.createTranslator(root, Qt.resolvedUrl("i18n"))
  var title = strings ? strings.t("title", "My extension") : "My extension"
  return [{ id: "open", title: title, action: { type: "noop" } }]
}
```

Ship `i18n/en.json`, `i18n/de.json`, etc. in the extension directory. The parent passed to `createTranslator(owner, directory)` owns the translator, so destroying the extension also releases its file watchers. Do not create one per query; retain it on the service. If the extension caches generated rows, connect the translator's `stringsChanged` signal to `host.requery()` so the cache can rebuild. Guard these optional methods when supporting older Keystroke releases. A provider view receives `host`, so it can use the same interface.

## Adding a language

Copy `en.json` to the desired Omarchy code, translate the values, preserve `%1` placeholders and add the language's plural forms. Keep brands, command examples, units and keyboard keys unchanged. Regional catalogs may contain only overrides. Run `tests/i18n_catalog_check.py`, `tests/legacy_i18n_check.py` and `tests/palette_i18n_check.py`, plus the regular suite. The native live-switch check is skipped on older Omarchy installations; the legacy check always runs without the 4.5 types.

Existing English-based integration fixtures explicitly pin a private test language file, so a developer's desktop language cannot change their assertions. Tests use synthetic content and temporary language files; they do not change the real OS language or open real clipboard or conversation stores.

# Currency

Currency conversion for the [Keystroke](../../README.md) command palette. Type `100 usd to eur` and the answer is a row you can copy; the rates are the European Central Bank's reference rates from [Frankfurter](https://frankfurter.dev), downloaded once a day the first time you convert something, and kept so the palette still answers offline.

Written by [Gunhan Selas](https://github.com/gunhanselas) as [keystroke-currency](https://github.com/gunhanselas/keystroke-currency) and ported into Keystroke's extension folder when extensions moved into this repository.

## Turn it on

Extensions ship with Keystroke switched off. Type `ext`, open **Extensions → Currency**, and confirm **Enabled** (or Keystroke Settings → Currency → Enabled).

## Use

| Query | Result |
| --- | --- |
| `100 usd to eur` · `100 usd in eur` | 100 US dollars in euros |
| `12,50 eur in tl` | a decimal comma works; `tl` is Turkish lira |
| `$100 in try` · `£20 to usd` · `100€ to $` | symbols: `$ € £ ¥ ₺ ₹ ₩ ₽ ₴ ₪ ฿` |
| `129usd` · `129 usd` | into your preferred currency (Settings → Currency) |

Enter copies the result (`5,000.00 TRY`); Ctrl+Enter copies the bare number. The row's subtitle shows the rate and the date it is from; the preview adds when the table was fetched and where it came from.

Only currencies Frankfurter lists are answered (about 50, the ECB's set plus a few more), so `100 kgs to lbs` is left to the unit converter.

## Settings

Keystroke Settings → Currency:

- **Preferred currency**: the target for amounts that name none, like `129usd`. Empty (the default) uses your locale's currency.
- **Target for amounts that name none**: *Preferred currency* (default), or *The one I convert to most*, which counts the targets you name in explicit conversions (`100 usd to eur`, after a moment on the row or on Enter) and uses the most frequent one.

Values live under `providers.currency` in `~/.config/omarchy/keystroke.json`.

## How the rates get here

The first conversion of the day (after 04:00 local time, so the ECB's afternoon publication is always included) runs `curl` against `https://api.frankfurter.dev/v2/rates`, which returns every rate against the euro in one request. The table is checked (euro base, positive rates, dated rows, the major currencies present) and written to `~/.cache/keystroke/currency/rates.json`; every conversion is a cross rate computed from it. Until the first table arrives the row says *Downloading exchange rates…*; if the download fails the last table keeps answering, the preview says the refresh failed, and the next attempt is ten minutes later. Nothing runs in the background, no timer, no service: the download happens only when you ask for a conversion and the table is missing or from an earlier day.

## Limits and dependencies

- Needs `curl` and network access to `api.frankfurter.dev`; the request carries no data of yours. Offline, the last table answers with its date shown.
- Writes `~/.cache/keystroke/currency/rates.json` (the table) and, in automatic mode, `~/.local/state/keystroke/currency/usage.json` (per-currency counts). Nothing else is written; no sudo, no daemons.
- Frankfurter publishes one table per working day; weekend and holiday conversions use Friday's rates, and the row says which date they are from.
- Amounts use a dot or a comma as the decimal separator; thousands separators are not understood.
- Like every extension, this one runs unsandboxed inside your shell with your permissions once you turn it on. `Service.qml` is short; read it first.

## Layout

- `extension.json`: name, version, description and icon for the Extensions screen; read without loading any code.
- `Service.qml`: the provider object (`query`, `activate`, `settings`, `patterns`), the curl process, the two files, the dwell that learns targets.
- `core/Currency.js`: parsing, cross rates, table validation, the refresh decision, the curl argv and the rows as pure functions.
- `tests/tst_currency.qml`: unit tests for the pure functions, run by `bin/keystroke check-extensions`.

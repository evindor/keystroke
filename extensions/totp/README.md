# TOTP Authenticator for Keystroke

Generate and copy time-based one-time passwords (TOTP / 2FA) directly inside the [Keystroke](https://github.com/evindor/keystroke) command palette on Linux (Omarchy).

Ported and enhanced from [raycast-totp](https://github.com/imbriandev/raycast-totp) for macOS.

---

## Features

- **RFC 6238 Compliant**: Computes standards-compliant one-time passwords (SHA-1, SHA-256, SHA-512; 6 to 8 digits; custom step periods from 10s to 120s) entirely in pure JavaScript inside the shell without external runtime lag.
- **Real-Time Countdown**: Countdown seconds (`... · 28s`) and OTP codes update live every second while the palette is open, and automatically roll over to new codes when the period expires.
- **Interactive In-Palette Form View**: Full-screen GUI form to add or edit accounts with live Base32 validation, real-time OTP preview, and a secret key reveal/hide toggle (`Ctrl+H`).
- **Comprehensive Actions Menu**:
  - `↵ Enter`: Copies the current OTP code to clipboard.
  - `Ctrl+↵`: Pastes the code directly into the previously active window.
  - `Alt Actions` (`totp/account/<id>`): Copy OTP, Paste OTP, Copy Secret, Copy `otpauth://` URI, Edit Account, and Delete Account (with double-confirmation).
- **Quick OTP**: Paste a raw Base32 secret key or `otpauth://totp/...` URI to instantly view and copy a temporary one-time password without saving it.
- **Configurable Search Scope**: Hide accounts from the root launcher by default to keep application search clean, or enable root search to find accounts directly without typing `totp`.
- **Encrypted Auto-Backups & Migration**: 100% compatible with Raycast TOTP encrypted backups (AES-256-GCM, PBKDF2 with 100,000 iterations). Supports automated export on account changes as well as manual export/import via GUI and CLI.
- **Zero-Knowledge & Offline**: Runs entirely offline with local user-only storage in `~/.local/state/keystroke/totp/accounts.json`. No network requests, no telemetry, no daemons.

---

## Turn it on

Like all extensions in Keystroke, TOTP ships switched off. To enable:

1. Open the Keystroke palette (`Super+Space`).
2. Type `ext` or open **Extensions → TOTP**.
3. Confirm **Enabled** (or open **Keystroke Settings → TOTP → Enabled**).

---

## Use

| Query | Action |
| --- | --- |
| `totp` | List all saved accounts with live codes and countdown timers |
| `totp github` | Filter accounts by name or issuer |
| `totp add JBSWY3DPEHPK3PXP GitHub` | Add an account directly from Base32 secret and name |
| `totp add otpauth://totp/GitHub:user?secret=...` | Add an account directly from an `otpauth://` URI |
| `totp quick JBSWY3DPEHPK3PXP` | Quick OTP: generate a temporary code without saving |
| `totp JBSWY3DPEHPK3PXP` | Auto-detects Base32 secret and offers Quick OTP |
| `otpauth://totp/...` | Auto-detects pasted URI and offers Quick OTP |
| `totp/manage` | Manage all accounts, trigger manual export, or import backups |

### Keybindings & Actions

* **Account row**:
  * `↵ Enter`: Copy OTP code to clipboard.
  * `Ctrl+↵`: Paste OTP code into active application.
  * Navigating into the account (`totp/account/<id>`): Opens the action list (Copy Secret, Copy URI, Edit, Delete).
* **Form View (`Add / Edit Account`)**:
  * `Tab` / `Shift+Tab`: Navigate between fields.
  * `Ctrl+H`: Toggle secret key visibility (Reveal / Hide).
  * `Ctrl+S` or `Ctrl+Enter`: Save account.
  * `Escape`: Cancel and go back.

---

## Settings

Configurable under **Keystroke Settings → TOTP**:

- **Notification on copy (`notifyOnCopy`)**: Show desktop notification when an OTP code is copied (default: `true`).
- **Search accounts in general launcher (`searchInRoot`)**: Show matching accounts in the main search bar without typing `totp` (default: `false` to prevent cluttering main launcher results).
- **Auto-backup directory (`backupDirectory`)**: Target folder to save encrypted `totp-backup.json` after every account addition, edit, or deletion (e.g. `~/Documents/Backups`).
- **Auto-backup passphrase (`backupPassphrase`)**: Passphrase for AES-256-GCM encryption. Masked as `••••••••` by default.
- **Show backup passphrase (`showBackupPassphrase`)**: Toggle to reveal the passphrase in plain text in Settings for verification (default: `false`).
- **Default digits (`defaultDigits`)**: Number of digits for raw secrets (6 to 8, default: `6`).
- **Default period (`defaultPeriod`)**: Validity interval in seconds (10 to 120, default: `30`).

---

## CLI Utility (`bin/totp-cli`)

A standalone script is included in `bin/totp-cli` for shell scripting and seamless backup migration:

```sh
# List all accounts
./bin/totp-cli list

# Add an account from URI or secret
./bin/totp-cli add "otpauth://totp/GitHub:alice?secret=JBSWY3DP"
./bin/totp-cli add JBSWY3DPEHPK3PXP "Work Google" --issuer Google

# Edit an existing account
./bin/totp-cli edit <account-id> --name "Personal GitHub"

# Delete an account
./bin/totp-cli delete <account-id>

# Export encrypted backup (compatible with raycast-totp)
./bin/totp-cli export my-backup.json --passphrase "my-secure-passphrase"

# Import backup from raycast-totp (or another Keystroke instance)
./bin/totp-cli import totp-backup-mac.json --passphrase "my-secure-passphrase"
```

---

## Limits and dependencies

- **Offline & Local**: No network access, no telemetry, no analytics. All cryptographic calculations (RFC 6238 HMAC-SHA1, HMAC-SHA256, HMAC-SHA512, Base32 decoding) run locally in pure JavaScript.
- **File Access**: Reads and writes only to `~/.local/state/keystroke/totp/accounts.json` with user-only file permissions (`0600`). When auto-backup is enabled, writes an encrypted `totp-backup.json` to the user's chosen directory.
- **Process Execution**: Spawns `mkdir -p` once on startup to ensure the state directory exists. If auto-backup is enabled, runs `bin/totp-cli export` in the background after account changes to produce the encrypted backup. No sudo, no system daemons.
- **No Idle Work**: Like all Keystroke extensions, nothing runs or is instantiated until the user explicitly turns the extension on. The ticking countdown timer triggers only while the palette window is open and displaying TOTP items.
- **Permissions**: Runs unsandboxed inside your shell with standard user permissions.

## Security & Privacy

- **Input Masking**: Both the backup passphrase in Settings and the secret key in the account form are masked (`••••••••`) by default to prevent shoulder-surfing.
- **Cryptographic Compatibility**: Backup encryption uses AES-256-GCM with PBKDF2 key derivation (100,000 iterations, SHA-256), fully compatible with Raycast's export format.


---

## Repository Layout

```
├── extension.json        Extension manifest, command declarations, and patterns
├── Service.qml           QML provider, live ticking timer, and IPC action dispatcher
├── AccountFormView.qml   Interactive form view for adding/editing accounts
├── core/
│   └── TOTP.js           Pure JS RFC 6238 engine, Base32 codec, and palette row builders
├── tests/
│   └── tst_totp.qml      Qt Quick unit test suite (RFC test vectors, storage, search)
├── assets/
│   ├── icon.svg          Vector key icon
│   └── totp-icon.png     Extension brand icon
├── bin/
│   └── totp-cli          CLI management and backup migration tool
└── README.md
```

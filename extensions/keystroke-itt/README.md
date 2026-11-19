# keystroke-ITT · Improve This Text

Select text in a Wayland app, open Keystroke, type `itt`, and press Enter to open ITT. ITT reads the primary selection and sends it to the configured provider. If the app does not expose a primary selection, paste or type the source in the editor and press Enter or click **Improve text**. Use Shift+Enter to insert a line break.

Review the improved text. Press **Enter** or click **Paste text** to replace the selection in the previous app. Press **Ctrl+Enter** or click **Send to clipboard** to copy the result.

## Install

From the root of this checkout:

```sh
mkdir -p ~/.local/share/keystroke/extensions
ln -s "$PWD/extensions/keystroke-itt" ~/.local/share/keystroke/extensions/keystroke-itt
```

Open Keystroke, find **keystroke-ITT** under **Extensions**, and enable it. ITT needs a Keystroke build with provider views and the native paste effect, Python 3, GNU `timeout`, and `wl-clipboard`.

## Configure

Under **Keystroke Settings › keystroke-ITT**, choose **AI provider**, set the corresponding **model** to a model your account can use, and enter the path to the provider's **API key file**. The file should contain only the API key. Keep it outside this checkout and restrict it to your user with `chmod 600`. If the path is blank, ITT uses `OPENAI_API_KEY` or `XAI_API_KEY` from the environment of the running Omarchy shell.

Choose **Omarchy default agent** to use the agent selected in Omarchy. This option currently supports **Codex** and uses the selected Omarchy Codex account and its model configuration. It needs a working, signed-in Codex CLI and uses no ITT API key or model setting. ITT checks Omarchy's selection on each request and shows an error if it is unset or unsupported.

## Limits and dependencies

- Opening the editor runs `timeout` and `wl-paste` once to read the Wayland primary selection. If selection capture fails, enter the text manually. Typing in the editor does not start a request.
- Each submission runs `timeout` and the bundled Python 3 helper. OpenAI and Grok requests read the configured key file or environment variable, then send the model name, fixed instruction, and source text to `api.openai.com` or `api.x.ai` over HTTPS. Provider usage charges apply.
- Omarchy mode runs `omarchy-default-agent`, `omarchy-agent-account-home` when needed, and `codex exec` with an ephemeral session in a temporary working directory. Codex uses the selected account's local configuration and configured backend.
- Paste and copy use Keystroke's clipboard handling. Paste also uses Keystroke's native paste helper to send the shortcut to the previous app. The extension itself keeps text and results in memory. It needs no setup script or runtime downloads of its own.

ITT's fixed instruction aims to improve grammar, clarity, and flow while preserving meaning, tone, and language. Review the result before pasting it.

The extension was written for this contribution with assistance from Codex.

[Keystroke extension guide](https://github.com/evindor/keystroke/blob/main/CONTRIBUTING.md#build-an-extension) · [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat) · [Grok Chat Completions](https://docs.x.ai/developers/rest-api-reference/inference/chat-completions)

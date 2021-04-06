# Speedport Pro command line interface

[![repo-size](https://img.shields.io/github/repo-size/tb1402/speedport_pro_cli?color=red)](https://github.com/tb1402/speedport_pro_cli/)
[![latest-commit](https://img.shields.io/github/last-commit/tb1402/speedport_pro_cli?color=red)](https://github.com/tb1402/speedport_pro_cli/)

[![top-language](https://img.shields.io/github/languages/top/tb1402/speedport_pro_cli?color=red)](https://github.com/tb1402/speedport_pro_cli/) based program to control the home router Speedport Pro from "Deutsche Telekom" via command line.
German: Command line interface für den Speedport Pro

## Table of Contents/Inhalt
- [Dependencies / Abhängigkeiten](#dependencies-abhängigkeiten)
- [Usage / Nutzung](#usage-nutzung)
- [Features](#features)
- [Contribution / Mitwirkung](#contribution-mitwirkung)
- [License / Lizenz](LICENSE)

## Dependencies-Abhängigkeiten
To use this program you will need following configuration and dependencies:
- minimum Python 3
- Argparse `$ pip install argparse`
- requests
- urrlib3
- hashlib
- xmltodict
- tabulate

Um das Tool zu nutzen, wird mindestens **Python 3** und folgende Module benötigt:
- Argparse `$ pip install argparse`
- requests
- urllib3
- hashlib
- xmltodict
- tabulate

## Usage-Nutzung
After you installed all required modules just clone the repository and run `$ python speedport.py`.
For help on available options and their usage see the Wiki section or run the script with `-h` or `--help`.

Nachdem die alle benötigten Module installiert haben. einfach das Repo klonen und `$ python speedport.py` ausführen.
Hilfe zu den Funktion gibt es im Wiki des Repositorys oder mittels der Optionen `-h` oder `--help`.

## Features
Currently available features are:
- WiFi interface information (e.g. connected clients)
- get external IP Address
- print log (with colored output)

Aktuell sind folgende Funktionen implementiert:
- Infomrationen über WLAN-Schnittstellen (z.B. verbundene Geräte)
- Abrufen der externen IP-Adresse
- farbige Ausgabe (mit Gruppierungen) des Systemprotokolls

## Contribution-Mitwirkung
If you want to contribute to this project, just contact me.

Falls sie mitwitrken möchten, kontaktieren sie mich.

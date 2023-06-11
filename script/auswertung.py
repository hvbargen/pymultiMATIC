# Auswertung Arbeitszahl auf monatlicher Basis.

"""
Auswertung Heizung und Warmwasser Energieverbrauch und gewonnene Umweltenergie.

Die Daten müssen zunächsts vom Vaillant-Server heruntergeladen werden (über ein anderes Skript).

Zum Download geht man wie folgt vor:

Anhand des höchsten Dateidatums im Ordner output feststellen,
in welchem Monat der letzte Download erfolgt ist.
Dieser Monat muss als unvollständig betrachtet werden.
Als Startdatum wählt man daher den 01. des entsprechenden Monats,
um den Monat nochmal in Gänze herunterzuladen.

Beispiel:
Der letzte Download erfolgte am 27.04.2023.
Der erste des Monats ist also der 1. April, technisch formatiert 2023-04-01.

Man aktiviert zunächst das Python Environment mittels
cmd.exe
cd (hier)
venv\scripts\activate.bat

Dann startet man den Download zumindest auf Monatsbasis mit:

python script\read_emf_history.py Ba4711 kennwort 2023-04-01 month

Optional kann man zusätzlich auch Downloads auf Wochenbasis oder Tagesbasis starten,
dann eben mit week oder day anstelle von month.

Im Ordner output werden durch den Download Dateien angelegt wie etwa

Wärmepumpe-Warmwasser-Umweltenergie-203-04-01-month.json.


Auswertung:

Die o.g. Dateien mit der Endung "-month.json" werden sämtlich eingelesen.
Der Dateiname besteht aus Präfix, Zeitstempel und Rest.
Das Präfix kennzeichnet, um welche Art von Daten es sich handelt, z.B.

Wärmepumpe-Warmwasser-Umweltenergie.

Dieses Präfix besteht wiederum aus 3 Teilen.
Der erste Teil "Wärmepumpe" oder "Hydraulikstation" kennzeichnet Außen- oder Innen-Gerät,
der zweite Teil ob es um Heizung oder Warmwasser geht,
der dritte Teil ob das verbrauchter Strom oder (vom Gerät gemeldete) gewonnene Umweltenergie geht.
Letzteres gibt es nur bei der Wärmepumpe, nicht bei der Hydraulikstation.

Die Daten der JSON-Dateien werden zusammengerechnet.
Falls es für einen Schlüssel (Feld "key" in der Datei) mehrere Sätze gibt,
dann "gewinnt" der Datei mit dem höheren Wert. Dies sollte dann auch immer der aktuellere Wert sein,
denn alle Verbrauchswerte sind monoton steigend.

Für einen einzelnen "key" kann es bis zu sechhs Werte geben,
entsprechend der sechs verschiedenen Präfixe.

Wir berechnen drei verschiedene Statistiken:

Arbeitszahl Heizung = (Heizung-Stromverbrauch plus Heizung-Umweltenergie) durch Heizung-Stromverbrauch
Arbeitszahl Warmwasser = analog, mit Warmwasser statt Heizung
Arbeitszahl kombiniert = Stromverbrauch + Umweltenergie durch Stromverbrauch.

Diese Arbeitszahl kann je Schlüssel berechnen oder für größere Zeitbereiche (z.B. das Kalenderjahr).

Diese Zahlen werdem am Ende ausgegeben als CSV-Datei.

"""

import json
from pathlib import Path


class WertePaar:
    key: str
    stromverbrauch: float
    umweltenergie:  float

    def __init__(self, key):
        self.key = key
        self.stromverbrauch = 0
        self.umweltenergie = 0

    def __repr__(self) -> str:
        return (f"WertePaar({self.key}: Stromverbrauch: {self.stromverbrauch}, Umweltenergie: {self.umweltenergie})")
    
    def __add__(self, other: "WertePaar") -> "WertePaar":
        if self.key is not None and other.key is not None and other.key != self.key:
            raise AssertionError("Trying to add values for different keys", self.key, other.key)
        wp = WertePaar(self.key)
        wp.stromverbrauch = self.stromverbrauch + other.stromverbrauch
        wp.umweltenergie = self.umweltenergie + other.umweltenergie
        return wp

def read_json_files(folder_name: Path):
    print (f"Read JSON files from {folder_name}...")
    json_data = {}
    for fname in folder_name.iterdir():
        if str(fname).endswith("-month.json"):
            print(fname)
            fname_parts = fname.parts[-1].split("-")
            print(fname_parts)
            device, kind, energy_type = fname_parts[:3]
            year, month, day = fname_parts[3:6]
            last_month = f"{year}-{month}"
            device_data = json_data.setdefault(device, {})
            kind_data = device_data.setdefault(kind, {})
            energy_type_data = kind_data.setdefault(energy_type, {})
            j = json.load(open(fname, "rt", encoding="utf-8"))
            print(j)
            energy_type_data[last_month] = j
    return json_data

def korrigieren(json_data):
    for device, device_data in json_data.items():
        for kind, kind_data in device_data.items():
            for energy_type, energy_type_data in kind_data.items():
                corrected_data = {}
                for month, month_data in energy_type_data.items():
                    for md in month_data:
                        rec = md["body"][0]
                        key = rec["key"]
                        if key not in corrected_data or corrected_data[key]["summaryOfValues"] < rec["summaryOfValues"]:
                            corrected_data[key] = rec
                energy_type_data["corrected"] = corrected_data

def auswerten(json_data):
    kombiniert = "Kombiniert"
    kinds = ["Heizung", "Warmwasser", kombiniert]
    statistik = dict([(kind, {}) for kind in kinds])

    keys = set()
    for kind in kinds:
        if kind == kombiniert:
            continue
        # Stromverbrauch aufsummieren
        for device, device_data in json_data.items():
            for energy_type, energy_type_data in device_data[kind].items():
                corrected_data = energy_type_data["corrected"]
                for key, rec in corrected_data.items():
                    keys.add(key)
                    print(device, energy_type, rec)
                    _wert = rec["summaryOfValues"]
                    try:
                        wert = int(_wert)
                    except:
                        wert = 0
                    if key not in statistik[kind]:
                        statistik[kind][key] = WertePaar(key)
                    wp = statistik[kind][key]
                    if energy_type == "Umweltenergie":
                        wp.umweltenergie += wert
                    else:
                        wp.stromverbrauch += wert

    # Kombiniert berechnen
    null_verbrauch = WertePaar(None)
    for key in keys:
        v1 = statistik["Heizung"].get(key, null_verbrauch)
        v2 = statistik["Warmwasser"].get(key, null_verbrauch)
        v = v1 + v2
        statistik[kombiniert][key] = v

    # quartalsweise und Jahresweise aufsummieren

    for key in sorted(keys):
        yyyy, mm = [int(e) for e in key.split("-")]
        year_key = str(yyyy)
        quarter_key = f"{yyyy}-Q{(mm-1) // 3 + 1}"
        print (year_key, mm, quarter_key)
        for kind in kinds:
            v = statistik[kind].get(key, null_verbrauch)
            if quarter_key not in statistik[kind]:
                statistik[kind][quarter_key] = null_verbrauch
                if year_key not in statistik[kind]:
                    statistik[kind][year_key] = null_verbrauch
            statistik[kind][quarter_key] += v
            statistik[kind][year_key] += v

    print("Verbrauchswerte je Monat/Quartal/Jahr [kWh]")
    for kind in kinds:
        print(f"{kind}:")
        for key in sorted(statistik[kind].keys()):
            v = statistik[kind][key]
            stromverbrauch_kwh = v.stromverbrauch / 1000
            umweltenergie_kwh = v.umweltenergie / 1000
            if stromverbrauch_kwh > 0:
                arbeitszahl = (umweltenergie_kwh + stromverbrauch_kwh) / stromverbrauch_kwh
            else:
                arbeitszahl = 0
            print(f"{key:8s} : Stromverbrauch: {stromverbrauch_kwh:8.1f} Umweltenergie: {umweltenergie_kwh:8.1f} Arbeitszahl: {arbeitszahl:2.2f}")

if __name__ == "__main__":
    json_data = read_json_files(Path("output"))
    korrigieren(json_data)
    auswerten(json_data)
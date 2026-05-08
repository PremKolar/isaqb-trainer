NOTE: this was 99.9% vibe-coded with Claude 🤓.

# iSAQB CPSA-FL Prüfungssimulator – README

Dieses Werkzeug simuliert eine iSAQB CPSA-FL Prüfung auf der Kommandozeile.
Es unterstützt alle drei offiziellen Fragetypen (A, P, K) und berechnet die
Punktzahl exakt nach den Prüfungsregeln (Version 2020.2-DE).

---

## Voraussetzungen

- Python 3.8 oder neuer (keine externen Bibliotheken nötig)

```bash
python --version   # sollte 3.8+ zeigen
```

---

## Dateien

```
exam_simulator/
├── exam_simulator.py   # Das Programm
├── sample_exam.json    # Fertige Beispielprüfung (12 Fragen, 19 Punkte)
└── README.md           # Diese Anleitung
```

---

## Schnellstart

```bash
cd exam_simulator
python exam_simulator.py sample_exam.json
```

---

## Aufrufvarianten

| Befehl | Beschreibung |
|--------|--------------|
| `python exam_simulator.py meine_pruefung.json` | Prüfung mit Sofort-Feedback nach jeder Frage |
| `python exam_simulator.py meine_pruefung.json --no-feedback` | Echter Prüfungsmodus – Feedback nur am Ende |
| `python exam_simulator.py --dump-sample` | Gibt die eingebettete Beispielprüfung als JSON aus |

---

## Eigene Prüfungen erstellen

Ausgangspunkt ist die mitgelieferte `sample_exam.json` oder die Ausgabe von `--dump-sample`.

### Grundstruktur

```json
{
  "exam": {
    "title": "Meine Übungsprüfung",
    "time_limit_minutes": 75,
    "pass_threshold": 0.6,
    "questions": []
  }
}
```

| Feld | Bedeutung |
|------|-----------|
| `title` | Titel der Prüfung (wird beim Start angezeigt) |
| `time_limit_minutes` | Zeitlimit in Minuten (nur informativ, kein Abbruch) |
| `pass_threshold` | Bestehensgrenze als Dezimalzahl, z.B. `0.6` = 60 % |

---

### A-Frage – Einfachauswahl

Genau eine korrekte Antwort. Volle Punktzahl für die richtige Antwort, sonst 0.

```json
{
  "id": 1,
  "type": "A",
  "points": 2,
  "question": "Was ist Softwarearchitektur?",
  "options": [
    {"id": "a", "text": "Die Menge aller Klassen"},
    {"id": "b", "text": "Grundlegende Strukturentscheidungen eines Systems"},
    {"id": "c", "text": "Ein Deployment-Skript"},
    {"id": "d", "text": "Ein Unit-Test-Framework"}
  ],
  "correct": "b"
}
```

---

### P-Frage – Mehrfachauswahl (Pick N)

Genau `required` korrekte Antworten wählen.

**Bewertung:**
- `+points/required` pro richtige Auswahl
- `−points/required` pro falsche Auswahl
- Mehr Kreuze als gefordert → 0 Punkte
- Niemals negative Gesamtpunkte

```json
{
  "id": 2,
  "type": "P",
  "points": 2,
  "required": 2,
  "question": "Welche ZWEI Aussagen zu Microservices sind korrekt?",
  "options": [
    {"id": "a", "text": "Jeder Service hat eine eigene Datenhaltung"},
    {"id": "b", "text": "Services kommunizieren über gemeinsamen Speicher"},
    {"id": "c", "text": "Services können unabhängig deployt werden"},
    {"id": "d", "text": "Microservices sind immer einfacher als Monolithen"}
  ],
  "correct": ["a", "c"]
}
```

---

### K-Frage – Klärungsfrage (Klassifikation)

Jede Option einer von zwei Kategorien zuordnen.

**Bewertung:**
- `+points/n` pro korrekte Zuordnung
- `−points/n` pro falsche Zuordnung
- Nicht zugeordnete Optionen: neutral (weder Plus noch Minus)
- Niemals negative Gesamtpunkte

```json
{
  "id": 3,
  "type": "K",
  "points": 1,
  "question": "Architekturrelevant oder nicht?",
  "categories": ["architekturrelevant", "nicht architekturrelevant"],
  "options": [
    {"id": "a", "text": "Wahl des Datenbankssystems",       "correct": "architekturrelevant"},
    {"id": "b", "text": "Benennung lokaler Variablen",       "correct": "nicht architekturrelevant"},
    {"id": "c", "text": "Kommunikationsprotokoll (REST/gRPC)","correct": "architekturrelevant"}
  ]
}
```

---

## Bewertungsregeln (Kurzübersicht)

| Typ | Richtige Antwort | Falsche Antwort | Keine Antwort | Minimum |
|-----|-----------------|-----------------|---------------|---------|
| **A** | volle Punkte | 0 | 0 | 0 |
| **P** | +pts/N | −pts/N | 0 | 0 |
| **K** | +pts/n | −pts/n | 0 | 0 |

**Bestehensgrenze:** standardmäßig 60 % der möglichen Gesamtpunkte.

---

## Tipps zur Prüfungsvorbereitung

- Üben Sie zunächst **mit Feedback** (`standard-Modus`), um die Erklärungen zu sehen.
- Testen Sie sich dann im **`--no-feedback`-Modus**, um die echte Prüfungssituation zu simulieren.
- Bei K-Fragen lohnt es sich, **unsichere Optionen offen zu lassen** – falsche Zuordnungen kosten Punkte, leere nicht.
- Bei P-Fragen gilt dasselbe: **Lieber weniger wählen als zu viele**, wenn Sie unsicher sind.

#!/usr/bin/env python3
"""
iSAQB CPSA-FL Prüfungssimulator
================================
Unterstützte Fragetypen (gemäß iSAQB-Prüfungsregeln 2020.2-DE):

  A  Einfachauswahl   – genau eine richtige Antwort
  P  Mehrfachauswahl  – genau N richtige Antworten wählen
  K  Klärungsfrage    – jede Option einer von zwei Kategorien zuordnen

Verwendung:
  python exam_simulator.py sample_exam.json
  python exam_simulator.py exam.json --no-feedback
  python exam_simulator.py --dump-sample > meine_pruefung.json

JSON-Struktur:
  {
    "exam": {
      "title":              "...",          // Titel der Prüfung
      "time_limit_minutes": 75,            // nur informativ
      "pass_threshold":     0.6,           // 60% zum Bestehen
      "questions": [ ... ]
    }
  }

  A-Frage:
    { "id": 1, "type": "A", "points": 1|2,
      "question": "...",
      "options": [{"id": "a", "text": "..."}, ...],
      "correct": "b" }

  P-Frage:
    { "id": 2, "type": "P", "points": 1|2, "required": N,
      "question": "...",
      "options": [{"id": "a", "text": "..."}, ...],
      "correct": ["a", "c"] }

  K-Frage:
    { "id": 3, "type": "K", "points": 1|2,
      "question": "...",
      "categories": ["Kategorie1", "Kategorie2"],
      "options": [{"id": "a", "text": "...", "correct": "Kategorie1"}, ...] }
"""

import argparse
import json
import os
import sys
import time


# ── Helpers ──────────────────────────────────────────────────────────────────

def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def load_exam(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def validate_exam(data: dict) -> None:
    """Raise ValueError with a descriptive message on structural problems."""
    if "exam" not in data:
        raise ValueError("Top-level key 'exam' fehlt.")
    exam = data["exam"]
    if "questions" not in exam or not isinstance(exam["questions"], list):
        raise ValueError("'exam.questions' fehlt oder ist keine Liste.")
    for i, q in enumerate(exam["questions"], 1):
        qtype = str(q.get("type", "")).upper()
        if qtype not in ("A", "P", "K"):
            raise ValueError(f"Frage {i}: unbekannter Typ '{q.get('type')}'.")
        if "points" not in q or q["points"] not in (1, 2):
            raise ValueError(f"Frage {i}: 'points' muss 1 oder 2 sein.")
        if "question" not in q:
            raise ValueError(f"Frage {i}: 'question' fehlt.")
        if "options" not in q or not q["options"]:
            raise ValueError(f"Frage {i}: 'options' fehlt oder ist leer.")
        if qtype == "A" and "correct" not in q:
            raise ValueError(f"Frage {i}: 'correct' fehlt.")
        if qtype == "P":
            if "correct" not in q or "required" not in q:
                raise ValueError(f"Frage {i}: 'correct' und 'required' werden benötigt.")
        if qtype == "K":
            if "categories" not in q or len(q["categories"]) != 2:
                raise ValueError(f"Frage {i}: 'categories' muss genau 2 Einträge haben.")
            for opt in q["options"]:
                if "correct" not in opt:
                    raise ValueError(f"Frage {i}: Option '{opt.get('id')}' hat kein 'correct'.")


# ── Scoring ───────────────────────────────────────────────────────────────────

def score_a(question: dict, answer: str) -> float:
    """Full points for the one correct answer; 0 otherwise."""
    if answer and answer == question["correct"]:
        return float(question["points"])
    return 0.0


def score_p(question: dict, answers: list) -> float:
    """
    Pick-N scoring:
      +points/required  per correct selection
      -points/required  per wrong selection
      Never below 0; also 0 if more answers given than required.
    """
    required = question["required"]
    if len(answers) > required:
        return 0.0
    correct_set = set(question["correct"])
    unit = question["points"] / required
    raw = sum(unit if a in correct_set else -unit for a in answers)
    return max(0.0, raw)


def score_k(question: dict, answers: dict) -> float:
    """
    Classification scoring:
      +points/n  per correct assignment
      -points/n  per wrong assignment
      Unanswered options: neutral.
      Never below 0.
    """
    n = len(question["options"])
    unit = question["points"] / n
    raw = 0.0
    for opt in question["options"]:
        if opt["id"] in answers:
            raw += unit if answers[opt["id"]] == opt["correct"] else -unit
    return max(0.0, raw)


# ── Input helpers ─────────────────────────────────────────────────────────────

def ask_a(question: dict) -> str:
    print(f"\n[A-Frage – Einfachauswahl]  {question['points']} Punkt(e)")
    print(f"\n{question['question']}\n")
    for opt in question["options"]:
        print(f"  {opt['id']}) {opt['text']}")
    valid = {opt["id"] for opt in question["options"]}
    while True:
        raw = input("\nIhre Antwort (Enter = überspringen): ").strip().lower()
        if raw == "":
            return ""
        if raw in valid:
            return raw
        print(f"  Ungültig. Bitte eine wählen: {', '.join(sorted(valid))}")


def ask_p(question: dict) -> list:
    req = question["required"]
    print(f"\n[P-Frage – Mehrfachauswahl, genau {req} Antwort(en)]  {question['points']} Punkt(e)")
    print(f"\n{question['question']}\n")
    for opt in question["options"]:
        print(f"  {opt['id']}) {opt['text']}")
    valid = {opt["id"] for opt in question["options"]}
    while True:
        raw = input(f"\nIhre {req} Antwort(en), kommagetrennt (z.B. a,c),"
                    " Enter = leer abgeben: ").strip().lower()
        if raw == "":
            return []
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        if len(parts) != len(set(parts)):
            print("  Keine doppelten Angaben erlaubt.")
            continue
        if not all(p in valid for p in parts):
            print(f"  Ungültig. Bitte aus: {', '.join(sorted(valid))}")
            continue
        return parts


def ask_k(question: dict) -> dict:
    cats = question["categories"]
    print(f"\n[K-Frage – Klärungsfrage]  {question['points']} Punkt(e)")
    print(f"\n{question['question']}\n")
    for opt in question["options"]:
        print(f"  {opt['id']}) {opt['text']}")
    print(f"\n  1 = {cats[0]}")
    print(f"  2 = {cats[1]}")
    print("  Enter = diese Option überspringen\n")
    answers = {}
    for opt in question["options"]:
        while True:
            raw = input(f"  {opt['id']}) [1/2/Enter]: ").strip()
            if raw == "":
                break
            if raw == "1":
                answers[opt["id"]] = cats[0]
                break
            if raw == "2":
                answers[opt["id"]] = cats[1]
                break
            print("    Bitte 1, 2 oder Enter eingeben.")
    return answers


# ── Feedback ──────────────────────────────────────────────────────────────────

def feedback_a(question: dict, answer: str, score: float) -> None:
    correct = question["correct"]
    correct_text = next(o["text"] for o in question["options"] if o["id"] == correct)
    if score == question["points"]:
        print(f"\n  ✓  Richtig!  ({score:.2f} / {question['points']} Punkte)")
    else:
        given = answer if answer else "(keine Antwort)"
        print(f"\n  ✗  Falsch.  Ihre Antwort: {given}")
        print(f"     Richtige Antwort: {correct}) {correct_text}")
        print(f"     (0 / {question['points']} Punkte)")


def feedback_p(question: dict, answers: list, score: float) -> None:
    correct_set = set(question["correct"])
    correct_texts = [
        f"{o['id']}) {o['text']}" for o in question["options"] if o["id"] in correct_set
    ]
    given = ", ".join(answers) if answers else "(keine)"
    mark = "✓" if score == question["points"] else ("~" if score > 0 else "✗")
    print(f"\n  Richtige Antworten: {', '.join(correct_texts)}")
    print(f"  Ihre Antworten:     {given}")
    print(f"  {mark}  ({score:.2f} / {question['points']} Punkte)")


def feedback_k(question: dict, answers: dict, score: float) -> None:
    print()
    for opt in question["options"]:
        given = answers.get(opt["id"])
        if given is None:
            mark, given_str = "·", "(nicht beantwortet)"
        elif given == opt["correct"]:
            mark, given_str = "✓", given
        else:
            mark, given_str = "✗", given
        print(f"  {mark}  {opt['id']}) {opt['text']}")
        print(f"       Korrekt: {opt['correct']}   Ihre Antwort: {given_str}")
    overall = "✓" if score == question["points"] else ("~" if score > 0 else "✗")
    print(f"\n  {overall}  ({score:.2f} / {question['points']} Punkte)")


# ── Exam loop ─────────────────────────────────────────────────────────────────

def run_exam(exam_data: dict, feedback: bool = True) -> None:
    exam = exam_data["exam"]
    questions = exam["questions"]
    total_possible = sum(q["points"] for q in questions)
    threshold = float(exam.get("pass_threshold", 0.6))

    print(f"\n{'═' * 64}")
    print(f"  {exam.get('title', 'iSAQB CPSA-FL Prüfungssimulator')}")
    print(f"{'═' * 64}")
    print(f"  Fragen:           {len(questions)}")
    print(f"  Punkte gesamt:    {total_possible}")
    min_pts = total_possible * threshold
    print(f"  Bestehensgrenze: {threshold * 100:.0f}%  ({min_pts:.1f} Punkte)")
    if "time_limit_minutes" in exam:
        print(f"  Zeitlimit:        {exam['time_limit_minutes']} Minuten")
    print(f"{'═' * 64}")
    input("\n  Drücken Sie Enter zum Starten …\n")

    scores = []
    start = time.monotonic()

    for idx, q in enumerate(questions, 1):
        clear_screen()
        elapsed_min = (time.monotonic() - start) / 60
        print(f"Frage {idx}/{len(questions)}  │  Typ: {q['type']}-Frage  "
              f"│  Zeit: {elapsed_min:.1f} min")
        print("─" * 64)

        qtype = q["type"].upper()
        if qtype == "A":
            ans = ask_a(q)
            sc = score_a(q, ans)
            if feedback:
                feedback_a(q, ans, sc)
        elif qtype == "P":
            ans = ask_p(q)
            sc = score_p(q, ans)
            if feedback:
                feedback_p(q, ans, sc)
        elif qtype == "K":
            ans = ask_k(q)
            sc = score_k(q, ans)
            if feedback:
                feedback_k(q, ans, sc)
        else:
            print(f"  Unbekannter Fragetyp '{q['type']}' – übersprungen.")
            sc = 0.0

        scores.append(sc)
        if feedback:
            input("\n  [Enter für nächste Frage …]")

    # ── Results ───────────────────────────────────────────────────────────────
    elapsed_min = (time.monotonic() - start) / 60
    total = sum(scores)
    pct = total / total_possible if total_possible else 0.0
    passed = pct >= threshold

    clear_screen()
    print(f"\n{'═' * 64}")
    print("  AUSWERTUNG")
    print(f"{'═' * 64}")
    print(f"  Dauer:            {elapsed_min:.1f} Minuten")
    print(f"  Erreichte Punkte: {total:.2f} / {total_possible}")
    print(f"  Prozentsatz:      {pct * 100:.1f}%")
    print(f"  Bestehensgrenze: {threshold * 100:.0f}%")
    status = "✓  BESTANDEN" if passed else "✗  NICHT BESTANDEN"
    print(f"  Ergebnis:         {status}")
    print(f"{'═' * 64}\n")

    print("  Detailübersicht:")
    for i, (q, sc) in enumerate(zip(questions, scores), 1):
        mark = "✓" if sc == q["points"] else ("~" if sc > 0 else "✗")
        print(f"  {mark}  Frage {i:2d} ({q['type']}):  {sc:.2f} / {q['points']} Pt.")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="exam_simulator",
        description="iSAQB CPSA-FL Prüfungssimulator (Typen A, P, K)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Beispiele:\n"
            "  python exam_simulator.py sample_exam.json\n"
            "  python exam_simulator.py exam.json --no-feedback\n"
            "  python exam_simulator.py --dump-sample > meine_pruefung.json\n"
        ),
    )
    parser.add_argument("exam_file", nargs="?", help="Pfad zur JSON-Prüfungsdatei")
    parser.add_argument(
        "--no-feedback",
        action="store_true",
        help="Kein Sofort-Feedback nach jeder Frage (echter Prüfungsmodus)",
    )
    parser.add_argument(
        "--dump-sample",
        action="store_true",
        help="Gibt die eingebettete Beispiel-Prüfung als JSON aus und beendet das Programm",
    )
    args = parser.parse_args()

    if args.dump_sample:
        print(json.dumps(SAMPLE_EXAM, ensure_ascii=False, indent=2))
        return

    if not args.exam_file:
        parser.print_help()
        sys.exit(1)

    try:
        data = load_exam(args.exam_file)
    except FileNotFoundError:
        sys.exit(f"Fehler: Datei nicht gefunden – {args.exam_file}")
    except json.JSONDecodeError as exc:
        sys.exit(f"Fehler: Ungültiges JSON – {exc}")

    try:
        validate_exam(data)
    except ValueError as exc:
        sys.exit(f"Fehler in der Prüfungsdatei: {exc}")

    run_exam(data, feedback=not args.no_feedback)


# ── Embedded sample exam ──────────────────────────────────────────────────────

SAMPLE_EXAM = {
    "exam": {
        "title": "iSAQB CPSA-FL – Übungsprüfung",
        "time_limit_minutes": 75,
        "pass_threshold": 0.6,
        "questions": [

            # ── A-Fragen ────────────────────────────────────────────────────

            {
                "id": 1,
                "type": "A",
                "points": 2,
                "question": (
                    "Was bezeichnet der Begriff 'Softwarearchitektur' am treffendsten?"
                ),
                "options": [
                    {"id": "a", "text": "Die Summe aller Klassen und Methoden eines Systems"},
                    {"id": "b", "text": (
                        "Die grundlegenden Strukturentscheidungen eines Systems sowie "
                        "die Prinzipien, die seinen Entwurf und seine Evolution leiten"
                    )},
                    {"id": "c", "text": "Die technische Betriebsdokumentation eines Systems"},
                    {"id": "d", "text": "Ein konkretes Entwurfsmuster für Benutzeroberflächen"}
                ],
                "correct": "b"
            },

            {
                "id": 2,
                "type": "A",
                "points": 1,
                "question": (
                    "Welches der folgenden Muster beschreibt KEINE Architekturstil?"
                ),
                "options": [
                    {"id": "a", "text": "Schichtenarchitektur (Layered Architecture)"},
                    {"id": "b", "text": "Microservices"},
                    {"id": "c", "text": "Event-Driven Architecture"},
                    {"id": "d", "text": "Singleton"}
                ],
                "correct": "d"
            },

            {
                "id": 3,
                "type": "A",
                "points": 2,
                "question": (
                    "Welche Aussage zum arc42-Template ist KORREKT?"
                ),
                "options": [
                    {"id": "a", "text": "arc42 schreibt genau vor, welche Technologien zu verwenden sind"},
                    {"id": "b", "text": (
                        "arc42 ist ein praxiserprobtes Template zur Dokumentation "
                        "von Softwarearchitekturen, das aus 12 Abschnitten besteht"
                    )},
                    {"id": "c", "text": "arc42 ersetzt vollständig die Anforderungsanalyse"},
                    {"id": "d", "text": "arc42 ist ausschließlich für Java-Projekte geeignet"}
                ],
                "correct": "b"
            },

            {
                "id": 4,
                "type": "A",
                "points": 1,
                "question": (
                    "Was beschreibt das Prinzip 'Separation of Concerns'?"
                ),
                "options": [
                    {"id": "a", "text": "Jede Klasse hat genau einen Konstruktor"},
                    {"id": "b", "text": "Funktionalität wird in klar abgegrenzten, "
                                        "verantwortlichen Einheiten organisiert"},
                    {"id": "c", "text": "Alle Datenbankzugriffe werden zentralisiert"},
                    {"id": "d", "text": "Schnittstellen dürfen nur synchron kommunizieren"}
                ],
                "correct": "b"
            },

            {
                "id": 5,
                "type": "A",
                "points": 2,
                "question": (
                    "Welche Sicht der ISO/IEC 25010 beschreibt "
                    "Softwarequalität aus Benutzerperspektive?"
                ),
                "options": [
                    {"id": "a", "text": "Product Quality"},
                    {"id": "b", "text": "System Quality"},
                    {"id": "c", "text": "Quality in Use"},
                    {"id": "d", "text": "Process Quality"}
                ],
                "correct": "c"
            },

            # ── P-Fragen ────────────────────────────────────────────────────

            {
                "id": 6,
                "type": "P",
                "points": 2,
                "required": 3,
                "question": (
                    "Welche DREI der folgenden sind Qualitätsmerkmale gemäß ISO/IEC 25010 "
                    "(Produktqualität)?"
                ),
                "options": [
                    {"id": "a", "text": "Zuverlässigkeit (Reliability)"},
                    {"id": "b", "text": "Refactoring"},
                    {"id": "c", "text": "Sicherheit (Security)"},
                    {"id": "d", "text": "Wartbarkeit (Maintainability)"},
                    {"id": "e", "text": "Deployment-Pipeline"}
                ],
                "correct": ["a", "c", "d"]
            },

            {
                "id": 7,
                "type": "P",
                "points": 2,
                "required": 2,
                "question": (
                    "Welche ZWEI der folgenden Aussagen zu Microservices sind KORREKT?"
                ),
                "options": [
                    {"id": "a", "text": "Jeder Microservice besitzt eine eigene, unabhängige Datenhaltung"},
                    {"id": "b", "text": "Microservices kommunizieren ausschließlich über gemeinsamen Speicher"},
                    {"id": "c", "text": "Microservices können unabhängig voneinander deployt werden"},
                    {"id": "d", "text": "Eine Microservice-Architektur vereinfacht immer die Entwicklung "
                                        "gegenüber einem Monolithen"}
                ],
                "correct": ["a", "c"]
            },

            {
                "id": 8,
                "type": "P",
                "points": 1,
                "required": 2,
                "question": (
                    "Welche ZWEI Techniken werden typischerweise zur Architekturbewertung eingesetzt?"
                ),
                "options": [
                    {"id": "a", "text": "ATAM (Architecture Tradeoff Analysis Method)"},
                    {"id": "b", "text": "Scrum Sprint Review"},
                    {"id": "c", "text": "Qualitative Szenario-basierte Bewertung"},
                    {"id": "d", "text": "Continuous Integration Pipeline"}
                ],
                "correct": ["a", "c"]
            },

            {
                "id": 9,
                "type": "P",
                "points": 2,
                "required": 3,
                "question": (
                    "Welche DREI der folgenden Aussagen beschreiben Aufgaben "
                    "eines Softwarearchitekten?"
                ),
                "options": [
                    {"id": "a", "text": "Technologieentscheidungen treffen und begründen"},
                    {"id": "b", "text": "Jede einzelne Codezeile selbst schreiben"},
                    {"id": "c", "text": "Architekturentscheidungen kommunizieren und dokumentieren"},
                    {"id": "d", "text": "Qualitätsanforderungen mit Stakeholdern klären"},
                    {"id": "e", "text": "Das Projektbudget verwalten"}
                ],
                "correct": ["a", "c", "d"]
            },

            # ── K-Fragen ────────────────────────────────────────────────────

            {
                "id": 10,
                "type": "K",
                "points": 1,
                "question": (
                    "Sind die folgenden Entscheidungen architekturrelevant "
                    "oder nicht architekturrelevant?"
                ),
                "categories": ["architekturrelevant", "nicht architekturrelevant"],
                "options": [
                    {
                        "id": "a",
                        "text": "Wahl des Datenbank-Management-Systems (RDBMS vs. NoSQL)",
                        "correct": "architekturrelevant"
                    },
                    {
                        "id": "b",
                        "text": "Benennung privater lokaler Variablen in einer Methode",
                        "correct": "nicht architekturrelevant"
                    },
                    {
                        "id": "c",
                        "text": "Kommunikationsprotokoll zwischen Frontend und Backend (REST vs. gRPC)",
                        "correct": "architekturrelevant"
                    },
                    {
                        "id": "d",
                        "text": "Anzahl der Leerzeichen zur Code-Einrückung",
                        "correct": "nicht architekturrelevant"
                    }
                ]
            },

            {
                "id": 11,
                "type": "K",
                "points": 2,
                "question": (
                    "Ordnen Sie die folgenden Qualitätsmerkmale zu: "
                    "Handelt es sich um ein funktionales oder nicht-funktionales Merkmal?"
                ),
                "categories": ["nicht-funktional", "funktional"],
                "options": [
                    {
                        "id": "a",
                        "text": "Performance-Effizienz (z.B. Antwortzeit < 200 ms)",
                        "correct": "nicht-funktional"
                    },
                    {
                        "id": "b",
                        "text": "Korrekte Berechnung einer Mehrwertsteuer",
                        "correct": "funktional"
                    },
                    {
                        "id": "c",
                        "text": "Verfügbarkeit (99,9% Uptime)",
                        "correct": "nicht-funktional"
                    },
                    {
                        "id": "d",
                        "text": "Benutzeranmeldung mit Benutzername und Passwort",
                        "correct": "funktional"
                    }
                ]
            },

            {
                "id": 12,
                "type": "K",
                "points": 1,
                "question": (
                    "Ordnen Sie die folgenden Architekturmuster zu: "
                    "Handelt es sich um ein Strukturmuster oder ein Integrationsmuster?"
                ),
                "categories": ["Strukturmuster", "Integrationsmuster"],
                "options": [
                    {
                        "id": "a",
                        "text": "Schichtenarchitektur (Layered Architecture)",
                        "correct": "Strukturmuster"
                    },
                    {
                        "id": "b",
                        "text": "Message Broker / Enterprise Service Bus",
                        "correct": "Integrationsmuster"
                    },
                    {
                        "id": "c",
                        "text": "Ports & Adapters (Hexagonal Architecture)",
                        "correct": "Strukturmuster"
                    },
                    {
                        "id": "d",
                        "text": "Publish-Subscribe",
                        "correct": "Integrationsmuster"
                    }
                ]
            }

        ]
    }
}

if __name__ == "__main__":
    main()

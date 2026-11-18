# RETURN-TRANSPORT-743 — geschlossener Rücktransport

18. November 2026. Befugnis: SPECROAD-DECISION-1, Spezifikation 2.4.3.1 und
verification/development_contract.json, Vertrag 4 mit positivem Restbudget.

W.5/W.6 legen Rücktransport und Reviewtrennung fest, jedoch noch kein
vollständiges Dateiinventar, keine lokale Draft-Ableitung und keinen sicheren
Übergang vom festen Entrypoint zur registrierten Hostautorität. Gewählt ist
die additive Detailfestlegung W.5.1: native Basisrekonstruktion, geschlossenes
inhaltsadressiertes Delta, frisches Paketstaging und ein einmaliger privater
Hostkanal zum vorhandenen nativen Writer. Alternativen — Arbeitsbaumkopie,
ausführbarer KI-Entrypoint, Payload direkt in Fachpfaden, importierte Reviews
oder nachträgliche Prüfung — verletzen bestehende Grenzen. Ein zweiter
Schreibmotor wäre größer und würde native Receipts und Sperren duplizieren.

Die fest gebundene öffentliche PatchHarbor-1.8.0-API stellt `apply_guarded`
mit `PatchAdmission` bereit. Dessen unveränderliche vollständige Paketbytes
und Repositorykontext werden unter derselben Sperre vor Payloadschreibzugriff
an die Hostprüfung übergeben. Paket-SHA und erwartetes Ziel werden nativ
geprüft; nur der exakte Boolean True erlaubt Fortsetzung. Das erfüllt die
technische Voraussetzung PH-API-APPLY-GATE; reale Vertragsabnahmen gehören
in die folgenden Apply-Gates, nicht in diesen Dokumentcommit.

Umsetzung: vollständige Gruppen 18.q und 18.r; keine Produktzähleränderung
im Klärungsstand. Kein Ersatz von menschlichem Fachreview, Releasefreigabe oder
fehlenden Plattformnachweisen. Alle betroffenen aktiven Katalogbindungen
verweisen auf die neue Spezifikationsfassung. Vorbereitung ist kein Testerfolg.

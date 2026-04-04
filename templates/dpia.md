# Gegevensbeschermingseffectbeoordeling / Data Protection Impact Assessment (DPIA)

> Conform AVG Artikel 35 / GDPR Article 35
> Preflight Template — EA-raad / EA Board
> Datum / Date: {{DATUM}}
> Opgesteld door / Prepared by: {{AUTEUR}}
> FG/DPO review: {{FG_NAAM}} — {{FG_DATUM}}
> Versie / Version: {{VERSIE}}
> Status: Concept / Ter review FG / Vastgesteld

---

## 1. Context en Scope / Context & Scope

| Veld / Field | Waarde / Value |
|---|---|
| Naam verwerking / Processing name | {{NAAM}} |
| Verantwoordelijke / Controller | {{ZIEKENHUIS_NAAM}} |
| Afdeling / Department | {{AFDELING}} |
| Systeem / System | {{SYSTEEM}} |
| Leverancier / Vendor | {{VENDOR}} |
| Aanleiding DPIA / DPIA trigger | Hoog-risicoverwerking / Nieuwe technologie / Grootschalige verwerking bijzondere gegevens / AP-lijst / Anders: {{ANDERS}} |

---

## 2. Systematische Beschrijving van de Verwerking / Systematic Description of Processing

> AVG Artikel 35 lid 7 sub a

### 2.1 Welke persoonsgegevens / Personal Data Categories

| Categorie | Gegevens | Bijzonder (Art. 9) |
|---|---|---|
| Identificatiegegevens | {{bijv. naam, BSN, patientnummer}} | Nee |
| Contactgegevens | {{bijv. adres, telefoonnummer, e-mail}} | Nee |
| Gezondheidsgegevens | {{bijv. diagnose, labwaarden, beeldvorming}} | Ja |
| Genetische gegevens | {{bijv. DNA-sequencing}} | Ja |
| Biometrische gegevens | {{bijv. vingerafdruk, gezichtsherkenning}} | Ja |
| Financiele gegevens | {{bijv. verzekeringsnummer, DBC-code}} | Nee |
| Loggegevens | {{bijv. toegangslog, audit trail}} | Nee |
| Anders | {{SPECIFICEER}} | {{JA_NEE}} |

### 2.2 Betrokkenen / Data Subjects

| Categorie | Geschat aantal | Kwetsbare groep |
|---|---|---|
| Patienten | {{AANTAL}} | {{JA_NEE — bijv. kinderen, psychiatrie}} |
| Medewerkers | {{AANTAL}} | Nee |
| Bezoekers | {{AANTAL}} | Nee |
| Anders | {{SPECIFICEER}} | {{JA_NEE}} |

### 2.3 Verwerkingsgrondslag / Legal Basis

**Grondslag Artikel 6 AVG:**
- [ ] 6.1.a — Toestemming
- [ ] 6.1.b — Uitvoering overeenkomst
- [ ] 6.1.c — Wettelijke verplichting
- [ ] 6.1.d — Vitaal belang
- [ ] 6.1.e — Publieke taak
- [ ] 6.1.f — Gerechtvaardigd belang

Toelichting: {{TOELICHTING_ART6}}

**Uitzondering Artikel 9 AVG (bij bijzondere persoonsgegevens):**
- [ ] 9.2.a — Uitdrukkelijke toestemming
- [ ] 9.2.b — Arbeidsrecht / sociale zekerheid
- [ ] 9.2.h — Gezondheidszorg (Wgbo / Wzd / Wvggz)
- [ ] 9.2.i — Volksgezondheid
- [ ] 9.2.j — Wetenschappelijk onderzoek
- [ ] Niet van toepassing

Toelichting: {{TOELICHTING_ART9}}

### 2.4 Doelbinding / Purpose Limitation

| Doel / Purpose | Toelichting |
|---|---|
| Primair doel | {{PRIMAIR}} |
| Secundair doel | {{SECUNDAIR — bijv. kwaliteitsregistratie, onderzoek}} |
| Verenigbaar gebruik | {{TOELICHTING_VERENIGBAARHEID}} |

### 2.5 Bewaartermijn / Retention Period

| Gegevenscategorie | Bewaartermijn | Grondslag termijn |
|---|---|---|
| Medisch dossier | 20 jaar (Wgbo art. 7:454 BW) | Wettelijk |
| {{CATEGORIE}} | {{TERMIJN}} | {{GRONDSLAG}} |
| Loggegevens | {{TERMIJN}} | {{GRONDSLAG}} |

Vernietigingsprocedure: {{PROCEDURE}}

### 2.6 Ontvangers / Recipients

| Ontvanger | Rol | Land | Doorgifte-mechanisme |
|---|---|---|---|
| {{NAAM}} | Verwerker / Gezamenlijk verwerkingsverantwoordelijke / Ontvanger | {{LAND}} | Verwerkersovereenkomst / SCC / Adequaatheidsbesluit / NVT |
| {{NAAM}} | {{ROL}} | {{LAND}} | {{MECHANISME}} |

### 2.7 Datastromen / Data Flows

{{BESCHRIJVING — verwijs eventueel naar bijlage met dataflow-diagram}}

---

## 3. Noodzakelijkheid en Evenredigheid / Necessity & Proportionality

> AVG Artikel 35 lid 7 sub b

| Toets / Assessment | Beoordeling |
|---|---|
| Is de verwerking noodzakelijk voor het doel? | {{JA_NEE + TOELICHTING}} |
| Kan het doel met minder gegevens bereikt worden (dataminimalisatie)? | {{JA_NEE + TOELICHTING}} |
| Zijn er minder ingrijpende alternatieven overwogen? | {{JA_NEE + TOELICHTING}} |
| Staat de inbreuk op privacy in verhouding tot het doel (proportionaliteit)? | {{JA_NEE + TOELICHTING}} |
| Is er een DPIA vereist volgens de AP-lijst? | {{JA_NEE + REFERENTIE}} |

---

## 4. Risico's voor Betrokkenen / Risks to Data Subjects

> AVG Artikel 35 lid 7 sub c

| # | Risico | Kans (L/M/H) | Impact (L/M/H) | Risicoscore | Betrokkenen |
|---|---|---|---|---|---|
| R1 | {{bijv. ongeautoriseerde toegang tot medisch dossier}} | {{H}} | {{H}} | {{HH}} | Patienten |
| R2 | {{bijv. datalek bij verwerker}} | {{M}} | {{H}} | {{MH}} | Patienten |
| R3 | {{bijv. onrechtmatige profilering}} | {{L}} | {{M}} | {{LM}} | {{GROEP}} |
| R4 | {{RISICO}} | {{KANS}} | {{IMPACT}} | {{SCORE}} | {{GROEP}} |
| R5 | {{RISICO}} | {{KANS}} | {{IMPACT}} | {{SCORE}} | {{GROEP}} |

---

## 5. Maatregelen / Mitigating Measures

> AVG Artikel 35 lid 7 sub d

| # | Risico-ref | Maatregel / Measure | Type | Verantwoordelijke | Status |
|---|---|---|---|---|---|
| M1 | R1 | {{bijv. Role-based access control, NEN 7510 §9}} | Technisch | {{FUNCTIE}} | {{Gepland / Geimplementeerd}} |
| M2 | R2 | {{bijv. Verwerkersovereenkomst BOZ-model, audit-clausule}} | Organisatorisch | {{FUNCTIE}} | {{Gepland / Geimplementeerd}} |
| M3 | R1 | {{bijv. Logging conform NEN 7513}} | Technisch | {{FUNCTIE}} | {{Gepland / Geimplementeerd}} |
| M4 | R3 | {{bijv. Pseudonimisering bij secundair gebruik}} | Technisch | {{FUNCTIE}} | {{Gepland / Geimplementeerd}} |
| M5 | {{REF}} | {{MAATREGEL}} | {{TYPE}} | {{FUNCTIE}} | {{STATUS}} |

**Restrisico na maatregelen / Residual risk:** {{BEOORDELING}}

---

## 6. Rechten van Betrokkenen / Data Subject Rights

| Recht / Right | Geborgd | Hoe / How |
|---|---|---|
| Inzage (Art. 15) | {{JA_NEE}} | {{PROCEDURE}} |
| Rectificatie (Art. 16) | {{JA_NEE}} | {{PROCEDURE}} |
| Wissing (Art. 17) | {{JA_NEE}} | {{PROCEDURE — let op Wgbo-uitzondering}} |
| Beperking (Art. 18) | {{JA_NEE}} | {{PROCEDURE}} |
| Dataportabiliteit (Art. 20) | {{JA_NEE}} | {{PROCEDURE}} |
| Bezwaar (Art. 21) | {{JA_NEE}} | {{PROCEDURE}} |

---

## 7. Advies FG/DPO / DPO Opinion

> AVG Artikel 35 lid 2

| Veld / Field | Waarde / Value |
|---|---|
| Advies FG | {{POSITIEF / POSITIEF MET VOORWAARDEN / NEGATIEF}} |
| Voorwaarden | {{VOORWAARDEN}} |
| Opmerkingen | {{OPMERKINGEN}} |
| Voorafgaande raadpleging AP nodig (Art. 36)? | {{JA_NEE + TOELICHTING}} |
| Handtekening FG / DPO sign-off | {{NAAM, DATUM}} |

---

## 8. Verwerkingsregister-entry / Record of Processing Activities (Article 30)

> Conceptinvoer voor het verwerkingsregister van het ziekenhuis.

| Veld (Art. 30 lid 1) | Waarde |
|---|---|
| Naam verwerking | {{NAAM}} |
| Verwerkingsverantwoordelijke | {{ZIEKENHUIS_NAAM}}, {{ADRES}} |
| Contactgegevens FG | {{FG_NAAM}}, {{FG_EMAIL}} |
| Verwerkingsdoeleinden | {{DOELEINDEN}} |
| Categorieen betrokkenen | {{CATEGORIEEN}} |
| Categorieen persoonsgegevens | {{CATEGORIEEN_PG}} |
| Ontvangers | {{ONTVANGERS}} |
| Doorgifte derde landen | {{JA_NEE — LAND, MECHANISME}} |
| Bewaartermijnen | {{TERMIJNEN}} |
| Technische en organisatorische maatregelen (Art. 32) | {{MAATREGELEN_SAMENVATTING}} |

---

## 9. Herbeoordelingsplanning / Review Schedule

| Veld / Field | Waarde / Value |
|---|---|
| Volgende herbeoordeling / Next review | {{DATUM}} |
| Trigger voor tussentijdse herbeoordeling | Wijziging verwerking / Datalek / Nieuwe risico's / Leverancierswijziging |
| Eigenaar herbeoordeling / Review owner | {{FUNCTIE}} |

---

*Template versie 1.0 — Preflight EA Assessment Tool*

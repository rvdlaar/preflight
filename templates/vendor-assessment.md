# Leveranciers- en Productbeoordeling / Vendor & Product Assessment

> Preflight Template — EA-raad / EA Board
> Datum / Date: {{DATUM}}
> Opgesteld door / Prepared by: {{AUTEUR}}
> Versie / Version: {{VERSIE}}

---

## 1. Leveranciersprofiel / Vendor Profile

| Veld / Field | Waarde / Value |
|---|---|
| Leverancier / Vendor | {{VENDOR_NAAM}} |
| KvK / Chamber of Commerce | {{KVK_NUMMER}} |
| Vestigingsland / Country of incorporation | {{LAND}} |
| Website | {{URL}} |
| Contactpersoon / Account manager | {{CONTACT}} |
| Bestaande relatie / Existing relationship | {{JA_NEE}} |
| Huidige contracten / Current contracts | {{REFERENTIES}} |
| Financiele stabiliteit / Financial stability | {{BEOORDELING}} |
| Referenties NL ziekenhuizen / NL hospital references | {{REFERENTIES_ZH}} |

---

## 2. Productbeoordeling / Product Assessment

| Veld / Field | Waarde / Value |
|---|---|
| Productnaam / Product name | {{PRODUCT}} |
| Versie / Version | {{PRODUCT_VERSIE}} |
| Productcategorie / Category | {{CATEGORIE}} |
| Doelgroep / Target users | {{GEBRUIKERS}} |
| Bedrijfsfunctie (ZiRA) | {{ZIRA_BEDRIJFSFUNCTIE}} |
| Informatiedomein (ZiRA) | {{ZIRA_INFORMATIEDOMEIN}} |
| Overlap met bestaand landschap / Landscape overlap | {{OVERLAP}} |
| Integratiemethode / Integration method | HL7v2 / FHIR / REST / DICOM / Anders: {{ANDERS}} |
| Koppelvlakken / Interfaces required | {{INTERFACES}} |
| Hosting model | On-premise / Private cloud / Public cloud / SaaS |
| Dataclassificatie (BIV) | B: {{B}} / I: {{I}} / V: {{V}} |
| Persoonsgegevens / Personal data | {{JA_NEE_TOELICHTING}} |
| Bijzondere persoonsgegevens / Special category data | {{JA_NEE_TOELICHTING}} |

---

## 3. Technology Radar Positie / Tech Radar Position

| Veld / Field | Waarde / Value |
|---|---|
| Aanbevolen ring / Recommended ring | ADOPT / TRIAL / ASSESS / HOLD |
| Rationale | {{RATIONALE}} |
| Voorwaarden ringverandering / Conditions for ring movement | {{VOORWAARDEN}} |
| Gerelateerde items in landschap / Related landscape items | {{GERELATEERD}} |

---

## 4. AIVG 2022 + Module ICT — Compliancechecklist

> Algemene Inkoopvoorwaarden Gezondheidszorg 2022, inclusief Module ICT.
> Vul per item de status in. Lever bewijsstukken aan in de kolom "Evidentieverwijzing."

### 4.1 Informatiebeveiliging / Information Security

- [ ] **NEN 7510 compliance / ISO 27001 certificering**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **NEN 7512 — Vertrouwensbasis elektronisch gegevensverkeer**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **NEN 7513 — Logging van toegang tot patiëntgegevens**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Penetratietest (pentest) — maximaal 12 maanden oud**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

### 4.2 Verwerkersovereenkomst / Data Processing Agreement

- [ ] **Verwerkersovereenkomst conform BOZ-model**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Sub-verwerkers geïdentificeerd en goedgekeurd**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

### 4.3 Hosting en Datalocatie / Hosting & Data Location

- [ ] **Hosting binnen EER (Europese Economische Ruimte)**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Geen doorgifte naar derde landen zonder passend beschermingsniveau**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Datalocatie(s) gespecificeerd en contractueel vastgelegd**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

### 4.4 Exit en Continuïteit / Exit & Continuity

- [ ] **Exit-clausule met data-retour in gangbaar gestructureerd formaat**
  Formaat: {{FORMAAT — bijv. CSV, XML, FHIR, SQL dump}}
  Migratieperiode: {{TERMIJN}}
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Broncode-escrow met individueel afgifterecht**
  Escrow-agent: {{AGENT}}
  Afgiftecondities: {{CONDITIES}}
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **SaaS calamiteitenregeling (continuïteitsregeling bij faillissement/overname)**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

### 4.5 Ondersteuning en Lifecycle / Support & Lifecycle

- [ ] **24-maanden versie-ondersteuning na release nieuwe versie**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Patchbeleid inclusief security-patches — doorlooptijd gespecificeerd**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Releasekalender / Roadmap beschikbaar**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

### 4.6 Acceptatie en Oplevering / Acceptance & Delivery

- [ ] **Acceptatietest — 14 dagen testperiode, two-strike rule**
  Beschrijving: Na eerste afkeuring corrigeert leverancier en levert opnieuw op. Bij tweede afkeuring recht op ontbinding.
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Acceptatiecriteria vooraf schriftelijk vastgelegd**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

### 4.7 SLA en Beschikbaarheid / SLA & Availability

- [ ] **SLA met beschikbaarheidspercentage en meetmethode**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Incident response tijden gedefinieerd per prioriteit**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Datalekprocedure — melding binnen 24 uur**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

### 4.8 Overig / Other

- [ ] **Auditrecht opdrachtgever (of diens vertegenwoordiger)**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

- [ ] **Intellectueel eigendom — rechten op maatwerkonderdelen geregeld**
  Status: {{VOLDAAN / NIET_VOLDAAN / NVT}}
  Evidentieverwijzing: {{BEWIJS}}
  Toelichting: {{TOELICHTING}}

---

## 5. Samenvatting Compliance / Compliance Summary

| Categorie | Voldaan | Niet voldaan | NVT | Opmerkingen |
|---|---|---|---|---|
| Informatiebeveiliging | {{N}} | {{N}} | {{N}} | |
| Verwerkersovereenkomst | {{N}} | {{N}} | {{N}} | |
| Hosting & Datalocatie | {{N}} | {{N}} | {{N}} | |
| Exit & Continuïteit | {{N}} | {{N}} | {{N}} | |
| Ondersteuning & Lifecycle | {{N}} | {{N}} | {{N}} | |
| Acceptatie & Oplevering | {{N}} | {{N}} | {{N}} | |
| SLA & Beschikbaarheid | {{N}} | {{N}} | {{N}} | |
| Overig | {{N}} | {{N}} | {{N}} | |

**Totaal: {{VOLDAAN}} / {{TOTAAL}} items voldaan**

---

## 6. Advies aan EA-raad / Recommendation to EA Board

| Veld / Field | Waarde / Value |
|---|---|
| Advies / Recommendation | Goedkeuren / Goedkeuren met voorwaarden / Afwijzen / Nader onderzoek |
| Voorwaarden / Conditions | {{VOORWAARDEN}} |
| Openstaande risico's / Residual risks | {{RISICOS}} |
| Geschatte doorlooptijd contract / Estimated contract timeline | {{DOORLOOPTIJD}} |

---

*Template versie 1.0 — Preflight EA Assessment Tool*

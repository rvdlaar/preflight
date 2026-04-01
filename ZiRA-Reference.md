# ZiRA (Ziekenhuis Referentie Architectuur) - Comprehensive Reference

## 1. OVERZICHT / OVERVIEW

**Bron:** https://sites.google.com/site/zirawiki/home

De ZiRA (Ziekenhuis Referentie Architectuur) is een verzameling van instrumenten behulpzaam bij het inrichten van de organisatie en informatiehuishouding van Nederlandse ziekenhuizen. De ZiRA heeft in 2018 het Referentiedomeinenmodel ziekenhuizen (RDZ) vervangen.

De naamgeving nader toegelicht:
- **Ziekenhuizen**: het heeft betrekking op de informatievoorziening van ziekenhuizen
- **Referentie**: het biedt een gemeenschappelijke basis, die direct toegepast kan worden, maar die desgewenst ook toegespitst kan worden op specifieke ziekenhuissituaties
- **Architectuur**: het betreft een richtinggevend kader voor de inrichting van organisatie, processen, informatie, applicatie en techniek

### Doelgroep
De ZiRA is primair ontwikkeld voor mensen die zich richten op de inrichting van de informatievoorziening in een ziekenhuis:
- Enterprise- en informatie-architecten
- Informatiemanagers
- Solution-architecten
- Functioneel en technisch ontwerpers
- Functioneel beheerders
- Beleidsmedewerkers, adviseurs

### Doelstellingen
- Referentie bieden voor organisatie- en informatiesysteemontwikkeling
- Consistente terminologie vaststellen tussen ziekenhuizen
- Kennisdeling en best practices bevorderen
- Standaardisatie van processen en applicaties
- Interoperabiliteit in de zorgketen ondersteunen
- Architectuurprojecten versnellen

### Kernprincipes
- Van toepassing op alle Nederlandse ziekenhuizen
- "De ZiRA is van, voor en door de ziekenhuizen"
- Volgt het Nictiz vijflagen-interoperabiliteitsmodel
- Gebruikt ArchiMate modelleertaal
- Beschikbaar voor import in ArchiMate tools (XMI/EAP/Archimate formaat)

---

## 2. METAMODEL

**Bron:** https://sites.google.com/site/zirawiki/home/project-definition/zira-metamodel

Het ZiRA metamodel illustreert de kernconcepten en hun relaties, volgend op het Nictiz vijflagen-interoperabiliteitsmodel.

### Dienstverleningsketen
- Patiënten (of partners, verzekeraars, overheid) consumeren **diensten**
- Diensten worden geleverd door **bedrijfsprocessen**
- Bedrijfsprocessen bestaan uit **werkprocessen**
- Werkprocessen worden typisch geleverd door **bedrijfsfuncties** binnen organisatorische eenheden

### Kernrelaties
- Bedrijfsactiviteiten worden ondersteund door **applicatiefuncties** (geclusterde, leveranciersonafhankelijke functionaliteit)
- **Informatieobjecten** zijn bedrijfsrelevante eenheden van informatie, gegenereerd en gebruikt door activiteiten
- **Domeinen** zijn georganiseerd in bedrijfsdomeinen (Zorg, Onderzoek, Onderwijs, Sturing, Bedrijfsondersteuning) en informatiedomeinen

### Onderscheid Bedrijfsfunctie vs. Bedrijfsproces
Beide representeren sets van activiteiten, maar verschillen fundamenteel:
- **Bedrijfsfuncties**: gekarakteriseerd door gedeelde kennis, vaardigheden of middelen (WAT)
- **Bedrijfsprocessen**: gekarakteriseerd door sequentiële flow richting dienstlevering (HOE)

### ArchiMate Mapping
**Bron:** https://sites.google.com/site/zirawiki/home/project-definition/zira-metamodel/zira-metamodel-in-archimate

De ZiRA is in ArchiMate gemodelleerd met Enterprise Architect (Sparx). De witte/lichtgrijze concepten zijn binnen de ZiRA niet uitgewerkt maar wel in het metamodel opgenomen om de relatie weer te geven.

Interactieve HTML-export beschikbaar:
- Nederlands: https://nictiz.github.io/ZiRA/1.4/nl
- Engels: https://nictiz.github.io/ZiRA/1.4/en

---

## 3. ARCHITECTUURPRINCIPES (12 Principes)

**Bron:** https://sites.google.com/site/zirawiki/home/principes

Vernieuwd in 2023. Per principe: omschrijving, rationale en implicaties, gekoppeld aan de lagen uit het Nictiz Interoperabiliteitsmodel.

Architectuurprincipes zijn "richtinggevende afspraken binnen een organisatie, gebaseerd op overtuigingen hoe de ambities van de organisatie te realiseren." Ze beperken ontwerpvrijheid en zijn afgeleid van organisatiedoelstellingen.

### De Twaalf Principes:

1. **Waardevol** - We doen alleen dingen die waarde toevoegen; initiatieven sluiten aan bij organisatiedoelen
2. **Veilig en vertrouwd** - Veiligheid en privacy staan voorop voor patiënten, medewerkers en bezoekers
3. **Duurzaam** - Toekomstbestendige zorg, verspilling vermijden, beschikbaarheid middelen borgen
4. **Continu** - Continuïteit van zorg door vroegtijdige risico-identificatie en -mitigatie
5. **Mens centraal** - De mens staat centraal in alle organisatieactiviteiten
6. **Samen** - Afstemming met alle stakeholders in zorgnetwerken
7. **Gestandaardiseerd** - Processen volgen open marktstandaarden en best practices
8. **Flexibel** - Oplossingen zijn modulair, uitbreidbaar en vervangbaar met gedefinieerde functies
9. **Eenvoudig** - De eenvoudigste oplossing die aan kernvereisten voldoet wordt geselecteerd
10. **Onder eigenaarschap** - Alle processen, middelen en gegevens hebben aangewezen eigenaren
11. **Datagedreven** - Informatie is gestructureerd voor optimaal hergebruik in bedrijfsvoering en onderzoek
12. **Innovatief** - Innovatie wordt actief nagestreefd

### Toepassing
De principes zijn "niet bedoeld als blauwdruk om één op één over te nemen maar als richtinggevend instrument." Principes zijn per definitie niet volledig consistent, niet volledig en niet stabiel.

Drie niveaus van toepassing:
- **Strategie**: hoe wordt businessstrategie in ICT haalbaar gemaakt
- **Tactiek**: hoe worden strategieën in projecten gerealiseerd
- **Operatie**: welke impact hebben veranderingen op processen en systemen

---

## 4. BUSINESSMODEL

**Bron:** https://sites.google.com/site/zirawiki/home/businessmodel

Gebaseerd op het Business Model Canvas (BMC) van Osterwalder. Het BMC vormt een startpunt voor enterprise architectuur.

### Negen elementen:
1. **Waardepropositie** (centraal) - Wat onderscheidt het ziekenhuis?
2. **Klantsegmenten** - Patiënten, huisartsen, zorgverzekeraars
3. **Communicatiekanalen**
4. **Klantrelaties**
5. **Kernactiviteiten** (diensten)
6. **Mensen en middelen**
7. **Strategische partners**
8. **Kostenstructuur**
9. **Batenstructuur**

"Een goed geformuleerde waardepropositie moet onderscheidend zijn" - zowel richting patiënt, verwijzer als zorgverzekeraar.

---

## 5. BEDRIJFSFUNCTIEMODEL

**Bron:** https://sites.google.com/site/zirawiki/home/bedrijfsfunctiemodel

### Definitie
"Een bedrijfsfunctie wordt gevormd door een set bedrijfsactiviteiten die samenhang vertonen in de benodigde kennis, vaardigheid en middelen."

Aangescherpt in ZiRA: "Een intern gedragselement dat wordt gevormd door een set bedrijfsactiviteiten die samenhang vertoont in de benodigde kennis, vaardigheid en middelen en toegevoegde waarde levert vanuit bedrijfsperspectief."

### Vijf Bedrijfsdomeinen
1. **Zorg** - patiëntgerelateerde activiteiten
2. **Onderzoek**
3. **Onderwijs**
4. **Sturing**
5. **Bedrijfsondersteuning**

### Criteria voor Bedrijfsactiviteiten
1. Vereiste kennis voor uitvoering
2. Benodigde vaardigheden en middelen
3. Werkproces-relatie (teams met gemeenschappelijke kennis, resources en middelen)

### Kernonderscheidingen
- **Bedrijfsfuncties vs. Processen**: Functies beschrijven WAT (volgorde-onafhankelijk), processen beschrijven HOE (chronologisch)
- **Bedrijfsfuncties vs. Diensten**: Diensten zijn extern gericht, functies intern
- **Bedrijfsfuncties vs. Afdelingen**: Functionele indeling vs. organisatorische structuur
- Bedrijfsfuncties blijven doorgaans **stabieler** dan organisatiestructuren

### Relatie tot RDZ
Vervangt het voormalige RDZ-kader. Waar RDZ informatieobjecten integreerde, blijven bedrijfsfuncties gericht op activiteitenclustering.

---

## 6. DIENSTENMODEL

**Bron:** https://sites.google.com/site/zirawiki/home/dienstenmodel

### Definitie
"Een dienst is een afgebakende prestatie, een product of een service, van een persoon of (een onderdeel van de) organisatie."

Diensten zijn bedoeld om aan behoeften van externe klanten of interne afnemers te voldoen. Diensten ontstaan uit het uitvoeren van één of meerdere processen.

### Drie Hoofdcategorieën
1. **Primaire diensten** - zorg, onderzoek, onderwijs
2. **Bedrijfsondersteunende diensten**
3. **Diensten voor sturing en verantwoording**

### Zorgdiensten
- Diagnostiek
- Advies
- Aanvullend onderzoek
- Behandeling (inclusief verzorging en verpleging)

### Dienstkenmerken (7 eigenschappen)
1. Input requirements
2. Verwachte output
3. Verwerkingstijd
4. Aanvragers
5. Gebruikers (patiënten, huisartsen, andere zorgverleners, apothekers)
6. Actoren (opdrachtgever/aanvrager/leverancier/uitvoerder/patiënt)
7. Processen die de dienst realiseren
8. Beperkingen
9. Relaties met andere diensten

### Diensten-oriëntatie
"Diensten nemen vraag en behoeften van de omgeving als uitgangspunt" - helpt vraaggericht te denken. Concentreert zich op het resultaat voor de afnemer.

---

## 7. PROCESMODEL

**Bron:** https://sites.google.com/site/zirawiki/home/procesmodel

### Definitie
"Een proces bestaat uit een keten van activiteiten die nodig is om tot een bepaald resultaat te komen, inclusief activiteiten die deel uitmaken van de ondersteuning of bedrijfsvoering."

### Acht Primaire Bedrijfsprocessen (Niveau 1)
1. **Vaststellen zorgbehoefte** - initiële beoordeling van patiëntbehoeften
2. **Diagnosticeren** - onderzoeks- en diagnostische activiteiten
3. **Aanvullend onderzoek** - verdere diagnostische werkzaamheden
4. **MDO (Multidisciplinair Overleg)** - gezamenlijke besluitvorming
5. **Adviseren** - consultatie en adviesdiensten
6. **Opstellen behandelplan** - planningsfase voor zorg
7. **Behandelen** - therapeutische interventies
8. **Overdragen** - transitie naar vervolgzorg

### Structuur
- Bedrijfsproces → Werkprocessen → Processtappen (bedrijfsactiviteiten)
- Uitgewerkt in ArchiMate-representatie per proces
- "Ook deze uitgewerkte processen zijn nog steeds generiek en globaal"

### Procescyclus (SOEP-denken)
Het klinisch redeneren volgt het hypothetico-deductieve model. SOEP:
- **S**ubjectief - verzamelen informatie
- **O**bjectief - verzamelen informatie
- **E**valuatie - wat is er mis? wat gaan we doen?
- **P**lan - uitvoeren

Dit iteratieve proces vereist flexibele processenopstellingen met ordermanagement:
Aanvraag → Acceptatie → Planning → Uitvoering → Oplevering → Notificatie → Afsluiting

---

## 8. INFORMATIEMODEL

**Bron:** https://sites.google.com/site/zirawiki/home/informatiemodel

### Definitie
"Informatieobjecten zijn eenheden van informatie die relevant zijn vanuit een bedrijfsperspectief" - zoals medische voorgeschiedenis, verslagen en orders.

### Componenten
1. **Informatieobjectencatalogus** - in ZiRA spreadsheets
2. **Informatiemodel Zorg** - logische representatie binnen het Zorgdomein
3. **Objecten in Zorgprocessen** - mapping van informatiegebruik in workflows
4. **Relatie met Zorginformatiebouwstenen (zibs)** - links naar gestandaardiseerde datastructuren
5. **Informatiedomeinenmodel** - organisatorisch kader voor datacategorisatie

### Informatiemodel Zorg
Twee primaire categorieën informatieobjecten:
- **Activiteit-informatieobjecten** (rood): informatie over de activiteit
- **Resultaat-informatieobjecten** (geel): informatie over uitkomsten

Onderscheid tussen "order-based" activiteiten (aangevraagd/gepland) en interventies (niet aangevraagd).

### Genoemde Informatieobjecten in Zorgprocessen
- Voorgeschiedenis
- Actueel medicatieoverzicht (AMO)
- Klacht
- Verwijsinformatie
- Anamneseverslag
- Zorgbehoefte

### Relatie met Zorginformatiebouwstenen (zibs)
- Een informatieobject kan uit één of meerdere zibs bestaan
- Gebaseerd op zib release 2015/2017
- Activiteit-IO's mappen op GeplandeZorgActiviteit of VerpleegkundigeInterventie
- Gemodelleerd als UML-<Trace>-relatie

### Informatiedomeinenmodel
Informatiedomeinen zijn "clusters van sterk verbonden bedrijfsactiviteiten en informatieobjecten." Verschil met bedrijfsfuncties: informatiedomeinen bevatten "naast bedrijfsactiviteiten ook informatieobjecten."

Georganiseerd over vijf bedrijfsdomeinen:
- Zorg (met subdomeinen: (Keten)samenwerking, Consultatie, Behandeling, Aanvullend onderzoek, Zorgondersteuning)
- Onderzoek
- Onderwijs
- Sturing
- Bedrijfsondersteuning

---

## 9. APPLICATIEFUNCTIEMODEL

**Bron:** https://sites.google.com/site/zirawiki/home/applicatiefunctiemodel

### Definitie
"Groeperingen van applicatiefunctionaliteit die een ziekenhuis nodig heeft om haar processen te ondersteunen." Opereert "op een logisch niveau, onafhankelijk van specifieke productkeuzen."

### Inspiratiebronnen
- HL7 EHR-S Functional Model
- Referentie Systeemfuncties Model (RSM)
- HORA applicatiemodel

### Structuur per Bedrijfsdomein

#### STURING
- Beleid & Innovatie
- Proces & Architectuur
- Project & Portfoliomanagement
- Kwaliteitsinformatiemanagement
- Performance & Verantwoording
- Marketing & Contractmanagement

#### ONDERZOEK
- Onderzoek ontwikkeling
- Onderzoekvoorbereiding
- Onderzoeksmanagement
- Researchdatamanagement
- Onderzoekpublicatie

#### ZORG - Samenwerking
- Dossier inzage (patiënt)
- Behandelondersteuning
- Interactie PGO (Persoonlijke Gezondheidsomgeving)
- Patientenforum
- Preventie
- Gezondheidsvragen
- Kwaliteit en tevredenheidsmeting
- Tele-consultatie
- Zelfmonitoring
- Tele-monitoring
- On-line afspraken

#### ZORG - Consultatie & Behandeling
- (verdere applicatiefuncties beschreven in ZiRA spreadsheet)

#### GENERIEKE ICT FUNCTIES
Ondersteunen activiteiten in alle domeinen, 4 categorieën. Beschrijven "veelgebruikte informatietechnische mogelijkheden" zonder zich op infrastructuur te richten.

### Toepassingen
- Vergelijking met eigen applicatielandschap
- Hostingbeslissingen (eigen datacenter, community cloud, public cloud)
- Inzichten in informatiestromen en koppelingen
- Basis voor programma's van eisen
- Ondersteuning informatiemanagement

---

## 10. NETWERKZORG

**Bron:** https://sites.google.com/site/zirawiki/architectuuronderwerpen/netwerkzorg

### Van Ketenzorg naar Netwerkzorg
- **Ketenzorg**: optimaliseert binnen bestaande sectorgrenzen (1e/2e/3e lijn)
- **Netwerkzorg**: integrale zorgvraag van patiënten centraal

### Kenmerkende Verschillen

| Keten-denken | Netwerk-denken |
|---|---|
| Enkelvoudige keten als doel | Meerdere ketens faciliteren |
| Rollen bepalen verantwoordelijkheden | Verantwoordelijkheden op basis van expertise |
| Ketenproces is leidend | Verdeling verantwoordelijkheden leidend |
| Afnemer definieert diensten | Partners selecteren diensten |
| Gemeenschappelijke ketentaal | Aanbieders bepalen eigen taal |
| Lage dynamiek | Hogere dynamiek |

---

## 11. DUURZAAM INFORMATIESTELSEL

**Bron:** https://sites.google.com/site/zirawiki/architectuuronderwerpen/duurzaam-informatiestelsel

Het Informatieberaad Zorg werkt aan drie doelstellingen:
1. **Regie van burgers** - meer controle over gezondheidsgegevens
2. **Medicatieveiligheid** - veiligheid in medicijngebruik
3. **E-health mogelijkheden** - mobiele applicaties, meetapparatuur, webplatforms

---

## 12. i-ZIEKENHUIS PROGRAMMA

**Bron:** https://sites.google.com/site/zirawiki/architectuuronderwerpen/i-ziekenhuis

Programma van, voor en door Nederlandse ziekenhuizen (NVZ/NICTIZ). Twee doelen:
1. Gezamenlijk opzetten en onderhouden van een kader voor informatievoorziening (referentiearchitectuur)
2. Samenwerkingsverband en kennisplatform

Vanaf april 2012 waren ruim 50 ziekenhuizen actief betrokken. Leidde tot ontwikkeling van de ZiRA.

---

## 13. RDZ (VOORGANGER)

**Bron:** https://sites.google.com/site/zirawiki/architectuuronderwerpen/rdz

Het RDZ (Referentiedomeinenmodel Ziekenhuizen) v2.2 was de oorsprong van de ZiRA. Het RDZ bood een "hulp- en communicatiemiddel bij vraagstukken op het snijvlak van zorg en inrichting van de informatievoorziening." Het vormde een referentieoverzicht van de samenhang tussen bedrijfsactiviteiten en informatieobjecten. De ZiRA verving de RDZ in 2018.

---

## 14. ZaRA (ZORGAANBIEDER REFERENTIE ARCHITECTUUR) - OPVOLGER

**Bron:** https://sites.google.com/site/zirawiki/zorgaanbieder-referentie-architectuur/zara
**Bron:** Congrespresentatie "Naar een zorgbrede referentiearchitectuur" (19 juni 2025)

### Aanleiding
- Referentiearchitectuur domeinenmodel Care (RDC) is verouderd
- ZiRA is up-to-date, maar alleen op Ziekenhuizen gericht
- "Zijn de verschillen tussen zorgaanbieders echt zo groot als ze soms lijken?"
- In 2024 ontstond het idee om ZiRA, RDC en RDGGZ samen te voegen naar 1 model

### Historie
- 2012-2017: RDZ (Ziekenhuizen), RDC (Care), RDGGZ (GGZ) apart
- 2018-2024: ZiRA (doorontwikkeling van RDZ)
- 2025 e.v.: ZaRA-kern met modules voor Ziekenhuizen, Care en GGZ

### Aanpak
- Iteratief
- Meerdere branches en Nictiz samen
- Onderdelen: Domeinenmodel, Bedrijfsfunctiemodel, Processenmodel, Informatieobjectenmodel, Applicatiefunctiemodel

### Uitdagingen
- Samenvoegen van verschillende branches: cure en care hebben andere dynamiek
- Terminologieverschillen: patiënt, cliënt, burger...?
- Zorgleefplan vs. behandelplan vs. plan...?
- Onderwijs: studenten, medewerkers, bewoners?
- Herkenbaar blijven
- Eenvoudig en voldoende detail
- Modulariteit voor diverse branches
- Domeinenmodel en bedrijfsfunctiemodel samenvoegen
- Governance inrichten

### Conceptversie ZaRA Capabilitymodel (slide 12)

**STURING EN VERANTWOORDING:**
- Strategie en governance
- Marketing
- Innovatie
- Planning en control
- Kwaliteitsmanagement
- Performance management
- Verantwoording

**SAMENWERKING:**
- Verwijzing ontvangen
- Gegevens uitwisselen
- Multidisciplinair samenwerken
- Verwijzen en Overdragen

**ONDERZOEK:**
- Onderzoeks ontwikkeling
- Onderzoeks voorbereiding
- Onderzoeks uitvoering
- Onderzoeks publicatie
- Valorisatie onderzoek
- Onderzoeks ondersteuning

**ZORG - Planvorming:**
- Instroom beheren
- Anamnese afnemen
- Vaststellen zorgbehoefte
- Eigen onderzoek uitvoeren
- Diagnosticeren
- Adviseren
- Opstellen plan
- Uit stroom beheren

**ZORG - Aanvullend onderzoek:**
- Laboratorium onderzoek uitvoeren
- Beeldvormend onderzoek uitvoeren
- Functie onderzoek uitvoeren
- Psychologisch onderzoek uitvoeren
- Overig onderzoek uitvoeren

**ZORG - Cliëntondersteuning:**
- Begeleiden
- Dagbesteding bieden
- Welzijn
- Verblijf bieden
- Wonen aanbieden
- Leefomgeving beheren
- Bewindvoeren
- Vervoeren

**ZORG - Eigen regie:**
- Regie faciliteren
- Participatie faciliteren

**ZORG - Behandeling:**
- Therapie geven
- Medicamenteus behandelen
- Opereren
- Revalideren
- Re-integreren
- Overige behandelingen

**ZORG - Verpleging en verzorging:**
- Verplegen
- Verzorgen

**ZORGPROCESONDERSTEUNING:**
- Zorgrelatie beheren
- Resources plannen
- Zorglogistiek
- Zorgplanning
- Financiële afhandeling
- Med.technologie en domotica beheren

**LEREN EN ONTWIKKELING:**
- Ontwikkeling onderwijs
- Uitvoering onderwijs
- Toetsing onderwijs
- Ondersteuning onderwijs

**BEDRIJFSONDERSTEUNING:**
- Beheer gebouwen en inventaris
- Inkoop en voorraadbeheer
- Juridische ondersteuning
- Communicatie en voorlichting
- Zorgcontractering
- Personeel en organisatie
- Financiële administratie
- ICT
- Kwaliteit, veiligheid, Arbo en Milieu

### ZiRA en RDC samengevoegd (slide 8)
De presentatie toont het ZiRA bedrijfsfunctiemodel (links) naast het RDC model (rechts), met de samenvoeging tot het ZaRA capabilitymodel.

---

## 15. BESCHIKBARE DOWNLOADS

**Bron:** https://sites.google.com/site/zirawiki/file-cabinet

### Nederlands (v1.4)
1. **ZiRA v1.4-NL.eap** - Sparx Enterprise Architect bestand
2. **ZiRA v1.4-NL.archimate** - Archi bestand
3. **ZiRA v1.4-NL.xml** - ArchiMate Model Exchange bestand
4. **ZiRA v1.4-NL.xlsx** - Excel spreadsheet (principes, diensten, bedrijfsfuncties, processen, informatiedomeinen, applicatiefuncties, matrices)
5. **ZiRA v1.4-NL.pptx** - PowerPoint presentatie

### Engels (v1.4)
1. **ZiRA v1.4-EN.eap** - Sparx Enterprise Architect
2. **ZiRA v1.4-EN.archimate** - Archi
3. **ZiRA v1.4-EN.xml** - ArchiMate Model Exchange
4. **ZiRA v1.4-EN.xlsx** - Excel
5. **ZiRA v1.4-EN.pptx** - PowerPoint

### Overige documenten
- ZiRA Architectuurprincipes publicatie.pdf
- ZiRA v1.3 architectuurprincipes en implicaties.xlsx
- ZiRA Canvas template.pptx
- ZiRA poster 2018
- The Dutch ZiRA - complete translation (The Open Group, okt 2023)
- Governance en beheer ZiRA
- ZiRA contribution "Digital maturity in hospitals" manuscript

### GitHub Repository
**Bron:** https://github.com/Nictiz/ZiRA

Bevat:
- `artifacts/` - XLSX, MAX, XML, ArchMate bestanden
- `docs/` - Generated HTML uit Enterprise Architect
- `ea-scripts/` - Enterprise Architect scripts
- `xslt/` - Transformatiescripts (zira2xls, ziraim2gv voor GraphViz)
- Tooling: Saxon HE 11.5 voor XSLT, LibreOffice voor spreadsheets

---

## 16. RELEASE HISTORIE

**Bron:** https://sites.google.com/site/zirawiki/zira-beheer/zira-releaseinfo

| Versie | Datum | Wijzigingen |
|---|---|---|
| 1.0 | 14 juni 2018 | Eerste oplevering, vervanging RDZ |
| 1.1 | 5 sept 2023 | Inhoudelijk aangescherpt, nieuwe Nictiz huisstijl |
| 1.2 | 12 okt 2023 | Volledige vertaling met The Open Group |
| 1.3 NL | 8 nov 2023 | Nieuwe architectuurprincipes, aangepast metamodel |
| 1.4 | 22 aug 2024 | MDO proces toegevoegd (NL+EN), principes in EN |

---

## 17. MAPPING NAAR EA-LAGEN (Enterprise Architecture Layers)

De ZiRA modellen mappen als volgt op standaard enterprise architectuurlagen:

| EA-Laag | ZiRA Model | ArchiMate Laag |
|---|---|---|
| **Strategy** | Businessmodel (BMC), Principes | Motivation |
| **Business** | Bedrijfsfunctiemodel, Dienstenmodel | Business Layer |
| **Process** | Procesmodel (8 bedrijfsprocessen) | Business Layer (Process) |
| **Information** | Informatiemodel, Informatiedomeinen | Application Layer (Data) |
| **Application** | Applicatiefunctiemodel | Application Layer |
| **Technology** | (niet expliciet uitgewerkt in ZiRA) | Technology Layer |

De ZiRA volgt het **Nictiz vijflagen-interoperabiliteitsmodel**:
1. Organisatie & beleid
2. Zorgproces
3. Informatie
4. Applicatie
5. IT-infrastructuur

---

## 18. KERNCONCEPTEN SAMENVATTING

| Concept | Definitie |
|---|---|
| **Bedrijfsfunctie** | Intern gedragselement gevormd door bedrijfsactiviteiten met samenhang in kennis, vaardigheid en middelen |
| **Dienst** | Afgebakende prestatie van een persoon of organisatieonderdeel |
| **Bedrijfsproces** | Keten van activiteiten nodig om tot een bepaald resultaat te komen |
| **Werkproces** | Onderdeel van een bedrijfsproces |
| **Bedrijfsactiviteit** | Kleinste eenheid van werk |
| **Informatieobject** | Eenheid van informatie relevant vanuit bedrijfsperspectief |
| **Informatiedomein** | Cluster van sterk verbonden bedrijfsactiviteiten en informatieobjecten |
| **Applicatiefunctie** | Samenhangende geautomatiseerde functionaliteit die bedrijfsactiviteiten ondersteunt |
| **Bedrijfsdomein** | Hoofdindeling: Zorg, Onderzoek, Onderwijs, Sturing, Bedrijfsondersteuning |

---

## 19. BELANGRIJKE URLS

| Resource | URL |
|---|---|
| ZiRA Wiki (hoofdsite) | https://sites.google.com/site/zirawiki/home |
| ZiRA op Nictiz | https://nictiz.nl/standaarden/referentiedomeinenmodellen/zira/ |
| ArchiMate HTML (NL) | https://nictiz.github.io/ZiRA/1.4/nl |
| ArchiMate HTML (EN) | https://nictiz.github.io/ZiRA/1.4/en |
| GitHub Repository | https://github.com/Nictiz/ZiRA |
| ZiRA Praktijkboek | https://nictiz.nl/publicaties/praktijkboek-zira/ |
| ZaRA (opvolger) | https://sites.google.com/site/zirawiki/zorgaanbieder-referentie-architectuur/zara |
| ZaRA contact | zara@nictiz.nl |
| ZiRA beheer | beheerzira@nictiz.nl |

---

## 20. CONTACTEN

### ZaRA Congrespresentatie (19 juni 2025)
- **Mikis van Dijk** - Enterprise architect, Nictiz - mikis.vandijk@nictiz.nl
- **Rik Nijman** - Domein architect, 's Heeren Loo - rik.nijman@sheerenloo.nl

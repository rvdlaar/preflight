# Security Assessment & STRIDE Threat Model / Beveiligingsbeoordeling & STRIDE Dreigingsmodel

> **Doel / Purpose:** Structured security assessment for a proposed system or integration. STRIDE-based threat modeling, authentication/authorization review, encryption strategy, supply chain analysis, NEN 7510 control mapping, and penetration test scoping. Feeds into the PSA and is reviewed by the CISO / security architect.

---

## Metadata / Metadata

| Veld / Field | Waarde / Value |
|---|---|
| **Voorstel / Proposal** | `{{proposal_name}}` |
| **PSA-referentie / PSA reference** | `{{psa_id}}` |
| **Datum / Date** | `{{date}}` |
| **Security architect** | `{{architect_name}}` |
| **Versie / Version** | `{{version}}` |
| **BIV-classificatie / CIA classification** | B:`{{1-4}}` I:`{{1-4}}` V:`{{1-4}}` |
| **Status** | ☐ Concept / Draft  ☐ Review  ☐ Goedgekeurd / Approved |

---

## 1. Systeemoverzicht / System Overview

`{{Brief description of the system under assessment: what it does, where it runs, what data it processes, who uses it.}}`

**Scope van beoordeling / Assessment scope:**
- ☐ Nieuwe applicatie / New application
- ☐ Nieuwe integratie / New integration
- ☐ Wijziging bestaand systeem / Change to existing system
- ☐ SaaS/cloud dienst / SaaS/cloud service
- ☐ On-premises

**Dataclassificatie / Data classification:**
- ☐ Bijzondere persoonsgegevens / Special category personal data (medical)
- ☐ Persoonsgegevens / Personal data
- ☐ Vertrouwelijk / Confidential (non-personal)
- ☐ Intern / Internal
- ☐ Openbaar / Public

---

## 2. STRIDE Dreigingsmodel / STRIDE Threat Model

> For each STRIDE category, identify threats per system component. Pre-filled structure — complete per component.

### 2.1 Spoofing — Identiteitsvervalsing

> Can an attacker pretend to be someone or something they are not?

| Component | Bevinding / Finding | Risico / Risk (H/M/L) | Mitigatie / Mitigation | Status |
|---|---|---|---|---|
| Gebruikersauthenticatie / User authentication | `{{e.g., "Single-factor authentication allows credential theft"}}` | `{{H/M/L}}` | `{{e.g., "Enforce MFA via Entra ID"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Service-to-service communicatie | `{{e.g., "No mutual TLS between app and Cloverleaf"}}` | `{{H/M/L}}` | `{{e.g., "Implement mTLS or API key rotation"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| API endpoints | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| `{{component}}` | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |

### 2.2 Tampering — Manipulatie

> Can an attacker modify data in transit or at rest?

| Component | Bevinding / Finding | Risico / Risk (H/M/L) | Mitigatie / Mitigation | Status |
|---|---|---|---|---|
| Berichten in transit / Messages in transit | `{{e.g., "HL7 messages over MLLP are unencrypted on internal network"}}` | `{{H/M/L}}` | `{{e.g., "Wrap MLLP in TLS tunnel"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Database records | `{{e.g., "No audit trail on record modification"}}` | `{{H/M/L}}` | `{{e.g., "Enable row-level audit logging"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Configuratiebestanden / Config files | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| `{{component}}` | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |

### 2.3 Repudiation — Ontkenbaarheid

> Can an attacker deny having performed an action?

| Component | Bevinding / Finding | Risico / Risk (H/M/L) | Mitigatie / Mitigation | Status |
|---|---|---|---|---|
| Gebruikersacties / User actions | `{{e.g., "No logging of data access events"}}` | `{{H/M/L}}` | `{{e.g., "Implement SIEM-integrated audit log"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Systeemacties / System actions | `{{e.g., "Automated data exports not logged"}}` | `{{H/M/L}}` | `{{e.g., "Log all export events with timestamp and actor"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Beheeracties / Admin actions | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| `{{component}}` | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |

### 2.4 Information Disclosure — Informatielekken

> Can an attacker gain access to data they should not see?

| Component | Bevinding / Finding | Risico / Risk (H/M/L) | Mitigatie / Mitigation | Status |
|---|---|---|---|---|
| API responses | `{{e.g., "Error messages expose stack traces and DB schema"}}` | `{{H/M/L}}` | `{{e.g., "Generic error messages in production, detailed in logs only"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Logbestanden / Log files | `{{e.g., "Patient BSN logged in plain text"}}` | `{{H/M/L}}` | `{{e.g., "Mask PII in logs, tokenize BSN"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Backups | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Netwerk / Network | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| `{{component}}` | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |

### 2.5 Denial of Service — Dienstweigering

> Can an attacker make the system unavailable?

| Component | Bevinding / Finding | Risico / Risk (H/M/L) | Mitigatie / Mitigation | Status |
|---|---|---|---|---|
| API endpoints | `{{e.g., "No rate limiting on public-facing API"}}` | `{{H/M/L}}` | `{{e.g., "Implement rate limiting, WAF rules"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Berichtenqueue / Message queue | `{{e.g., "Queue overflow could block Cloverleaf thread"}}` | `{{H/M/L}}` | `{{e.g., "Queue depth monitoring + overflow to DLQ"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Database | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| `{{component}}` | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |

### 2.6 Elevation of Privilege — Privilegeverhoging

> Can an attacker gain higher access than intended?

| Component | Bevinding / Finding | Risico / Risk (H/M/L) | Mitigatie / Mitigation | Status |
|---|---|---|---|---|
| Rolmodel / Role model | `{{e.g., "Single admin role — no separation of duties"}}` | `{{H/M/L}}` | `{{e.g., "Implement RBAC with least-privilege roles"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| Service accounts | `{{e.g., "Integration service account has DBA privileges"}}` | `{{H/M/L}}` | `{{e.g., "Restrict to minimum required permissions"}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| API autorisatie / API authorization | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |
| `{{component}}` | `{{finding}}` | `{{H/M/L}}` | `{{mitigation}}` | ☐ Open ☐ Mitigated ☐ Accepted |

### 2.7 STRIDE Samenvatting / STRIDE Summary

| Categorie / Category | Aantal bevindingen / Finding count | Hoog / High | Midden / Medium | Laag / Low | Open |
|---|---|---|---|---|---|
| Spoofing | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` |
| Tampering | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` |
| Repudiation | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` |
| Information Disclosure | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` |
| Denial of Service | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` |
| Elevation of Privilege | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` | `{{count}}` |
| **Totaal / Total** | **`{{count}}`** | **`{{count}}`** | **`{{count}}`** | **`{{count}}`** | **`{{count}}`** |

---

## 3. Authenticatie & Autorisatie / Authentication & Authorization Design Review

### 3.1 Authenticatie / Authentication

| Aspect | Ontwerp / Design | Beoordeling / Assessment |
|---|---|---|
| **Methode / Method** | `{{e.g., OIDC via Microsoft Entra ID}}` | `{{Adequate / Improvement needed — explain}}` |
| **MFA** | `{{e.g., Entra ID Conditional Access — MFA required}}` | `{{Adequate / Not implemented — risk}}` |
| **Sessieduur / Session duration** | `{{e.g., 8 hours, re-auth for sensitive operations}}` | `{{Adequate / Too long — explain}}` |
| **Wachtwoordbeleid / Password policy** | `{{e.g., Entra ID policy, 14 char minimum}}` | `{{Adequate / Improvement needed}}` |
| **Service accounts** | `{{e.g., Managed Identity / certificate-based}}` | `{{Adequate / Shared credentials — risk}}` |
| **Break-glass procedure** | `{{e.g., Emergency access accounts in safe}}` | `{{Documented / Missing}}` |

### 3.2 Autorisatie / Authorization

| Aspect | Ontwerp / Design | Beoordeling / Assessment |
|---|---|---|
| **Model** | `{{RBAC / ABAC / hybrid}}` | `{{Adequate / Over-permissive — explain}}` |
| **Rollen gedefinieerd / Roles defined** | `{{List roles and high-level permissions}}` | `{{Follows least privilege / Needs refinement}}` |
| **Functiescheiding / Separation of duties** | `{{e.g., Admin cannot approve own changes}}` | `{{Adequate / Missing controls}}` |
| **Consent / Patient consent** | `{{How is patient consent enforced in data access?}}` | `{{Adequate / Not implemented}}` |
| **Data-level autorisatie / Data-level auth** | `{{e.g., Row-level security, department scoping}}` | `{{Adequate / Missing}}` |

---

## 4. Versleutelingsstrategie / Encryption Strategy

### 4.1 Data at Rest

| Component | Versleuteling / Encryption | Sleutelbeheer / Key management | Beoordeling / Assessment |
|---|---|---|---|
| Database | `{{e.g., TDE with AES-256}}` | `{{e.g., Azure Key Vault, HSM-backed}}` | `{{Adequate / Missing / Weak}}` |
| Bestandsopslag / File storage | `{{e.g., BitLocker / LUKS / cloud-native}}` | `{{key management}}` | `{{Adequate / Missing / Weak}}` |
| Backups | `{{e.g., Encrypted with separate key}}` | `{{key management}}` | `{{Adequate / Missing / Weak}}` |
| Logs | `{{e.g., PII masked, logs encrypted}}` | `{{key management}}` | `{{Adequate / Missing / Weak}}` |

### 4.2 Data in Transit

| Verbinding / Connection | Protocol | TLS versie | Certificaatbeheer / Cert management | Beoordeling / Assessment |
|---|---|---|---|---|
| Gebruiker naar applicatie / User to app | `{{HTTPS}}` | `{{TLS 1.2+ / 1.3}}` | `{{e.g., Let's Encrypt auto-renewal}}` | `{{Adequate / Weak ciphers}}` |
| App naar database / App to DB | `{{e.g., TLS}}` | `{{TLS 1.2+}}` | `{{internal CA}}` | `{{Adequate / Missing}}` |
| App naar Cloverleaf | `{{e.g., MLLP over TLS}}` | `{{version}}` | `{{cert management}}` | `{{Adequate / Missing}}` |
| App naar extern / App to external | `{{HTTPS / VPN / sFTP over SSH}}` | `{{version}}` | `{{cert management}}` | `{{Adequate / Missing}}` |

### 4.3 Data in Use

| Aspect | Ontwerp / Design | Beoordeling / Assessment |
|---|---|---|
| Geheugenbeveiliging / Memory protection | `{{e.g., No sensitive data cached in plain text}}` | `{{Adequate / Risk identified}}` |
| Schermbeveiliging / Screen masking | `{{e.g., BSN masked after first display}}` | `{{Adequate / Not implemented}}` |
| Clipboard bescherming / Clipboard protection | `{{e.g., Copy disabled for sensitive fields}}` | `{{Adequate / Not implemented}}` |

---

## 5. Supply Chain & SBOM

### 5.1 Software Bill of Materials

| Aspect | Detail |
|---|---|
| **SBOM beschikbaar / SBOM available** | `{{Yes / No / Requested from vendor}}` |
| **Formaat / Format** | `{{CycloneDX / SPDX / proprietary}}` |
| **Automatisch bijgewerkt / Auto-updated** | `{{Yes — via CI/CD pipeline / No — manual}}` |
| **Vulnerability scanning** | `{{e.g., Dependabot, Snyk, Trivy — describe integration}}` |

### 5.2 Supply Chain Risico's / Supply Chain Risks

| Risico / Risk | Beoordeling / Assessment | Mitigatie / Mitigation |
|---|---|---|
| Open source afhankelijkheden / Open source dependencies | `{{Count of direct/transitive deps, known vulnerabilities}}` | `{{e.g., Automated scanning, update policy}}` |
| Leverancierstoegang / Vendor access | `{{Does vendor have remote access? To what?}}` | `{{e.g., VPN with MFA, session recording, time-limited}}` |
| Leveranciers subverwerkers / Vendor sub-processors | `{{Does vendor use sub-processors for data processing?}}` | `{{e.g., DPA covers sub-processors, exit clause}}` |
| Build pipeline integriteit / Build pipeline integrity | `{{Signed builds? Reproducible? Verified artifacts?}}` | `{{e.g., Signed containers, SLSA level}}` |
| End-of-life / End-of-support | `{{Known EOL dates for components}}` | `{{Migration plan}}` |

### 5.3 Leveranciersbeoordeling / Vendor Assessment

| Aspect | Detail |
|---|---|
| **ISO 27001 / SOC 2** | `{{Certified? Scope covers this product?}}` |
| **NEN 7510 / NEN 7512 / NEN 7513** | `{{Certified? Self-declared?}}` |
| **Verwerkersovereenkomst / DPA** | `{{In place? Covers BSN, medical data?}}` |
| **DPIA** | `{{Required? Completed?}}` |
| **Exitstrategie / Exit strategy** | `{{Data portability, format, timeline, cost}}` |

---

## 6. NEN 7510 Control Mapping

> Map relevant NEN 7510 controls to the proposed system. Pre-filled with commonly applicable controls.

| NEN 7510 Control | Omschrijving / Description | Implementatiestatus / Implementation status | Toelichting / Notes |
|---|---|---|---|
| **5.2** | Informatiebeveiligingsbeleid / Information security policy | `{{Compliant / Partially / Not compliant / N/A}}` | `{{notes}}` |
| **6.1.1** | Rollen en verantwoordelijkheden / Roles and responsibilities | `{{status}}` | `{{notes}}` |
| **8.1** | Classificatie van informatie / Information classification | `{{status}}` | `{{e.g., BIV classification completed}}` |
| **9.1.1** | Toegangsbeleid / Access control policy | `{{status}}` | `{{notes}}` |
| **9.2.3** | Beheer van speciale toegangsrechten / Privileged access management | `{{status}}` | `{{notes}}` |
| **9.4.1** | Beperking van toegang tot informatie / Information access restriction | `{{status}}` | `{{notes}}` |
| **10.1.1** | Beleid inzake cryptografie / Cryptographic controls policy | `{{status}}` | `{{notes}}` |
| **12.4.1** | Gebeurtenissen registreren / Event logging | `{{status}}` | `{{e.g., Audit trail implemented per NEN 7513}}` |
| **12.4.3** | Logbestanden van beheerders / Administrator logs | `{{status}}` | `{{notes}}` |
| **13.1.1** | Beheersmaatregelen voor netwerken / Network controls | `{{status}}` | `{{notes}}` |
| **13.2.1** | Beleid en procedures voor informatietransport / Information transfer | `{{status}}` | `{{e.g., Encryption in transit}}` |
| **14.1.1** | Analyse van informatiebeveiligingseisen / Security requirements analysis | `{{status}}` | `{{This document}}` |
| **14.2.1** | Beleid voor beveiligd ontwikkelen / Secure development policy | `{{status}}` | `{{notes}}` |
| **15.1.1** | Informatiebeveiligingsbeleid leveranciersrelaties / Supplier security policy | `{{status}}` | `{{notes}}` |
| **16.1.1** | Verantwoordelijkheden en procedures / Incident management | `{{status}}` | `{{notes}}` |
| **18.1.3** | Bescherming van registraties / Protection of records | `{{status}}` | `{{e.g., Retention policy, WGBO compliance}}` |
| **18.1.4** | Privacy en bescherming persoonsgegevens / Privacy and PII protection | `{{status}}` | `{{e.g., AVG/GDPR compliance, DPIA}}` |

**Aanvullende controls / Additional controls:**
`{{List any additional NEN 7510 controls applicable to this specific system that are not in the standard set above.}}`

---

## 7. Penetratietest Scope / Penetration Test Scope

### 7.1 Testscope / Test Scope

| Aspect | Detail |
|---|---|
| **Type test** | `{{Web app pentest / API pentest / Network pentest / Social engineering / combination}}` |
| **Testmethodiek / Methodology** | `{{e.g., OWASP Testing Guide v4, PTES, custom}}` |
| **Perspectief / Perspective** | `{{Black box / Grey box / White box}}` |
| **Omgeving / Environment** | `{{Production / Pre-production / Dedicated test}}` |
| **Tijdlijn / Timeline** | `{{Proposed test window, duration}}` |

### 7.2 In Scope

| Component | URL / IP / Endpoint | Beschrijving / Description |
|---|---|---|
| Web applicatie / Web application | `{{url}}` | `{{description}}` |
| API endpoints | `{{base_url/api}}` | `{{description}}` |
| Integratie-interfaces / Integration interfaces | `{{endpoint}}` | `{{e.g., Cloverleaf-facing interface}}` |
| Authenticatie / Authentication | `{{endpoint}}` | `{{e.g., OIDC flow, token endpoints}}` |
| `{{component}}` | `{{endpoint}}` | `{{description}}` |

### 7.3 Buiten Scope / Out of Scope

| Component | Reden / Reason |
|---|---|
| `{{e.g., Cloverleaf engine itself}}` | `{{Shared infrastructure — separate assessment}}` |
| `{{e.g., Microsoft Entra ID}}` | `{{Third-party managed service}}` |
| `{{component}}` | `{{reason}}` |

### 7.4 Voorwaarden / Prerequisites

- ☐ Testaccounts aangemaakt / Test accounts created (one per role)
- ☐ Testdata beschikbaar / Test data available (no production patient data)
- ☐ Toestemming / Authorization letter signed by `{{responsible_manager}}`
- ☐ Noodcontact / Emergency contact during test: `{{name, phone}}`
- ☐ Terugdraaiprocedure / Rollback procedure documented
- ☐ Monitoring team geïnformeerd / Monitoring team informed (prevent false positive incident)

### 7.5 Rapportage-eisen / Reporting Requirements

| Aspect | Eis / Requirement |
|---|---|
| **Classificatiemodel / Rating model** | `{{CVSS v3.1 / DREAD / custom}}` |
| **Rapportageformaat / Report format** | `{{e.g., Executive summary + technical detail + remediation guidance}}` |
| **Hertest / Retest** | `{{Included? Timeline for retest after remediation?}}` |
| **Vertrouwelijkheid / Confidentiality** | `{{Report distribution limited to: security team, CISO, project lead}}` |

---

## 8. Beveiligingsadvies / Security Recommendation

**Algeheel oordeel / Overall assessment:**

☐ **Goedgekeurd** / Approved — Beveiligingsrisico's acceptabel
☐ **Goedgekeurd met voorwaarden** / Approved with conditions — Zie onderstaand
☐ **Niet goedgekeurd** / Not approved — Onacceptabele risico's, zie onderstaand
☐ **Meer informatie nodig** / More information needed

**Voorwaarden voor goedkeuring / Conditions for approval:**
1. `{{condition_1}}`
2. `{{condition_2}}`
3. `{{condition_3}}`

**Openstaande acties / Outstanding actions:**

| Actie / Action | Eigenaar / Owner | Deadline | Prioriteit / Priority |
|---|---|---|---|
| `{{action_1}}` | `{{owner}}` | `{{date}}` | `{{H/M/L}}` |
| `{{action_2}}` | `{{owner}}` | `{{date}}` | `{{H/M/L}}` |

---

*Dit document is gegenereerd door Preflight en dient te worden gereviewd door de security architect en CISO.*
*This document was generated by Preflight and must be reviewed by the security architect and CISO.*

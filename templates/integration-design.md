# Integration Design / Integratieontwerp

> **Doel / Purpose:** Full integration specification for a proposed system. Covers data flows, message specifications, error handling, volumetrics, SLAs, monitoring, and cascade impact. This document feeds into the PSA and is reviewed by the integration architect and Cloverleaf team.

---

## Metadata / Metadata

| Veld / Field | Waarde / Value |
|---|---|
| **Voorstel / Proposal** | `{{proposal_name}}` |
| **PSA-referentie / PSA reference** | `{{psa_id}}` |
| **Datum / Date** | `{{date}}` |
| **Integratie-architect / Integration architect** | `{{architect_name}}` |
| **Versie / Version** | `{{version}}` |
| **Status** | ☐ Concept / Draft  ☐ Review  ☐ Goedgekeurd / Approved |

---

## 1. Overzicht / Overview

`{{2-3 sentences describing the integration scope. What systems are being connected, why, and what clinical or business value this integration delivers.}}`

**Integratiestijl / Integration style:**
☐ Point-to-point
☐ Middleware-brokered (Cloverleaf)
☐ API-based (REST/GraphQL)
☐ File-based (sFTP/share)
☐ Event-driven (message bus)
☐ Hybrid — `{{describe}}`

---

## 2. Datastroomontwerp / Data Flow Design

### 2.1 Stroomoverzicht / Flow Overview

> Describe each integration flow. For each flow, specify source, target, middleware role, transformation, and trigger.

#### Flow 1: `{{flow_name}}`

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│              │      │              │      │              │
│  {{source}}  │─────▶│  Cloverleaf  │─────▶│  {{target}}  │
│              │      │              │      │              │
└──────────────┘      └──────────────┘      └──────────────┘
     {{protocol_in}}       {{transform}}       {{protocol_out}}
```

| Aspect | Detail |
|---|---|
| **Bronsysteem / Source system** | `{{system_name, version}}` |
| **Doelsysteem / Target system** | `{{system_name, version}}` |
| **Middleware** | `{{Cloverleaf / direct / other}}` |
| **Richting / Direction** | `{{Unidirectional / Bidirectional}}` |
| **Trigger** | `{{Event-driven (e.g., ADT event) / Scheduled (e.g., every 5 min) / On-demand}}` |
| **Protocol inkomend / Inbound protocol** | `{{MLLP / HTTPS / sFTP / DICOM / other}}` |
| **Protocol uitgaand / Outbound protocol** | `{{MLLP / HTTPS / sFTP / DICOM / other}}` |
| **Transformatie / Transformation** | `{{Describe: field mapping, code translation, segment rewriting, enrichment}}` |
| **Filtering** | `{{Which messages are routed vs. dropped? e.g., only ADT^A01, A02, A08}}` |

#### Flow 2: `{{flow_name}}`

`{{Repeat structure above for each additional flow}}`

### 2.2 Cloverleaf Routeconfiguratie / Cloverleaf Route Configuration

| Route | Bron thread / Source thread | Doel thread / Dest thread | TPS filter | Xlate | Notes |
|---|---|---|---|---|---|
| `{{route_1}}` | `{{source_thread}}` | `{{dest_thread}}` | `{{TPS details}}` | `{{Xlate name}}` | `{{notes}}` |
| `{{route_2}}` | `{{source_thread}}` | `{{dest_thread}}` | `{{TPS details}}` | `{{Xlate name}}` | `{{notes}}` |

---

## 3. Berichtspecificaties / Message Specifications

### 3.1 HL7v2 Berichten / HL7v2 Messages

> Complete this section if the integration uses HL7v2.

#### Message Type: `{{e.g., ADT^A01}}`

**Trigger:** `{{When is this message sent?}}`
**HL7 Version:** `{{2.3 / 2.3.1 / 2.5.1}}`

| Segment | Veld / Field | Positie / Position | Beschrijving / Description | Bron mapping / Source mapping | Verplicht / Required |
|---|---|---|---|---|---|
| MSH | Sending Application | MSH-3 | `{{value or mapping}}` | `{{source field}}` | R |
| MSH | Sending Facility | MSH-4 | `{{value or mapping}}` | `{{source field}}` | R |
| PID | Patient ID | PID-3 | `{{BSN / MRN / other}}` | `{{source field}}` | R |
| PID | Patient Name | PID-5 | `{{format}}` | `{{source field}}` | R |
| PV1 | Patient Class | PV1-2 | `{{I/O/E/P}}` | `{{source field}}` | R |
| `{{segment}}` | `{{field_name}}` | `{{position}}` | `{{description}}` | `{{source_mapping}}` | `{{R/O/C}}` |

**Z-segmenten / Z-segments (custom):**

| Segment | Beschrijving / Description | Velden / Fields |
|---|---|---|
| `{{e.g., ZPI}}` | `{{purpose}}` | `{{field list}}` |

#### Message Type: `{{e.g., ORM^O01}}`

`{{Repeat structure above}}`

### 3.2 FHIR Resources

> Complete this section if the integration uses FHIR.

**FHIR Version:** `{{R4 / R4B / R5}}`
**Profiles gebruikt / Profiles used:** `{{e.g., nl-core-Patient, nl-core-Organization}}`

| Resource | Operatie / Operation | Endpoint | Beschrijving / Description |
|---|---|---|---|
| `{{e.g., Patient}}` | `{{GET / POST / PUT / PATCH}}` | `{{/Patient, /Patient/{id}}}` | `{{description}}` |
| `{{e.g., Observation}}` | `{{POST}}` | `{{/Observation}}` | `{{description}}` |

**Veldmapping / Field Mapping:**

| FHIR Path | Bron / Source | Transformatie / Transformation | Opmerkingen / Notes |
|---|---|---|---|
| `Patient.identifier[BSN]` | `{{source_field}}` | `{{none / format conversion}}` | `{{notes}}` |
| `{{fhir_path}}` | `{{source_field}}` | `{{transformation}}` | `{{notes}}` |

**Terminologie / Terminology:**

| CodeSystem | Gebruik / Usage | Bron / Source |
|---|---|---|
| `{{e.g., SNOMED CT NL}}` | `{{where used}}` | `{{mapping source}}` |
| `{{e.g., LOINC}}` | `{{where used}}` | `{{mapping source}}` |

### 3.3 Overige berichten / Other Message Formats

> For file-based, DICOM, or proprietary formats.

| Formaat / Format | Beschrijving / Description | Specificatie / Specification |
|---|---|---|
| `{{e.g., CSV}}` | `{{purpose}}` | `{{field layout, delimiter, encoding}}` |
| `{{e.g., DICOM}}` | `{{purpose}}` | `{{modality worklist, storage, query/retrieve — SOP classes}}` |

---

## 4. Foutafhandeling / Error Handling

### 4.1 Foutstrategie per flow / Error Strategy per Flow

| Flow | Fouttype / Error type | Strategie / Strategy | Details |
|---|---|---|---|
| `{{flow_1}}` | Connectiviteit / Connectivity | Retry | `{{retry count, interval, backoff strategy — e.g., 3 retries, exponential 30s/60s/120s}}` |
| `{{flow_1}}` | Transformatie / Transformation | Dead letter queue | `{{DLQ location, retention period, review process}}` |
| `{{flow_1}}` | Validatie / Validation (NAK) | Alert + manual review | `{{who is alerted, response SLA}}` |
| `{{flow_1}}` | Timeout | Retry + alert | `{{timeout threshold, escalation}}` |
| `{{flow_2}}` | `{{error_type}}` | `{{strategy}}` | `{{details}}` |

### 4.2 Dead Letter Queue

| Aspect | Detail |
|---|---|
| **Locatie / Location** | `{{Cloverleaf error database / dedicated queue / file system}}` |
| **Retentie / Retention** | `{{days/weeks}}` |
| **Review proces / Review process** | `{{Who reviews? How often? SLA for resolution?}}` |
| **Replay mogelijk / Replay capability** | `{{Yes/No — describe mechanism}}` |
| **Alerting** | `{{Threshold for alert — e.g., >5 messages in DLQ triggers page}}` |

### 4.3 Escalatiematrix / Escalation Matrix

| Ernst / Severity | Voorbeeld / Example | Eerste lijn / First responder | Escalatie / Escalation | SLA |
|---|---|---|---|---|
| Kritiek / Critical | All messages failing, patient safety risk | `{{team/person}}` | `{{escalation path}}` | `{{response time}}` |
| Hoog / High | Single flow down, workaround available | `{{team/person}}` | `{{escalation path}}` | `{{response time}}` |
| Midden / Medium | Intermittent errors, no data loss | `{{team/person}}` | `{{escalation path}}` | `{{response time}}` |
| Laag / Low | Cosmetic, non-blocking | `{{team/person}}` | `{{escalation path}}` | `{{response time}}` |

---

## 5. Volumetrie / Volumetrics

| Flow | Berichten per uur / Msgs per hour | Berichten per dag / Msgs per day | Piekbelasting / Peak load | Piekmoment / Peak time | Berichtgrootte / Msg size (avg) |
|---|---|---|---|---|---|
| `{{flow_1}}` | `{{count}}` | `{{count}}` | `{{count/hr}}` | `{{e.g., Mon 08:00-10:00}}` | `{{KB}}` |
| `{{flow_2}}` | `{{count}}` | `{{count}}` | `{{count/hr}}` | `{{e.g., weekdays 07:00-09:00}}` | `{{KB}}` |

**Groeiprognose / Growth projection:**
`{{Expected volume growth over next 12-24 months. Factor in new departments, increased usage, etc.}}`

**Capaciteitsimpact / Capacity impact:**
`{{Does this exceed current Cloverleaf/middleware capacity? New threads needed? Hardware impact?}}`

---

## 6. SLA / Service Level Agreement

| Aspect | Eis / Requirement | Meetmethode / Measurement |
|---|---|---|
| **Beschikbaarheid / Availability** | `{{e.g., 99.5% during business hours, 99.0% overall}}` | `{{monitoring tool}}` |
| **Latentie / Latency** | `{{e.g., end-to-end < 5 seconds for 95th percentile}}` | `{{measurement point to point}}` |
| **Gegarandeerde aflevering / Guaranteed delivery** | `{{e.g., at-least-once / exactly-once / best-effort}}` | `{{mechanism — ACK/NAK, idempotency keys}}` |
| **Berichtvolgorde / Message ordering** | `{{e.g., per patient ordered / globally unordered}}` | `{{Cloverleaf sequencing config}}` |
| **Onderhoudsvenster / Maintenance window** | `{{e.g., Sunday 02:00-06:00}}` | `{{change calendar}}` |
| **RPO / Recovery Point Objective** | `{{e.g., 0 messages lost — persistent queue}}` | `{{queue persistence, backup}}` |
| **RTO / Recovery Time Objective** | `{{e.g., 30 minutes}}` | `{{failover procedure}}` |

---

## 7. Monitoring en Alerting / Monitoring and Alerting

### 7.1 Health Checks

| Component | Check | Frequentie / Frequency | Methode / Method | Alert bij falen / Alert on failure |
|---|---|---|---|---|
| Bron / Source system | Connectivity | `{{e.g., every 60s}}` | `{{TCP/ping/heartbeat msg}}` | `{{Yes — who}}` |
| Cloverleaf thread | Thread status | `{{e.g., every 30s}}` | `{{Cloverleaf monitoring}}` | `{{Yes — who}}` |
| Doel / Target system | Connectivity | `{{e.g., every 60s}}` | `{{TCP/ping/heartbeat msg}}` | `{{Yes — who}}` |
| End-to-end | Message flow | `{{e.g., every 5 min}}` | `{{synthetic test message}}` | `{{Yes — who}}` |

### 7.2 Operationele Dashboards / Operational Dashboards

| Dashboard | Tool | Inhoud / Content |
|---|---|---|
| Berichtverkeer / Message traffic | `{{e.g., Grafana / Cloverleaf console}}` | `{{Volume, latency, error rate per flow}}` |
| Foutenlog / Error log | `{{e.g., Splunk / ELK}}` | `{{Failed messages, DLQ depth, NAK reasons}}` |
| SLA rapportage / SLA reporting | `{{tool}}` | `{{Availability %, latency percentiles, delivery rate}}` |

### 7.3 Alerting

| Alert | Conditie / Condition | Kanaal / Channel | Ontvanger / Recipient |
|---|---|---|---|
| Flow down | `{{No messages received for > X minutes}}` | `{{SMS / Teams / PagerDuty}}` | `{{team/person}}` |
| DLQ threshold | `{{> X messages in dead letter queue}}` | `{{Teams / email}}` | `{{team/person}}` |
| Latency breach | `{{p95 latency > SLA threshold}}` | `{{Teams / dashboard}}` | `{{team/person}}` |
| Volume anomaly | `{{Volume < 50% or > 200% of baseline}}` | `{{Teams / email}}` | `{{team/person}}` |

---

## 8. Cascade Impact / Cascade-impact

> ArchiMate-based impact analysis: what downstream systems are affected if this integration fails or changes?

### 8.1 ArchiMate Relaties / ArchiMate Relationships

| Broncomponent / Source component | Relatietype / Relationship | Doelcomponent / Target component | Impact bij falen / Impact on failure |
|---|---|---|---|
| `{{application_component}}` | Serving | `{{application_component}}` | `{{describe clinical/business impact}}` |
| `{{application_component}}` | Flow | `{{application_component}}` | `{{describe data flow interruption}}` |
| `{{application_component}}` | Triggering | `{{application_component}}` | `{{describe process interruption}}` |
| `{{application_component}}` | Access | `{{data_object}}` | `{{describe data access loss}}` |

### 8.2 Afhankelijkheidsanalyse / Dependency Analysis

**Upstream afhankelijkheden / Upstream dependencies:**
`{{Systems that feed data INTO this integration. If they fail, this integration is affected.}}`

| Systeem / System | Afhankelijkheid / Dependency | Impact bij uitval / Impact if down |
|---|---|---|
| `{{system}}` | `{{what it provides}}` | `{{what breaks}}` |

**Downstream afhankelijkheden / Downstream dependencies:**
`{{Systems that CONSUME data from this integration. If this integration fails, they are affected.}}`

| Systeem / System | Afhankelijkheid / Dependency | Impact bij uitval / Impact if down |
|---|---|---|
| `{{system}}` | `{{what it consumes}}` | `{{what breaks}}` |

### 8.3 Scenario-analyse / Scenario Analysis

| Scenario | Getroffen flows / Affected flows | Klinische impact / Clinical impact | Mitigatie / Mitigation |
|---|---|---|---|
| Bron valt uit / Source failure | `{{flows}}` | `{{impact}}` | `{{mitigation}}` |
| Cloverleaf uitval / Cloverleaf outage | `{{flows}}` | `{{impact}}` | `{{mitigation}}` |
| Doel valt uit / Target failure | `{{flows}}` | `{{impact}}` | `{{mitigation}}` |
| Netwerk partitie / Network partition | `{{flows}}` | `{{impact}}` | `{{mitigation}}` |

---

## 9. Implementatieplan / Implementation Plan

| Fase / Phase | Activiteit / Activity | Verantwoordelijke / Owner | Doorlooptijd / Duration |
|---|---|---|---|
| Ontwerp / Design | Interface specificatie afstemmen / Align interface spec | `{{owner}}` | `{{duration}}` |
| Bouw / Build | Cloverleaf routes configureren / Configure Cloverleaf routes | `{{owner}}` | `{{duration}}` |
| Test | Functionele test / Functional test | `{{owner}}` | `{{duration}}` |
| Test | Volumetest / Volume test | `{{owner}}` | `{{duration}}` |
| Test | Failover test | `{{owner}}` | `{{duration}}` |
| Acceptatie / Acceptance | Klinische acceptatie / Clinical acceptance | `{{owner}}` | `{{duration}}` |
| Go-live | Productie-activatie / Production activation | `{{owner}}` | `{{date}}` |

---

*Dit document is gegenereerd door Preflight en dient te worden gereviewd door de integratie-architect en het Cloverleaf-team.*
*This document was generated by Preflight and must be reviewed by the integration architect and Cloverleaf team.*

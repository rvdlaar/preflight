# {% if language == "nl" %}Operationele Gereedheid Checklist{% else %}Operational Readiness Checklist{% endif %}

**{% if language == "nl" %}Voorstel{% else %}Proposal{% endif %}:** {{ proposal_name }}
**PSA-referentie / PSA reference:** {{ psa_id }}
**{% if language == "nl" %}Datum{% else %}Date{% endif %}:** {{ date }}
**{% if language == "nl" %}Infrastructuurarchitect{% else %}Infrastructure architect{% endif %}:** {{ architect_name }}
**{% if language == "nl" %}Versie{% else %}Version{% endif %}:** {{ version }}
**BIV:** B={{ biv_b }} I={{ biv_i }} V={{ biv_v }}
**Status:** {{ status }}

> *{% if language == "nl" %}Alle items moeten zijn afgevinkt of expliciet geaccepteerd als N.v.t. voordat go-live kan plaatsvinden.{% else %}All items must be checked off or explicitly accepted as N/A before go-live.{% endif %}*

[§P:infrastructure]

---

## 1. Monitoring

- ☐ SLIs {% if language == "nl" %}gedefinieerd en meetbaar{% else %}defined and measurable{% endif %}
- ☐ Alerting {% if language == "nl" %}geconfigureerd en getest{% else %}configured and tested{% endif %}
- ☐ Dashboards {% if language == "nl" %}beschikbaar{% else %}available{% endif %}
- ☐ Escalatiepaden {% if language == "nl" %}gedocumenteerd{% else %}documented{% endif %}
- ☐ On-call rooster {% if language == "nl" %}actief{% else %}active{% endif %}

---

## 2. Backup

- ☐ {% if language == "nl" %}Backupschema actief{% else %}Backup schedule active{% endif %}
- ☐ Retentie {% if language == "nl" %}afgestemd op bewaartermijnen{% else %}aligned with retention requirements{% endif %} (Wgbo, AVG)
- ☐ Restore {% if language == "nl" %}getest en gedocumenteerd{% else %}tested and documented{% endif %}

---

## 3. Patching

- ☐ {% if language == "nl" %}Patchverantwoordelijkheden toegewezen{% else %}Patch responsibilities assigned{% endif %} (OS, middleware, {% if language == "nl" %}applicatie{% else %}application{% endif %})
- ☐ {% if language == "nl" %}Testomgeving beschikbaar{% else %}Test environment available{% endif %}
- ☐ Noodpatchprocedure {% if language == "nl" %}gedocumenteerd{% else %}documented{% endif %}

---

## 4. Incident Response

- ☐ Escalatiepad {% if language == "nl" %}gedocumenteerd{% else %}documented{% endif %}
- ☐ On-call rooster {% if language == "nl" %}actief{% else %}active{% endif %}
- ☐ Runbook {% if language == "nl" %}compleet{% else %}complete{% endif %}
- ☐ Incidentcategorieën in TOPdesk

---

## 5. DR

- ☐ DR-tier toegewezen (BIV B={{ biv_b }})
- ☐ Failover-procedure {% if language == "nl" %}gedocumenteerd{% else %}documented{% endif %}
- ☐ Failover {% if language == "nl" %}getest{% else %}tested{% endif %}

---

## 6. {% if language == "nl" %}Toegangsbeheer{% else %}Access Management{% endif %}

- ☐ Provisioning-procedure {% if language == "nl" %}gereed{% else %}ready{% endif %}
- ☐ Deprovisioning {% if language == "nl" %}gekoppeld aan HR{% else %}linked to HR{% endif %}
- ☐ Toegangsreview-cyclus {% if language == "nl" %}ingepland{% else %}scheduled{% endif %}

---

## 7. {% if language == "nl" %}Beveiligingsmonitoring{% else %}Security Monitoring{% endif %}

- ☐ SIEM-integratie {% if language == "nl" %}actief{% else %}active{% endif %}
{% if biv_v >= 3 %}- ☐ NEN 7513 logging {% if language == "nl" %}actief{% else %}active{% endif %} [§K:nen7513]{% endif %}
- ☐ SOC {% if language == "nl" %}geïnformeerd{% else %}informed{% endif %}

[§P:security]

---

## 8. Go-Live

| # | {% if language == "nl" %}Item{% else %}Item{% endif %} | Status |
|---|---|---|
| 1 | Monitoring | ☐ {% if language == "nl" %}Gereed{% else %}Ready{% endif %} ☐ N.v.t. |
| 2 | Backup | ☐ {% if language == "nl" %}Gereed{% else %}Ready{% endif %} ☐ N.v.t. |
| 3 | Patching | ☐ {% if language == "nl" %}Gereed{% else %}Ready{% endif %} ☐ N.v.t. |
| 4 | Incident response | ☐ {% if language == "nl" %}Gereed{% else %}Ready{% endif %} ☐ N.v.t. |
| 5 | DR | ☐ {% if language == "nl" %}Gereed{% else %}Ready{% endif %} ☐ N.v.t. |
| 6 | {% if language == "nl" %}Toegang{% else %}Access{% endif %} | ☐ {% if language == "nl" %}Gereed{% else %}Ready{% endif %} ☐ N.v.t. |
| 7 | Security | ☐ {% if language == "nl" %}Gereed{% else %}Ready{% endif %} ☐ N.v.t. |
| 8 | {% if language == "nl" %}Documentatie{% else %}Documentation{% endif %} | ☐ {% if language == "nl" %}Gereed{% else %}Ready{% endif %} ☐ N.v.t. |

**Go-live beslissing:** ☐ Go ☐ No-go ☐ {% if language == "nl" %}Conditioneel{% else %}Conditional{% endif %}

---

## {% if language == "nl" %}Wijzigingshistorie{% else %}Change History{% endif %}

| {% if language == "nl" %}Versie{% else %}Version{% endif %} | {% if language == "nl" %}Datum{% else %}Date{% endif %} | {% if language == "nl" %}Auteur{% else %}Author{% endif %} | {% if language == "nl" %}Wijziging{% else %}Change{% endif %} |
|--------|-------|--------|-----------|
| 0.1 | {{ date }} | Preflight | {% if language == "nl" %}Initieel concept{% else %}Initial draft{% endif %} |

---

*{% if language == "nl" %}Preflight doet het huiswerk. De architect voegt oordeel toe. Het board beslist.{% else %}Preflight does the homework. The architect adds judgment. The board decides.{% endif %}*
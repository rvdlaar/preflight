# {% if language == "nl" %}Leveranciers- en Productbeoordeling{% else %}Vendor & Product Assessment{% endif %}

**{% if language == "nl" %}Voorstel{% else %}Proposal{% endif %}:** {{ proposal_name }}
**{% if language == "nl" %}Datum{% else %}Date{% endif %}:** {{ date }}
**{% if language == "nl" %}Opgesteld door{% else %}Prepared by{% endif %}:** {{ architect_name }}
**{% if language == "nl" %}Versie{% else %}Version{% endif %}:** {{ version }}

---

## 1. {% if language == "nl" %}Leveranciersprofiel{% else %}Vendor Profile{% endif %}

| {% if language == "nl" %}Veld{% else %}Field{% endif %} | {% if language == "nl" %}Waarde{% else %}Value{% endif %} |
|---|---|
| {% if language == "nl" %}Leverancier{% else %}Vendor{% endif %} | {{ vendor_name | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Vestigingsland{% else %}Country{% endif %} | {{ vendor_country | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Bestaande relatie{% else %}Existing relationship{% endif %} | {{ vendor_existing | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Financiële stabiliteit{% else %}Financial stability{% endif %} | {{ vendor_financial_stability | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Referenties NL ziekenhuizen{% else %}NL hospital references{% endif %} | {{ vendor_nl_references | default("[ARCHITECT INPUT NEEDED]") }} |

[§P:application], [§P:risk]

---

## 2. {% if language == "nl" %}Productbeoordeling{% else %}Product Assessment{% endif %}

| {% if language == "nl" %}Veld{% else %}Field{% endif %} | {% if language == "nl" %}Waarde{% else %}Value{% endif %} |
|---|---|
| {% if language == "nl" %}Product{% else %}Product{% endif %} | {{ product_name | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Categorie{% else %}Category{% endif %} | {{ product_category | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Bedrijfsfunctie (ZiRA){% else %}Business function (ZiRA){% endif %} | {{ product_zira_function | default("[—]") }} |
| {% if language == "nl" %}Overlap met landschap{% else %}Landscape overlap{% endif %} | {{ product_landscape_overlap | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Hosting model{% else %}Hosting model{% endif %} | {{ product_hosting | default("[ARCHITECT INPUT NEEDED]") }} |
| BIV | B={{ biv_b }} I={{ biv_i }} V={{ biv_v }} |
| {% if language == "nl" %}Persoonsgegevens{% else %}Personal data{% endif %} | {{ product_personal_data | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Bijzondere persoonsgegevens{% else %}Special category data{% endif %} | {{ product_special_category_data | default("[ARCHITECT INPUT NEEDED]") }} |

[§P:security], [§P:dataprivacy]

---

## 3. Technology Radar {% if language == "nl" %}Positie{% else %}Position{% endif %}

| {% if language == "nl" %}Veld{% else %}Field{% endif %} | {% if language == "nl" %}Waarde{% else %}Value{% endif %} |
|---|---|
| {% if language == "nl" %}Aanbevolen ring{% else %}Recommended ring{% endif %} | {{ tech_radar_status | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Rationale{% else %}Rationale{% endif %} | {{ tech_radar_rationale | default("[ARCHITECT INPUT NEEDED]") }} |

---

## 4. AIVG 2022 + {% if language == "nl" %}Module ICT{% else %}ICT Module{% endif %} — {% if language == "nl" %}Compliancechecklist{% else %}Compliance Checklist{% endif %}

| {% if language == "nl" %}Item{% else %}Item{% endif %} | {% if language == "nl" %}Status{% else %}Status{% endif %} | {% if language == "nl" %}Evidentie{% else %}Evidence{% endif %} |
|---|---|---|
| NEN 7510 / ISO 27001 | {{ vendor_nen7510 | default("[ARCHITECT INPUT NEEDED]") }} | [—] |
| NEN 7512 | {{ vendor_nen7512 | default("[—]") }} | [—] |
| NEN 7513 | {{ vendor_nen7513 | default("[—]") }} | [—] |
| {% if language == "nl" %}Verwerkersovereenkomst (BOZ-model){% else %}DPA (BOZ model){% endif %} | {{ vendor_dpa | default("[ARCHITECT INPUT NEEDED]") }} | [—] |
| {% if language == "nl" %}Hosting binnen EER{% else %}Hosting within EEA{% endif %} | {{ vendor_hosting_eer | default("[ARCHITECT INPUT NEEDED]") }} | [—] |
| {% if language == "nl" %}Exit-clausule{% else %}Exit clause{% endif %} | {{ vendor_exit_clause | default("[ARCHITECT INPUT NEEDED]") }} | [—] |
| {% if language == "nl" %}Broncode-escrow{% else %}Source code escrow{% endif %} | {{ vendor_escrow | default("[—]") }} | [—] |
| {% if language == "nl" %}Penetratietest ≤12m{% else %}Pentest ≤12m{% endif %} | {{ vendor_pentest | default("[—]") }} | [—] |
| SLA {% if language == "nl" %}beschikbaarheid{% else %}availability{% endif %} | {{ vendor_sla_availability | default("[ARCHITECT INPUT NEEDED]") }} | [—] |
| {% if language == "nl" %}Auditrecht{% else %}Audit right{% endif %} | {{ vendor_audit_right | default("[ARCHITECT INPUT NEEDED]") }} | [—] |

[§K:aivg2022-ict], [§P:security], [§P:risk]

---

## 5. {% if language == "nl" %}Persona-inbreng{% else %}Persona Input{% endif %}

| Persona | {% if language == "nl" %}Naam{% else %}Name{% endif %} | Rating | {% if language == "nl" %}Kernbevinding{% else %}Key finding{% endif %} |
|---------|------|--------|---------|
{% for pf in persona_findings %}| {{ pf.role | default(pf.name) }} | {{ pf.name }} | {{ pf.rating | rating_nl }} | {{ pf.findings[0] | default("[—]") | truncate(60) }} [§P:{{ pf.name }}] |
{% endfor %}
{% if not persona_findings %}| — | — | — | — |
{% endif %}

---

## 6. {% if language == "nl" %}Advies aan EA-raad{% else %}Recommendation to EA Board{% endif %}

**{% if language == "nl" %}Advies{% else %}Recommendation{% endif %}:** {{ recommendation }}

**{% if language == "nl" %}Voorwaarden{% else %}Conditions{% endif %}:**
{% for pf in persona_findings %}{% if pf.rating in ("conditional", "concern", "block") %}{% for c in pf.conditions %}
- {{ c }} [§P:{{ pf.name }}]
{% endfor %}{% endif %}{% endfor %}

---

*{% if language == "nl" %}Preflight doet het huiswerk. De architect voegt oordeel toe. Het board beslist.{% else %}Preflight does the homework. The architect adds judgment. The board decides.{% endif %}*
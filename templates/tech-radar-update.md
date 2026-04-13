# {% if language == "nl" %}Technologieradar-wijziging{% else %}Technology Radar Update{% endif %}

**{% if language == "nl" %}Voorstel{% else %}Proposal{% endif %}:** {{ proposal_name }}
**{% if language == "nl" %}Datum{% else %}Date{% endif %}:** {{ date }}
**{% if language == "nl" %}Versie{% else %}Version{% endif %}:** {{ version }}

[§P:application], [§P:enterprise]

---

## {% if language == "nl" %}Technologie{% else %}Technology{% endif %}

| {% if language == "nl" %}Veld{% else %}Field{% endif %} | {% if language == "nl" %}Waarde{% else %}Value{% endif %} |
|---|---|
| {% if language == "nl" %}Naam{% else %}Name{% endif %} | {{ tech_radar_name | default(proposal_name) }} |
| {% if language == "nl" %}Categorie{% else %}Category{% endif %} | {{ tech_radar_category | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Huidige ring{% else %}Current ring{% endif %} | {{ tech_radar_current_ring | default("Nieuw") }} |
| {% if language == "nl" %}Aanbevolen ring{% else %}Recommended ring{% endif %} | {{ tech_radar_status | default("[ARCHITECT INPUT NEEDED]") }} |

---

## Rationale

{{ tech_radar_rationale | default("[ARCHITECT INPUT NEEDED]") }}

---

## {% if language == "nl" %}Voorwaarden voor Ringverandering{% else %}Conditions for Ring Movement{% endif %}

{% for cond in tech_radar_conditions %}
- {{ cond }}
{% endfor %}
{% if not tech_radar_conditions %}
- [ARCHITECT INPUT NEEDED]
{% endif %}

---

## {% if language == "nl" %}Gerelateerde Items{% else %}Related Landscape Items{% endif %}

{% for app in existing_apps %}
- {{ app.name | default(app) }} {% if app.lifecycle %}({{ app.lifecycle }}){% endif %}
{% endfor %}
{% if not existing_apps %}
- [ARCHITECT INPUT NEEDED]
{% endif %}

[§K:archimate]

---

## {% if language == "nl" %}Risico's{% else %}Risks{% endif %}

{% for pf in persona_findings %}{% if pf.rating in ("concern", "block") %}
- {{ pf.findings[0] | default("") }} [§P:{{ pf.name }}]
{% endif %}{% endfor %}
{% if not persona_findings %}
- [ARCHITECT INPUT NEEDED]
{% endif %}

---

## {% if language == "nl" %}Besluit EA-raad{% else %}EA Board Decision{% endif %}

| {% if language == "nl" %}Veld{% else %}Field{% endif %} | {% if language == "nl" %}Waarde{% else %}Value{% endif %} |
|---|---|
| {% if language == "nl" %}Besluit{% else %}Decision{% endif %} | [BOARD DECISION NEEDED] |
| {% if language == "nl" %}Voorwaarden{% else %}Conditions{% endif %} | {{ conditions_table | default("[—]") }} |

---

*{% if language == "nl" %}Preflight doet het huiswerk. De architect voegt oordeel toe. Het board beslist.{% else %}Preflight does the homework. The architect adds judgment. The board decides.{% endif %}*
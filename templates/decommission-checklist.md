# {% if language == "nl" %}Decommission Checklist{% else %}Decommission Checklist{% endif %} — {{ proposal_name }}

**{% if language == "nl" %}Datum{% else %}Date{% endif %}:** {{ date }} | **Status:** {{ status }} | **{% if language == "nl" %}Architect{% else %}Architect{% endif %}:** {{ architect_name }}

[§P:infrastructure], [§P:security], [§P:dataprivacy]

---

## 1. {% if language == "nl" %}Systeemidentificatie{% else %}System Identification{% endif %}

| {% if language == "nl" %}Veld{% else %}Field{% endif %} | {% if language == "nl" %}Waarde{% else %}Value{% endif %} |
|-------|-------|
| {% if language == "nl" %}Systeemnaam{% else %}System name{% endif %} | {{ decommission_system_name | default(proposal_name) }} |
| CMDB | {{ decommission_cmdb_id | default("[ARCHITECT INPUT NEEDED]") }} |
| {% if language == "nl" %}Huidige eigenaar{% else %}Current owner{% endif %} | {{ decommission_owner | default("[ARCHITECT INPUT NEEDED]") }} |
| Vendor | {{ vendor_name | default("[ARCHITECT INPUT NEEDED]") }} |

---

## 2. {% if language == "nl" %}Afhankelijkheidsanalyse{% else %}Dependency Analysis{% endif %}

### {% if language == "nl" %}Upstream{% else %}Upstream{% endif %}

| {% if language == "nl" %}Systeem{% else %}System{% endif %} | {% if language == "nl" %}Interface{% else %}Interface{% endif %} | {% if language == "nl" %}Impact{% else %}Impact{% endif %} |
|--------|-----------|------|
{% for dep in decommission_upstream %}| {{ dep.system }} | {{ dep.interface | default("[—]") }} | {{ dep.impact }} |
{% endfor %}
{% if not decommission_upstream %}| [ARCHITECT INPUT NEEDED] | | |
{% endif %}

### {% if language == "nl" %}Downstream{% else %}Downstream{% endif %}

| {% if language == "nl" %}Systeem{% else %}System{% endif %} | {% if language == "nl" %}Interface{% else %}Interface{% endif %} | {% if language == "nl" %}Migratieplan{% else %}Migration plan{% endif %} |
|--------|-----------|------|
{% for dep in decommission_downstream %}| {{ dep.system }} | {{ dep.interface | default("[—]") }} | {{ dep.migration_plan | default("[ARCHITECT INPUT NEEDED]") }} |
{% endfor %}
{% if not decommission_downstream %}| [ARCHITECT INPUT NEEDED] | | |
{% endif %}

[§K:archimate]

---

## 3. {% if language == "nl" %}Data Migratie{% else %}Data Migration{% endif %}

| {% if language == "nl" %}Dataset{% else %}Dataset{% endif %} | {% if language == "nl" %}Gevoeligheid{% else %}Sensitivity{% endif %} | {% if language == "nl" %}Bestemming{% else %}Destination{% endif %} | Status |
|---------|--------|-------------|--------|
{% for ds in decommission_data_sets %}| {{ ds.name }} | {{ ds.sensitivity }} | {{ ds.destination | default("[ARCHITECT INPUT NEEDED]") }} | {{ ds.status | default("Open") }} |
{% endfor %}
{% if not decommission_data_sets %}| [ARCHITECT INPUT NEEDED] | | | |
{% endif %}

{% if biv_v >= 2 %}
- ☐ FG-DPO {% if language == "nl" %}akkoord{% else %}approval{% endif %} {% if language == "nl" %}patiëntdata-migratie{% else %}for patient data migration{% endif %} [§P:fgdpo]
{% endif %}

---

## 4. {% if language == "nl" %}Regelgeving{% else %}Regulatory{% endif %}

- ☐ AVG/GDPR {% if language == "nl" %}verwerkingsregister geüpdatet{% else %}processing register updated{% endif %} [§K:avg-art30]
- ☐ DPIA {% if language == "nl" %}afsluiting{% else %}closure{% endif %} {% if language == "nl" %}beoordeeld{% else %}assessed{% endif %} [§P:fgdpo]
- ☐ NEN 7510 {% if language == "nl" %}audit log retentie{% else %}audit log retention{% endif %} (≥3 jaar) [§K:nen7513]
- ☐ Vendor {% if language == "nl" %}data verwijdering bevestigd{% else %}data deletion confirmed{% endif %}

---

## 5. {% if language == "nl" %}Technische Stappen{% else %}Technical Steps{% endif %}

- ☐ {% if language == "nl" %}Nieuwe gebruikerstoegang uitgeschakeld{% else %}Disable new user access{% endif %}
- ☐ Read-only {% if language == "nl" %}modus{% else %}mode{% endif %} (datum: ___)
- ☐ API keys / service accounts {% if language == "nl" %}ingetrokken{% else %}revoked{% endif %} [§P:security]
- ☐ SSO / IdP {% if language == "nl" %}verwijderd{% else %}removed{% endif %}
- ☐ CMDB status → "Retired"
- ☐ Monitoring / alerting {% if language == "nl" %}verwijderd{% else %}removed{% endif %}
- ☐ DR-plan {% if language == "nl" %}geüpdatet{% else %}updated{% endif %}
- ☐ Firewall regels {% if language == "nl" %}verwijderd{% else %}removed{% endif %} [§P:infrastructure]
- ☐ Infrastructuur {% if language == "nl" %}uitgeschakeld{% else %}decommissioned{% endif %}

---

## 6. Sign-off

| {% if language == "nl" %}Rol{% else %}Role{% endif %} | {% if language == "nl" %}Naam{% else %}Name{% endif %} | {% if language == "nl" %}Datum{% else %}Date{% endif %} |
|------|------|------|
| {% if language == "nl" %}Applicatie-eigenaar{% else %}Application owner{% endif %} | | |
| Data owner | | |
| {% if language == "nl" %}Security architect{% else %}Security architect{% endif %} | | |
| Enterprise architect | | |
{% if biv_v >= 2 %}| FG-DPO | | |
{% endif %}

---

{{ disclaimer }}
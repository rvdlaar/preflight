# {% if language == "nl" %}Niet-Functionele Eisen Specificatie{% else %}Non-Functional Requirements Specification{% endif %}

**{% if language == "nl" %}Voorstel{% else %}Proposal{% endif %}:** {{ proposal_name }}
**PSA-referentie / PSA reference:** {{ psa_id }}
**{% if language == "nl" %}Datum{% else %}Date{% endif %}:** {{ date }}
**{% if language == "nl" %}Architect{% else %}Architect{% endif %}:** {{ architect_name }}
**{% if language == "nl" %}Versie{% else %}Version{% endif %}:** {{ version }}
**BIV:** B={{ biv_b }} I={{ biv_i }} V={{ biv_v }}
**Status:** {{ status }}

> *{% if language == "nl" %}Velden met [ARCHITECT INPUT NEEDED] vereisen menselijk oordeel.{% else %}Fields marked [ARCHITECT INPUT NEEDED] require human judgment.{% endif %}*

[§P:enterprise], [§P:infrastructure], [§P:security]

---

## 1. {% if language == "nl" %}BIV-afgeleide Eisen{% else %}BIV-Derived Requirements{% endif %}

### 1.1 B={{ biv_b }} — {% if language == "nl" %}Beschikbaarheid{% else %}Availability{% endif %}

| NFR-ID | {% if language == "nl" %}Eis{% else %}Requirement{% endif %} | {% if language == "nl" %}Bron{% else %}Source{% endif %} | {% if language == "nl" %}Doel{% else %}Target{% endif %} |
|---|---|---|---|
| NFR-A01 | {% if language == "nl" %}Systeembeschikbaarheid{% else %}System availability{% endif %} | BIV B={{ biv_b }} | {% if biv_b >= 3 %}≥99.5%{% elif biv_b >= 2 %}≥99.0%{% else %}≥95.0%{% endif %} |
| NFR-A02 | RPO | BIV B={{ biv_b }} | {{ biv_rpo }} |
| NFR-A03 | RTO | BIV B={{ biv_b }} | {{ biv_rto }} |
{% if biv_b >= 3 %}| NFR-A04 | DR-plan | BIV B=3 | {% if language == "nl" %}Jaarlijks getest{% else %}Tested annually{% endif %} |
| NFR-A05 | HA {% if language == "nl" %}architectuur{% else %}architecture{% endif %} | BIV B=3 | {% if language == "nl" %}Geen SPOF{% else %}No SPOF{% endif %} |
{% endif %}

### 1.2 I={{ biv_i }} — {% if language == "nl" %}Integriteit{% else %}Integrity{% endif %}

| NFR-ID | {% if language == "nl" %}Eis{% else %}Requirement{% endif %} | {% if language == "nl" %}Bron{% else %}Source{% endif %} | {% if language == "nl" %}Doel{% else %}Target{% endif %} |
|---|---|---|---|
| NFR-I01 | {% if language == "nl" %}Datavalidatie{% else %}Data validation{% endif %} | BIV I={{ biv_i }} | {% if biv_i >= 2 %}{% if language == "nl" %}Verplicht{% else %}Required{% endif %}{% else %}{% if language == "nl" %}Aanbevolen{% else %}Recommended{% endif %}{% endif %} |
{% if biv_i >= 3 %}| NFR-I02 | Audit trail (NEN 7513) | BIV I=3 | {% if language == "nl" %}Alle mutaties gelogd{% else %}All mutations logged{% endif %} [§K:nen7513] |
| NFR-I04 | Checksums | BIV I=3 | {% if language == "nl" %}Verplicht{% else %}Required{% endif %} |
{% endif %}

### 1.3 V={{ biv_v }} — {% if language == "nl" %}Vertrouwelijkheid{% else %}Confidentiality{% endif %}

| NFR-ID | {% if language == "nl" %}Eis{% else %}Requirement{% endif %} | {% if language == "nl" %}Bron{% else %}Source{% endif %} | {% if language == "nl" %}Doel{% else %}Target{% endif %} |
|---|---|---|---|
| NFR-V01 | {% if language == "nl" %}Encryptie at rest{% else %}Encryption at rest{% endif %} | V={{ biv_v }} [§P:security] | {% if biv_v >= 3 %}AES-256{% elif biv_v >= 2 %}TLS 1.2+{% else %}{% if language == "nl" %}Aanbevolen{% else %}Recommended{% endif %}{% endif %} |
| NFR-V02 | {% if language == "nl" %}Encryptie in transit{% else %}Encryption in transit{% endif %} | V={{ biv_v }} [§P:security] | {% if biv_v >= 2 %}TLS 1.2+{% else %}{% if language == "nl" %}Aanbevolen{% else %}Recommended{% endif %}{% endif %} |
{% if biv_v >= 3 %}| NFR-V04 | NEN 7513 logging | V=3 [§K:nen7513] | {% if language == "nl" %}5 jaar bewaartermijn{% else %}5 year retention{% endif %} |
| NFR-V05 | ABAC {% if language == "nl" %}patiëntdata{% else %}patient data{% endif %} | V=3 | {% if language == "nl" %}Behandelrelatie-check{% else %}Treatment relationship check{% endif %} |
{% endif %}

---

## 2. {% if language == "nl" %}Prestatie-eisen{% else %}Performance Requirements{% endif %}

| NFR-ID | {% if language == "nl" %}Eis{% else %}Requirement{% endif %} | {% if language == "nl" %}Doel{% else %}Target{% endif %} |
|---|---|---|
| NFR-P01 | {% if language == "nl" %}Gebruikersresponstijd{% else %}User response time{% endif %} | [ARCHITECT INPUT NEEDED] |
| NFR-P02 | API {% if language == "nl" %}responstijd{% else %}response time{% endif %} | [ARCHITECT INPUT NEEDED] |

---

## 3. {% if language == "nl" %}Beveiligingseisen{% else %}Security NFRs{% endif %}

| NFR-ID | {% if language == "nl" %}Eis{% else %}Requirement{% endif %} | {% if language == "nl" %}Bron{% else %}Source{% endif %} | {% if language == "nl" %}Doel{% else %}Target{% endif %} |
|---|---|---|---|
| NFR-SEC01 | MFA | [§P:security] | {% if language == "nl" %}Verplicht{% else %}Required{% endif %} |
| NFR-SEC04 | {% if language == "nl" %}Penetratietest{% else %}Penetration test{% endif %} | [§P:security] | {% if language == "nl" %}Voor go-live{% else %}Before go-live{% endif %} |
| NFR-SEC06 | Hardening | [§P:security] | CIS Benchmark |

---

## 4. {% if language == "nl" %}Gegevensbewaring{% else %}Data Retention{% endif %}

| NFR-ID | {% if language == "nl" %}Eis{% else %}Requirement{% endif %} | {% if language == "nl" %}Doel{% else %}Target{% endif %} |
|---|---|---|
| NFR-DR01 | {% if language == "nl" %}Medisch dossier{% else %}Medical record{% endif %} | 20 jaar (Wgbo) |
| NFR-DR02 | {% if language == "nl" %}Toegangslogs{% else %}Access logs{% endif %}{% if biv_v >= 3 %} (NEN 7513){% endif %} | {% if biv_v >= 3 %}≥5 jaar{% else %}[ARCHITECT INPUT NEEDED]{% endif %} |

[§P:fgdpo]

---

## 5. {% if language == "nl" %}Samenvatting{% else %}Summary{% endif %}

**{% if language == "nl" %}Aanbeveling{% else %}Recommendation{% endif %}:** {{ recommendation }}

---

## {% if language == "nl" %}Wijzigingshistorie{% else %}Change History{% endif %}

| {% if language == "nl" %}Versie{% else %}Version{% endif %} | {% if language == "nl" %}Datum{% else %}Date{% endif %} | {% if language == "nl" %}Auteur{% else %}Author{% endif %} | {% if language == "nl" %}Wijziging{% else %}Change{% endif %} |
|--------|-------|--------|-----------|
| 0.1 | {{ date }} | Preflight | {% if language == "nl" %}Initieel concept{% else %}Initial draft{% endif %} |

---

*{% if language == "nl" %}Preflight doet het huiswerk. De architect voegt oordeel toe. Het board beslist.{% else %}Preflight does the homework. The architect adds judgment. The board decides.{% endif %}*
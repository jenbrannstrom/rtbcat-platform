# Ofte stillede spørgsmål

Spørgsmål er tagget efter målgruppe: **[Køber]** for mediakøbere og
kampagneansvarlige, **[DevOps]** for platformingeniører, **[Begge]** for
fælles spørgsmål.

---

### [Køber] Hvorfor er min dækningsprocent under 100%?

Dækning måler, hvor mange dato x rapporttype-celler der har data i forhold
til, hvor mange der forventes. Almindelige årsager til huller:

- **Google sendte ikke en rapport** for den dato (helligdag, eksportforsinkelse).
- **Gmail-importen gik glip af e-mailen** (tjek Gmail-status).
- **En bestemt rapporttype er ikke tilgængelig** for dit seat (f.eks. findes
  kvalitetsdata muligvis ikke for alle købere).

Tjek datafriskheds-gitteret på `/import` for at se præcis, hvilke celler der
mangler. Se [Dataimport](09-data-import.md).

### [Køber] Hvad er forskellen mellem "spild" og "lav vindrate"?

**Spild** = budforespørgsler, din bidder *afviste* uden at byde. Det er QPS,
du betalte for, men slet ikke kunne bruge. Løs det med pretargeting.

**Lav vindrate** = budforespørgsler, din bidder *bød på*, men tabte
auktionen. Det betyder, at dine bud ikke er konkurrencedygtige nok. Løs det
med budstrategi, ikke pretargeting.

Begge vises i tragten, men kræver forskellige handlinger. Se
[Forstå din QPS-tragt](03-qps-funnel.md).

### [Køber] Kan jeg fortryde en pretargeting-ændring?

Ja. Gå til `/history`, find ændringen, klik "Forhåndsvis rollback" for at se,
hvad der vil blive tilbageført, og bekræft derefter. Selve rollbacken
registreres. Se [Pretargeting-konfiguration](06-pretargeting.md).

### [Køber] Hvor ofte bør jeg genimportere data?

Dagligt. Gmail-autoimport håndterer dette automatisk. Hvis du importerer
manuelt, gør det én gang om dagen, efter rapporterne er ankommet. Forældede
data betyder forældede beslutninger.

### [Køber] Hvad ændrer optimizeren egentlig?

Optimizeren foreslår ændringer til dine pretargeting-konfigurationer: tilføjelse
eller fjernelse af geografier, formater, publishers osv. Den anvender aldrig
ændringer automatisk. Du gennemgår og godkender hvert forslag. Se
[Optimizeren](07-optimizer.md).

---

### [DevOps] Hvorfor fejlede runtime health strict-gaten?

Tjek workflow-loggen: `gh run view <id> --log-failed`. Se efter FAIL vs.
BLOCKED:

- **FAIL** = noget gik i stykker. Datafriskheds-timeout og
  SET statement_timeout-problemer er almindelige årsager. Se
  [Fejlsøgning](15-troubleshooting.md).
- **BLOCKED** = en afhængighed mangler, ikke nødvendigvis en kodefejl.
  Eksempler: ingen kvalitetsdata for denne køber, forslag mangler billing_id.
  Sammenlign med tidligere kørsler for at skelne regressioner fra allerede
  eksisterende huller.

### [DevOps] Hvorfor er data-freshness-endpointet langsomt?

Queryen scanner `rtb_daily` (~84M rækker) og `rtb_bidstream` (~21M rækker).
Hvis query-planen degraderer til en sekventiel scanning i stedet for at bruge
`(buyer_account_id, metric_date DESC)`-indekserne, tager det minutter.

Løsning: sørg for, at queries bruger `generate_series + EXISTS`-mønsteret
(14 indeksopslag i stedet for fuld tabelscanning). Se
[Databaseoperationer](14-database.md).

### [DevOps] Hvordan tjekker jeg, hvilken version der er deployet?

```bash
curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'
```

Dette returnerer git SHA og image-tag. Sammenlign med din commit-log.

### [DevOps] Hvordan deployer jeg en rettelse?

1. Push til `unified-platform`
2. Vent på at `build-and-push.yml` lykkes
3. Udløs `deploy.yml` via `gh workflow run` med `confirm=DEPLOY`
4. Verificér med `/api/health`

Se [Deployment](12-deployment.md) for den fulde procedure.

### [DevOps] Brugere sidder fast i en login-loop. Hvad gør jeg?

Tjek Cloud SQL Proxy: `sudo docker ps | grep cloudsql`. Hvis den er nede,
genstart den, vent 10 sekunder, og genstart derefter API-containeren. Se
[Fejlsøgning](15-troubleshooting.md) for den fulde procedure.

---

### [Begge] Hvor kommer Cat-Scans data fra?

Google Authorized Buyers CSV-eksporter. Der er ingen Reporting API. Data
ankommer enten via manuel CSV-upload eller automatisk Gmail-indlæsning. Se
[Dataimport](09-data-import.md).

### [Begge] Er det sikkert at genimportere den samme CSV?

Ja. Hver række hashes og deduplikeres. Genimportering dobbelttæller aldrig.

### [Begge] Hvilke sprog understøtter UI'et?

Engelsk, nederlandsk og kinesisk (forenklet). Sprogvælgeren findes i
sidepanelet.

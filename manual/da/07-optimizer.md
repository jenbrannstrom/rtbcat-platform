# Kapitel 7: Optimeringsværktøjet (BYOM)

*Målgruppe: medieindkøbere, optimeringsingeniører*

Optimeringsværktøjet er Cat-Scans automatiserede optimeringsmotor. "BYOM" står for
Bring Your Own Model: du registrerer et eksternt scoringsendpoint, og
Cat-Scan bruger det til at generere forslag til konfigurationsændringer.

## Hvordan det virker

```
  Score          Propose          Review          Apply
────────────> ────────────> ────────────> ────────────>
Din model      Cat-Scan       Du (menneske)  Google AB
evaluerer      genererer      godkend eller  konfiguration
segmenter      konfigurations-afvis          opdateres
               ændringer
```

1. **Score**: Cat-Scan sender segmentdata til dit model-endpoint. Modellen
   returnerer en score for hvert segment (geo, størrelse, udgiver).
2. **Propose**: Baseret på scorer genererer Cat-Scan specifikke pretargeting-
   konfigurationsændringer (f.eks. "ekskluder disse 5 geografier", "tilføj disse 3 størrelser").
3. **Review**: Du ser forslaget med projiceret effekt. Du godkender eller
   afviser.
4. **Apply**: Godkendte forslag anvendes på pretargeting-konfigurationen hos
   Google. Ændringen registreres i historikken.

## Modeladministration

### Registrering af en model

Gå til `/settings/system` og find sektionen Optimizer.

1. Klik på **Register Model**.
2. Udfyld: navn, modeltype, endpoint-URL (din scoringstjeneste).
3. Endpointet skal acceptere POST-anmodninger med segmentdata og returnere
   scorede resultater.
4. Gem.

### Validering af endpointet

Test din model før aktivering:

1. Klik på **Validate endpoint** på modelkortet.
2. Cat-Scan sender en testpakke til dit endpoint.
3. Resultater viser: svartid, svarformatets gyldighed, scorefordeling.
4. Ret eventuelle problemer før aktivering.

### Aktivering og deaktivering

- **Aktiver**: modellen bliver den aktive scorer for dette seat.
- **Deaktiver**: modellen stopper med at blive brugt, men dens konfiguration
  bevares. Kun én model kan være aktiv per seat ad gangen.

## Arbejdsgangsforindstillinger

Når du kører score-og-forslag, vælger du en forindstilling:

| Forindstilling | Adfærd | Hvornår den bruges |
|----------------|--------|---------------------|
| **Safe** | Foreslår kun ændringer med høj konfidens og lav risiko. Mindre forbedringer, lavere risiko for fejl. | Første gang med optimeringsværktøjet, eller konservative konti. |
| **Balanced** | Moderat konfidensgrænse. God balance mellem effekt og sikkerhed. | Standard for de fleste anvendelser. |
| **Aggressive** | Foreslår større ændringer med højere potentiel effekt. Større risiko for overoptimering. | Erfarne brugere, der overvåger dagligt og hurtigt kan rulle tilbage. |

## Økonomi

Optimeringsværktøjet sporer også optimeringens økonomi:

- **Effektiv CPM**: hvad du faktisk betaler per tusind visninger,
  når der tages højde for spild.
- **Hostingomkostningsgrundlag**: din bidders infrastrukturomkostning, konfigureret i
  optimeringsopsætningen. Bruges til at beregne, om besparelser fra QPS-reduktion
  opvejer hosting.
- **Effektivitetsoversigt**: samlet forholdstal mellem nyttigt QPS og totalt QPS.

Konfigurer dine hostingomkostninger under `/settings/system` > Optimizer Setup.

## Gennemgang af forslag

Hvert forslag viser:
- **Segmentscorer**, der drev anbefalingen
- **Specifikke ændringer** af pretargeting-felter (tilføjelser, fjernelser, opdateringer)
- **Projiceret effekt** på QPS, spildforhold og forbrug

Du kan:
- **Approve**: markerer forslaget som accepteret
- **Apply**: sender de godkendte ændringer til Google
- **Reject**: kasserer forslaget
- **Check apply status**: verificer at ændringerne er trådt i kraft hos Google

## Relateret

- [Pretargeting-konfiguration](06-pretargeting.md): de konfigurationer, som optimeringsværktøjet
  ændrer
- [Konverteringer og attribution](08-conversions.md): konverteringsdata bidrager
  til scoringskvalitet
- [Læs dine rapporter](10-reading-reports.md): spor effekten af optimeringsværktøjet

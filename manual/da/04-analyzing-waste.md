# Kapitel 4: Analyse af spild pr. dimension

*Målgruppe: mediekøbere, kampagneansvarlige*

Når du ved, *hvor meget* spild du har (fra [tragten](03-qps-funnel.md)),
fortæller disse tre visninger dig, *hvor* det stammer fra.

## Geografisk spild (`/qps/geo`)

Viser QPS-forbrug og performance pr. land og by.

![Geografisk QPS-opdeling pr. land](images/screenshot-geo-qps.png)

**Hvad du skal kigge efter:**
- Lande med høj QPS, men nul eller næsten nul vindere. Google sender dig
  trafik fra regioner, dine købere ikke målretter mod.
- Byer med uforholdsmæssigt stor QPS-andel men lavt forbrug, hvilket betyder
  long-tail-geografier, der tilføjer volumen men ingen værdi.

**Hvad du kan gøre ved det:**
- Tilføj underperformende geografier til din pretargeting-eksklusionsliste. Se
  [Pretargeting-konfiguration](06-pretargeting.md).

**Kontrolelementer:** Periodevælger (7/14/30 dage), pladsfilter.

## Udgiver-spild (`/qps/publisher`)

Viser performance opdelt pr. udgiverdomæne eller app.

![Udgiver-QPS med vinderprocent-analyse](images/screenshot-pub-qps.png)

**Hvad du skal kigge efter:**
- Domæner med højt budvolumen, men nul visninger. Din budgiver bruger
  beregningskraft på inventar, der aldrig vises.
- Apps eller sites med unormalt lave vinderprocenter. Du byder, men taber
  konsekvent, hvilket betyder, at du spilder tid på budevaluering.
- Kendte domæner med lav kvalitet.

**Hvad du kan gøre ved det:**
- Bloker specifikke udgivere i din pretargeting-konfigurations blokeringsliste.
  Cat-Scans udgivereditor gør dette enklere end Authorized Buyers-brugerfladen.

**Kontrolelementer:** Periodevælger, geografifilter, søg efter domæne.

## Størrelsesspild (`/qps/size`)

Viser, hvilke annoncestørrelser der modtager trafik, og om du har kreativer
til dem.

![QPS-opdeling pr. størrelse](images/screenshot-size-qps.png)

**Hvad du skal kigge efter:**
- Størrelser med høj QPS, men **ingen matchende kreativ**. Google sender ~400
  forskellige annoncestørrelser. Hvis du kører display-annoncer med fast
  størrelse (ikke HTML), er de fleste af disse størrelser irrelevante. Enhver
  forespørgsel på en umatchet størrelse er rent spild.
- Størrelser med kreativer, der underperformer. Overvej, om de kreative
  materialer er passende til det format.

**Hvad du kan gøre ved det:**
- Tilføj irrelevante størrelser til din pretargetings ekskluderede
  størrelses-liste. Dette er den enkelte optimering med størst effekt for
  display-købere.

**Kontrolelementer:** Periodevælger, pladsfilter, dækningsopdeling (diagram).

## Kombination af dimensioner

De tre visninger supplerer hinanden. En typisk optimeringscyklus:

1. Tjek **geografi**: ekskluder lande, du ikke har brug for.
2. Tjek **udgiver**: bloker domæner, der spilder bud.
3. Tjek **størrelse**: ekskluder størrelser uden matchende kreativ.
4. Anvend ændringer via [Pretargeting-konfiguration](06-pretargeting.md) med
   dry-run forhåndsvisning.
5. Vent en datacyklus (typisk en dag) og tjek tragten igen.

## Relateret

- [Forstå din QPS-tragt](03-qps-funnel.md): udgangspunktet
- [Pretargeting-konfiguration](06-pretargeting.md): handl på baggrund af spild-fund
- [Læs dine rapporter](10-reading-reports.md): følg effekten

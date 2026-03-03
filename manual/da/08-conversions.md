# Kapitel 8: Konverteringer og attribution

*Målgruppe: medieindkøbere, kampagneansvarlige*

Konverteringssporing lader Cat-Scan måle, hvad der sker efter en visning:
foretog brugeren en værdifuld handling? Disse data indgår i optimeringsværktøjets
scoring og hjælper dig med at evaluere den reelle kampagneydelse.

## Konverteringskilder

Cat-Scan understøtter to integrationsmetoder:

### Pixel

En sporingspixel affyres på din konverteringsside (f.eks. ordrebekræftelse).

- Endpoint: `/api/conversions/pixel`
- Parametre: `buyer_id`, `source_type=pixel`, `event_name`, `event_value`,
  `currency`, `event_ts`
- Ingen serversidekonfiguration kræves ud over at placere pixelen på din side.

### Webhook

Din server sender konverteringshændelser til Cat-Scans webhook-endpoint.

- Mere pålidelig end pixels (ingen ad-blockere, ingen klientside-afhængigheder).
- Kræver serversideintegration.
- Understøtter HMAC-signaturverifikation for sikkerhed.

## Webhook-sikkerhed

Cat-Scan tilbyder lagdelt webhook-sikkerhed:

| Funktion | Hvad den gør |
|----------|-------------|
| **HMAC-verifikation** | Hver webhook-anmodning signeres med en delt hemmelighed. Cat-Scan afviser usignerede eller fejlsignerede anmodninger. |
| **Hastighedsbegrænsning** | Forebygger misbrug ved at sætte en grænse for anmodninger per tidsvindue. |
| **Ferskhedsovervågning** | Advarer, hvis webhook-hændelser holder op med at ankomme (detektering af uaktualitet). |

Konfigurer webhook-sikkerhed under `/settings/system` > Conversion Health.

## Parathedstjek

Før du stoler på konverteringsdata, skal du verificere paratheden:

1. Gå til `/settings/system` eller opstartschecklisten.
2. Tjek **Conversion Readiness**: viser, om en kilde er forbundet og
   leverer hændelser inden for det forventede ferskhedsvindue.
3. Tjek **Ingestion Stats**: hændelsestal pr. kildetype og tidsperiode.

## Konverteringssundhed

Panelet Conversion Health viser:

- Indlæsningsstatus (modtager hændelser eller ej)
- Aggregeringsstatus (hændelser bliver behandlet til metrikker)
- Tidsstempel for seneste hændelse
- Fejlantal, hvis der er nogen

## Relateret

- [Optimeringsværktøjet](07-optimizer.md): konverteringsdata forbedrer scoringsnøjagtigheden
- [Dataimport](09-data-import.md): en anden dataindlæsningssti
- For DevOps: webhook-endpoint-konfiguration og fejlsøgning, se
  [Integrationer](17-integrations.md).

# Kapitel 16: Bruger- og rettighedsadministration

*Målgruppe: DevOps, systemadministratorer*

## Administrationspanel (`/admin`)

Administrationspanelet er kun synligt for brugere med `is_sudo`-flaget. Det giver adgang til brugerstyring, systemkonfiguration og revisionslogning.

## Brugerstyring (`/admin/users`)

### Oprettelse af brugere

To metoder:

| Metode | Hvornår den bruges |
|--------|-------------------|
| **Lokal konto** | Til brugere, der logger ind med e-mail og adgangskode. Du angiver den indledende adgangskode. |
| **OAuth-foroprettelse** | Til brugere, der logger ind med Google OAuth. Foroprettelse af posten giver dig mulighed for at tildele rettigheder før deres første login. |

Felter: e-mail (påkrævet), visningsnavn, rolle, autentificeringsmetode, adgangskode (kun lokal).

### Roller og rettigheder

**Globale rettigheder** styrer, hvad en bruger kan gøre på tværs af systemet:
- Standardbruger: adgang til hovedfunktioner
- Begrænset bruger: begrænset sidebar (ingen indstillinger, administration eller QPS-sektioner)
- Administrator (`is_sudo`): fuld adgang inklusive administrationspanelet

**Sæderettigheder** styrer, hvilke køberkonti en bruger kan se:
- Tildel adgang til specifikke `buyer_account_id`-værdier
- Adgangsniveauer kan variere pr. sæde
- En bruger uden sæderettigheder ser ingen data

### Administration af rettigheder

1. Gå til `/admin/users`
2. Vælg en bruger
3. Under "Sæderettigheder": tildel eller fjern adgang til købersæder
4. Under "Globale rettigheder": tildel eller fjern adgang på systemniveau
5. Ændringer træder i kraft ved brugerens næste sideindlæsning

### Deaktivering af brugere

Deaktivering af en bruger bevarer deres post (til revisionsloggen), men forhindrer login. Det sletter ikke deres data eller rettigheder; de kan genaktiveres.

## Tjenestekonti (`/settings/accounts`)

Tjenestekonti repræsenterer GCP-legitimationsoplysninger, der gør det muligt for Cat-Scan at kommunikere med Google API'er.

### Upload af legitimationsoplysninger

1. Gå til `/settings/accounts` > API Connection-fanen
2. Upload GCP-tjenestekontoens JSON-nøglefil
3. Cat-Scan validerer legitimationsoplysningerne og viser forbindelsesstatus

**Sikkerhedsbemærkning:** Tilføj kun tjenestekontoens JSON-nøgle i slutningen af opsætningen for at minimere eksponeringsrisikoen.

### Hvad tjenestekonti låser op

- **Sædeopdagelse**: find køberkonti tilknyttet legitimationsoplysningerne
- **Pretargeting-synkronisering**: hent aktuel konfigurationstilstand fra Google
- **RTB-endpoint-synkronisering**: opdag bidder-endpoints
- **Kreativindsamling**: indsaml kreativmetadata

## Revisionslog (`/admin/audit-log`)

Enhver væsentlig handling logges:

| Handling | Hvad der udløser den |
|----------|---------------------|
| `login` | Vellykket autentificering |
| `login_failed` | Mislykket autentificeringsforsøg |
| `login_blocked` | Login afvist (deaktiveret bruger osv.) |
| `create_user` | Ny bruger oprettet |
| `update_user` | Brugerprofil ændret |
| `deactivate_user` | Bruger deaktiveret |
| `reset_password` | Adgangskode nulstillet |
| `change_password` | Adgangskode ændret |
| `grant_permission` | Rettighed tildelt |
| `revoke_permission` | Rettighed fjernet |
| `update_setting` | Systemindstilling ændret |
| `create_initial_admin` | Første administrator oprettet under opsætning |

Filtre: efter bruger, handlingstype, ressourcetype, tidsvindue (dage), med paginering.

## Systemkonfiguration (`/admin/configuration`)

Globale nøgle-værdi-indstillinger, der styrer systemets adfærd. Redigerbare af administratorer. Ændringer registreres i revisionsloggen.

## Relateret

- [Login](01-logging-in.md): brugervendt autentificeringsoplevelse
- [Arkitekturoversigt](11-architecture.md): detaljer om autentificeringskæden

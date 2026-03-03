# Kapitel 1: Log ind

*Målgruppe: alle*

## Godkendelsesmetoder

Cat-Scan understøtter tre loginmetoder:

| Metode | Sådan fungerer det | Hvornår den skal bruges |
|--------|--------------------|------------------------|
| **Google OAuth** | Klik på "Sign in with Google", som omdirigerer gennem OAuth2 Proxy | De fleste brugere. Bruger din Google Workspace-konto. |
| **Authing (OIDC)** | Klik på "Sign in with Authing", som omdirigerer til OIDC-udbyderen | Organisationer, der bruger Authing som identitetsudbyder. |
| **E-mail og adgangskode** | Indtast legitimationsoplysninger direkte på login-siden | Lokale konti oprettet af en administrator. |

## Første login

1. Naviger til `https://scan.rtb.cat` (eller din installations-URL).
2. Du vil se login-siden med de tilgængelige login-muligheder.
3. Vælg din metode og godkend.
4. Ved første login opretter systemet automatisk din brugerpost (for
   OAuth-metoder). Din administrator skal muligvis give dig adgang til
   specifikke køber-pladser.

## Plads-vælgeren

Efter login ser du sidebjælken med en **plads-vælger** øverst. Hvis din konto
har adgang til flere køber-pladser, kan du bruge dropdown-menuen til at skifte
mellem dem. Alle data på hver side er afgrænset til den valgte plads.

- **Enkelt plads**: vælgeren viser dit pladsnavn og ID direkte.
- **Flere pladser**: en dropdown lader dig skifte. Hver post viser køberens
  visningsnavn, `buyer_account_id` og antal kreativer.
- **"Sync All"-knappen**: opdaterer kreativer, endpoints og
  pretargeting-konfigurationer fra Googles API for den valgte plads.

## Når login fejler

| Symptom | Sandsynlig årsag | Hvad du skal gøre |
|---------|------------------|-------------------|
| Omdirigerings-loop (siden genindlæser hele tiden) | Databasen er utilgængelig, så godkendelsestjekket fejler lydløst | Tjek Cloud SQL Proxy-containeren. Se [Fejlfinding](15-troubleshooting.md). |
| "Server unavailable" (502/503/504) | API- eller nginx-containeren er nede | Kontakt dit DevOps-team. Se [Sundhedsovervågning](13-health-monitoring.md). |
| "Authentication required" | Sessionen er udløbet, eller cookien er slettet | Log ind igen. |
| "You don't have access to this buyer account" | Tilladelser er ikke givet til denne plads | Spørg din administrator. Se [Brugeradministration](16-user-admin.md). |

## Næste skridt

- [Navigering i dashboardet](02-navigating-the-dashboard.md)

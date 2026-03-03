# Chapitre 9 : Import de donnees

*Public : acheteurs media, responsables de campagne*

L'analyse de Cat-Scan repose entierement sur les donnees de performance de Google Authorized Buyers. Comme Google ne fournit pas d'API de reporting, toutes les donnees proviennent d'exports CSV. Ce chapitre explique comment importer des donnees dans Cat-Scan et comment verifier qu'elles arrivent correctement.

## Pourquoi c'est important

Sans donnees importees, Cat-Scan n'a rien a analyser. L'entonnoir, les vues de gaspillage, les performances creatives et l'optimiseur dependent tous de donnees CSV recentes. Si vos donnees sont obsoletes, vos decisions reposent sur des informations perimees.

## Deux modes d'arrivee des donnees

### 1. Import CSV manuel (`/import`)

Glissez-deposez un fichier CSV exporte depuis Google Authorized Buyers.

![Page d'import de donnees avec zone de depot et grille de fraicheur](images/screenshot-import.png)

**Flux de travail :**

1. Exportez le rapport depuis votre compte Google Authorized Buyers.
2. Allez sur `/import` dans Cat-Scan.
3. Glissez le fichier dans la zone de depot (ou cliquez pour parcourir).
4. Cat-Scan **detecte automatiquement le type de rapport** et affiche un apercu :
   - Colonnes requises vs. colonnes trouvees
   - Nombre de lignes et plage de dates
   - Eventuelles erreurs de validation
5. Examinez l'apercu. Si des colonnes necessitent un remappage, utilisez l'editeur
   de correspondance de colonnes.
6. Cliquez sur **Importer**.
7. La barre de progression indique le statut du telechargement. Les fichiers de plus de 5 Mo
   sont telecharges en morceaux automatiquement.
8. Les resultats affichent : lignes importees, doublons ignores, erreurs le cas echeant.

**Types de rapports** detectes automatiquement :

| Type | Modele de nom CSV | Contenu |
|------|-------------------|---------|
| bidsinauction | `catscan-report-*` | Performance RTB quotidienne : impressions, encheres, gains, depenses |
| quality | `catscan-report-*` (metriques de qualite) | Signaux de qualite : visibilite, fraude, securite de marque |
| pipeline-geo | `*-pipeline-geo-*` | Repartition geographique du flux d'encheres |
| pipeline-publisher | `*-pipeline-publisher-*` | Repartition par domaine d'editeur |
| bid-filtering | `*-bid-filtering-*` | Raisons et volumes de filtrage des encheres |

### 2. Import automatique Gmail

Cat-Scan peut automatiquement ingerer les rapports depuis un compte Gmail connecte.

- Google Authorized Buyers envoie des rapports quotidiens par e-mail.
- L'integration Gmail de Cat-Scan lit ces e-mails et importe automatiquement les
  pieces jointes CSV.
- Verifiez le statut dans `/settings/accounts` > onglet Rapports Gmail, ou via
  `/gmail/status` dans l'API.

**Pour verifier que l'import Gmail fonctionne :**
- Verifiez le panneau Statut Gmail : `last_reason` doit etre `running`.
- Verifiez le compteur `unread` : un nombre eleve d'e-mails non lus peut indiquer que
  l'import est bloque.
- Verifiez l'historique d'import pour les entrees recentes.

## Grille de fraicheur des donnees

La grille de fraicheur des donnees (visible sur `/import` et utilisee par la porte de sante du runtime) affiche une **matrice date x type de rapport** :

```
              bidsinauction   quality   pipeline-geo   pipeline-publisher   bid-filtering
2026-03-02    imported        missing   imported       imported             imported
2026-03-01    imported        missing   imported       imported             imported
2026-02-28    imported        imported  imported       imported             imported
...
```

- **imported** : Cat-Scan dispose de donnees pour cette date et ce type de rapport.
- **missing** : aucune donnee trouvee. Soit le rapport n'a pas ete exporte, soit il n'a pas
  ete recu par Gmail, soit l'import a echoue.

Le **pourcentage de couverture** resume le degre de completude de vos donnees sur la fenetre d'observation. La porte de sante du runtime l'utilise pour determiner si le systeme est operationnel.

## Deduplication

Reimporter le meme CSV (ou laisser Gmail retraiter le meme e-mail) ne **double pas** le comptage des donnees. Chaque ligne est hashee, et les doublons sont ignores a l'insertion. Cela signifie qu'il est toujours possible de reimporter en toute securite.

## Historique des imports

Le tableau d'historique des imports sur `/import` affiche les 20 derniers imports :

- Horodatage
- Nom du fichier
- Nombre de lignes
- Declencheur de l'import (telechargement manuel vs. gmail-auto)
- Statut (termine, echoue, doublon)

## Depannage

| Probleme | Que verifier |
|----------|-------------|
| Cellules "missing" dans la grille de fraicheur | Le rapport a-t-il ete exporte depuis Google a cette date ? Verifiez dans Gmail si l'e-mail est present. |
| L'import echoue avec une erreur de validation | Incoherence de colonnes. Comparez le tableau des colonnes requises avec votre CSV. |
| L'import Gmail affiche "stopped" | Verifiez `/settings/accounts` > onglet Gmail. Il peut etre necessaire de redemarrer ou de reautoriser. |
| Le pourcentage de couverture baisse | Les rapports arrivent mais pour moins de dates que prevu. Verifiez le calendrier d'export dans Google AB. |

## Voir aussi

- [Comprendre votre entonnoir QPS](03-qps-funnel.md) : depend des donnees importees
- [Lire vos rapports](10-reading-reports.md) : ce que vous pouvez faire avec les
  donnees une fois importees
- Pour les DevOps : details sur les requetes de fraicheur des donnees et depannage, voir
  [Operations de base de donnees](14-database.md) et [Depannage](15-troubleshooting.md).

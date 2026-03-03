# Chapitre 4 : Analyser le gaspillage par dimension

*Public visé : acheteurs média, gestionnaires de campagnes*

Une fois que vous savez *combien* de gaspillage vous avez (grâce à
l'[entonnoir](03-qps-funnel.md)), ces trois vues vous indiquent *d'où* il
provient.

## Gaspillage géographique (`/qps/geo`)

Affiche la consommation de QPS et les performances par pays et ville.

![Répartition géographique du QPS par pays](images/screenshot-geo-qps.png)

**Ce qu'il faut rechercher :**
- Des pays avec un QPS élevé mais zéro victoire ou presque. Google vous envoie
  du trafic provenant de régions que vos acheteurs ne ciblent pas.
- Des villes avec une part de QPS disproportionnée mais de faibles dépenses,
  indiquant des zones géographiques de longue traîne qui ajoutent du volume
  mais aucune valeur.

**Que faire :**
- Ajoutez les zones géographiques sous-performantes à votre liste d'exclusion
  de préciblage. Voir [Configuration de préciblage](06-pretargeting.md).

**Contrôles :** Sélecteur de période (7/14/30 jours), filtre de siège.

## Gaspillage par éditeur (`/qps/publisher`)

Affiche les performances ventilées par domaine d'éditeur ou application.

![QPS par éditeur avec analyse du taux de victoire](images/screenshot-pub-qps.png)

**Ce qu'il faut rechercher :**
- Des domaines avec un volume d'enchères élevé mais zéro impression. Votre
  enchérisseur consacre de la puissance de calcul à de l'inventaire qui ne
  s'affiche jamais.
- Des applications ou sites avec des taux de victoire anormalement bas. Vous
  enchérissez mais perdez systématiquement, ce qui signifie que vous gaspillez
  du temps d'évaluation d'enchères.
- Des domaines de faible qualité connus.

**Que faire :**
- Bloquez des éditeurs spécifiques dans la liste d'exclusion de votre
  configuration de préciblage. L'éditeur de liste d'éditeurs de Cat-Scan rend
  cette opération plus simple que l'interface Authorized Buyers.

**Contrôles :** Sélecteur de période, filtre géographique, recherche par domaine.

## Gaspillage par format (`/qps/size`)

Affiche quels formats publicitaires reçoivent du trafic et si vous disposez de
créations correspondantes.

![Répartition du QPS par format](images/screenshot-size-qps.png)

**Ce qu'il faut rechercher :**
- Des formats avec un QPS élevé mais **aucune création correspondante**. Google
  envoie environ 400 formats publicitaires différents. Si vous diffusez des
  publicités display de taille fixe (pas HTML), la plupart de ces formats sont
  non pertinents. Chaque requête pour un format sans correspondance est du pur
  gaspillage.
- Des formats avec des créations sous-performantes. Demandez-vous si les
  éléments créatifs sont adaptés à ce format.

**Que faire :**
- Ajoutez les formats non pertinents à la liste des formats exclus de votre
  préciblage. C'est l'optimisation à plus fort impact pour les acheteurs display.

**Contrôles :** Sélecteur de période, filtre de siège, graphique de répartition
de la couverture.

## Combiner les dimensions

Les trois vues sont complémentaires. Un cycle d'optimisation type :

1. Vérifiez la **géographie** : excluez les pays dont vous n'avez pas besoin.
2. Vérifiez les **éditeurs** : bloquez les domaines qui gaspillent des enchères.
3. Vérifiez les **formats** : excluez les formats sans création correspondante.
4. Appliquez les modifications via la [Configuration de préciblage](06-pretargeting.md)
   avec aperçu en mode simulation.
5. Attendez un cycle de données (généralement un jour) et revérifiez l'entonnoir.

## En lien

- [Comprendre votre entonnoir QPS](03-qps-funnel.md) : le point de départ
- [Configuration de préciblage](06-pretargeting.md) : agir sur les constats de gaspillage
- [Lire vos rapports](10-reading-reports.md) : suivre l'impact des modifications

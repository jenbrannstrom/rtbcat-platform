# Chapitre 7 : L'optimiseur (BYOM)

*Public : acheteurs media, ingenieurs en optimisation*

L'optimiseur est le moteur d'optimisation automatisee de Cat-Scan. "BYOM" signifie Bring Your Own Model (Apportez Votre Propre Modele) : vous enregistrez un endpoint de scoring externe, et Cat-Scan l'utilise pour generer des propositions de modification de configuration.

## Comment ca fonctionne

```
  Score          Propose          Revue          Applique
────────────> ────────────> ────────────> ────────────>
Votre modele   Cat-Scan       Vous          Google AB
evalue         genere         (humain)      la config
les segments   des modifs     approuvez     est mise
               de config      ou rejetez    a jour
```

1. **Score** : Cat-Scan envoie les donnees de segment a votre endpoint de modele. Le modele renvoie un score pour chaque segment (geo, taille, editeur).
2. **Proposition** : A partir des scores, Cat-Scan genere des modifications specifiques de pretargeting (ex. : "exclure ces 5 zones geo", "ajouter ces 3 tailles").
3. **Revue** : Vous visualisez la proposition avec l'impact projete. Vous approuvez ou rejetez.
4. **Application** : Les propositions approuvees sont appliquees a la configuration de pretargeting cote Google. La modification est enregistree dans l'historique.

## Gestion des modeles

### Enregistrer un modele

Allez sur `/settings/system` et trouvez la section Optimiseur.

1. Cliquez sur **Enregistrer le modele**.
2. Remplissez : nom, type de modele, URL de l'endpoint (votre service de scoring).
3. L'endpoint doit accepter les requetes POST avec les donnees de segment et renvoyer
   les resultats scores.
4. Enregistrez.

### Valider l'endpoint

Avant d'activer, testez votre modele :

1. Cliquez sur **Valider l'endpoint** sur la fiche du modele.
2. Cat-Scan envoie un payload de test a votre endpoint.
3. Les resultats affichent : temps de reponse, validite du format de reponse, distribution des scores.
4. Corrigez les eventuels problemes avant d'activer.

### Activation et desactivation

- **Activer** : le modele devient le scoreur actif pour ce seat.
- **Desactiver** : le modele cesse d'etre utilise, mais sa configuration est
  conservee. Un seul modele peut etre actif par seat a la fois.

## Preselections de flux de travail

Lors de l'execution du scoring et de la proposition, vous choisissez une preselection :

| Preselection | Comportement | Quand l'utiliser |
|--------------|-------------|------------------|
| **Prudent** | Ne propose que des modifications a haute confiance et faible risque. Ameliorations plus modestes, moins de risque d'erreur. | Premiere utilisation de l'optimiseur, ou comptes conservateurs. |
| **Equilibre** | Seuil de confiance modere. Bon compromis entre impact et securite. | Choix par defaut pour la plupart des usages. |
| **Agressif** | Propose des modifications plus importantes avec un impact potentiel plus eleve. Plus de risque de sur-optimisation. | Utilisateurs experimentes qui surveillent quotidiennement et peuvent annuler rapidement. |

## Aspects economiques

L'optimiseur suit egalement les aspects economiques de l'optimisation :

- **CPM effectif** : ce que vous payez reellement pour mille impressions,
  en tenant compte du gaspillage.
- **Cout d'hebergement de reference** : le cout d'infrastructure de votre bidder, configure dans
  les parametres de l'optimiseur. Utilise pour calculer si les economies liees a la reduction de QPS
  compensent l'hebergement.
- **Resume d'efficacite** : ratio global de QPS utile par rapport au QPS total.

Configurez votre cout d'hebergement dans `/settings/system` > Configuration de l'optimiseur.

## Examiner les propositions

Chaque proposition affiche :
- **Scores des segments** ayant motive la recommandation
- **Modifications specifiques** des champs de pretargeting (ajouts, suppressions, mises a jour)
- **Impact projete** sur le QPS, le ratio de gaspillage et les depenses

Vous pouvez :
- **Approuver** : marque la proposition comme acceptee
- **Appliquer** : pousse les modifications approuvees vers Google
- **Rejeter** : ecarte la proposition
- **Verifier le statut d'application** : verifier que les modifications ont bien pris effet cote Google

## Voir aussi

- [Configuration du pretargeting](06-pretargeting.md) : les configurations que l'optimiseur
  modifie
- [Conversions et attribution](08-conversions.md) : les donnees de conversion alimentent
  la qualite du scoring
- [Lire vos rapports](10-reading-reports.md) : suivre l'impact de l'optimiseur

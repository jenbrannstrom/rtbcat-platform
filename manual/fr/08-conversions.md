# Chapitre 8 : Conversions et attribution

*Public : acheteurs media, responsables de campagne*

Le suivi des conversions permet a Cat-Scan de mesurer ce qui se passe apres une impression : l'utilisateur a-t-il effectue une action a forte valeur ? Ces donnees alimentent le scoring de l'optimiseur et vous aident a evaluer la performance reelle de vos campagnes.

## Sources de conversions

Cat-Scan prend en charge deux methodes d'integration :

### Pixel

Un pixel de suivi se declenche sur votre page de conversion (ex. : confirmation de commande).

- Endpoint : `/api/conversions/pixel`
- Parametres : `buyer_id`, `source_type=pixel`, `event_name`, `event_value`,
  `currency`, `event_ts`
- Aucune configuration cote serveur n'est necessaire en dehors du placement du pixel sur votre page.

### Webhook

Votre serveur envoie les evenements de conversion a l'endpoint webhook de Cat-Scan.

- Plus fiable que les pixels (pas de bloqueurs de publicite, pas de dependances cote client).
- Necessite une integration cote serveur.
- Prend en charge la verification de signature HMAC pour la securite.

## Securite des webhooks

Cat-Scan fournit une securite webhook multicouche :

| Fonctionnalite | Ce qu'elle fait |
|----------------|----------------|
| **Verification HMAC** | Chaque requete webhook est signee avec un secret partage. Cat-Scan rejette les requetes non signees ou mal signees. |
| **Limitation de debit** | Previent les abus en plafonnant les requetes par fenetre de temps. |
| **Surveillance de la fraicheur** | Alerte si les evenements webhook cessent d'arriver (detection de peremption). |

Configurez la securite des webhooks dans `/settings/system` > Sante des conversions.

## Verification de la disponibilite

Avant de vous fier aux donnees de conversion, verifiez la disponibilite :

1. Allez sur `/settings/system` ou la checklist de configuration.
2. Verifiez la **Disponibilite des conversions** : indique si une source est connectee et
   delivre des evenements dans la fenetre de fraicheur attendue.
3. Verifiez les **Statistiques d'ingestion** : nombre d'evenements par type de source et par periode.

## Sante des conversions

Le panneau Sante des conversions affiche :

- Statut d'ingestion (reception des evenements ou non)
- Statut d'agregation (evenements en cours de traitement en metriques)
- Horodatage du dernier evenement
- Nombre d'erreurs le cas echeant

## Voir aussi

- [L'optimiseur](07-optimizer.md) : les donnees de conversion ameliorent la precision du scoring
- [Import de donnees](09-data-import.md) : un autre chemin d'entree de donnees
- Pour les DevOps : configuration et depannage de l'endpoint webhook, voir
  [Integrations](17-integrations.md).

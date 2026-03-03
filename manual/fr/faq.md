# Foire aux questions

Les questions sont étiquetées par audience : **[Acheteur]** pour les acheteurs
média et responsables de campagnes, **[DevOps]** pour les ingénieurs plateforme,
**[Les deux]** pour les questions partagées.

---

### [Acheteur] Pourquoi mon pourcentage de couverture est-il inférieur à 100 % ?

La couverture mesure combien de cellules date x type de rapport contiennent des
données par rapport au nombre attendu. Raisons courantes des écarts :

- **Google n'a pas envoyé de rapport** pour cette date (jour férié, retard
  d'export).
- **L'import Gmail a raté l'e-mail** (vérifiez le statut Gmail).
- **Un type de rapport spécifique n'est pas disponible** pour votre siège (par
  exemple, les données de qualité peuvent ne pas exister pour tous les
  acheteurs).

Consultez la grille de fraîcheur des données sur `/import` pour voir exactement
quelles cellules sont manquantes. Voir [Import de données](09-data-import.md).

### [Acheteur] Quelle est la différence entre « gaspillage » et « faible taux de victoire » ?

**Gaspillage** = requêtes d'enchères que votre bidder a *rejetées* sans
enchérir. C'est du QPS que vous avez payé mais que vous n'avez pas pu utiliser
du tout. Corrigez-le avec le prétargeting.

**Faible taux de victoire** = requêtes d'enchères sur lesquelles votre bidder a
*enchéri* mais a perdu l'enchère. Cela signifie que vos enchères ne sont pas
assez compétitives. Corrigez-le avec la stratégie d'enchères, pas le
prétargeting.

Les deux apparaissent dans l'entonnoir mais nécessitent des actions différentes.
Voir [Comprendre votre entonnoir QPS](03-qps-funnel.md).

### [Acheteur] Puis-je annuler une modification de prétargeting ?

Oui. Allez sur `/history`, trouvez la modification, cliquez sur « Aperçu du
retour en arrière » pour voir ce qui sera restauré, puis confirmez. Le retour en
arrière lui-même est enregistré. Voir
[Configuration du prétargeting](06-pretargeting.md).

### [Acheteur] À quelle fréquence dois-je réimporter les données ?

Quotidiennement. L'auto-import Gmail gère cela automatiquement. Si vous importez
manuellement, faites-le une fois par jour après l'arrivée des rapports. Des
données obsolètes entraînent des décisions obsolètes.

### [Acheteur] Que modifie concrètement l'optimiseur ?

L'optimiseur propose des modifications à vos configurations de prétargeting :
ajout ou suppression de zones géographiques, de formats, d'éditeurs, etc. Il
n'applique jamais les modifications automatiquement. Vous examinez et approuvez
chaque proposition. Voir [L'optimiseur](07-optimizer.md).

---

### [DevOps] Pourquoi le gate de santé runtime strict a-t-il échoué ?

Consultez les logs du workflow : `gh run view <id> --log-failed`. Recherchez
FAIL vs. BLOCKED :

- **FAIL** = quelque chose a cassé. Le timeout de fraîcheur des données et les
  problèmes de SET statement_timeout sont des causes fréquentes. Voir
  [Dépannage](15-troubleshooting.md).
- **BLOCKED** = une dépendance est manquante, pas nécessairement un bug de
  code. Exemples : pas de données de qualité pour cet acheteur, la proposition
  n'a pas de billing_id. Comparez avec les exécutions précédentes pour
  distinguer les régressions des lacunes préexistantes.

### [DevOps] Pourquoi l'endpoint de fraîcheur des données est-il lent ?

La requête parcourt `rtb_daily` (~84M de lignes) et `rtb_bidstream` (~21M de
lignes). Si le plan de requête dégénère en parcours séquentiel au lieu
d'utiliser les index `(buyer_account_id, metric_date DESC)`, cela prendra des
minutes.

Correction : assurez-vous que les requêtes utilisent le pattern
`generate_series + EXISTS` (14 consultations d'index au lieu d'un parcours
complet de la table). Voir [Opérations de base de données](14-database.md).

### [DevOps] Comment vérifier quelle version est déployée ?

```bash
curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'
```

Cela retourne le SHA git et le tag de l'image. Comparez avec votre historique de
commits.

### [DevOps] Comment déployer un correctif ?

1. Poussez sur `unified-platform`
2. Attendez que `build-and-push.yml` réussisse
3. Déclenchez `deploy.yml` via `gh workflow run` avec `confirm=DEPLOY`
4. Vérifiez avec `/api/health`

Voir [Déploiement](12-deployment.md) pour la procédure complète.

### [DevOps] Les utilisateurs sont bloqués dans une boucle de connexion. Que faire ?

Vérifiez Cloud SQL Proxy : `sudo docker ps | grep cloudsql`. S'il est arrêté,
redémarrez-le, attendez 10 secondes, puis redémarrez le conteneur API. Voir
[Dépannage](15-troubleshooting.md) pour la procédure complète.

---

### [Les deux] D'où proviennent les données de Cat-Scan ?

Des exports CSV de Google Authorized Buyers. Il n'y a pas d'API de reporting.
Les données arrivent soit par import CSV manuel, soit par ingestion automatique
via Gmail. Voir [Import de données](09-data-import.md).

### [Les deux] Est-il sûr de réimporter le même CSV ?

Oui. Chaque ligne est hachée et dédoublonnée. La réimportation ne compte jamais
en double.

### [Les deux] Quelles langues l'interface supporte-t-elle ?

Anglais, néerlandais et chinois (simplifié). Le sélecteur de langue se trouve
dans la barre latérale.

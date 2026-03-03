# Chapitre 1 : Se connecter

*Public visé : tout le monde*

## Méthodes d'authentification

Cat-Scan prend en charge trois méthodes de connexion :

| Méthode | Fonctionnement | Quand l'utiliser |
|---------|----------------|------------------|
| **Google OAuth** | Cliquez sur « Se connecter avec Google », ce qui vous redirige via OAuth2 Proxy | La plupart des utilisateurs. Utilise votre compte Google Workspace. |
| **Authing (OIDC)** | Cliquez sur « Se connecter avec Authing », ce qui vous redirige vers le fournisseur OIDC | Organisations utilisant Authing comme fournisseur d'identité. |
| **E-mail et mot de passe** | Saisissez vos identifiants directement sur la page de connexion | Comptes locaux créés par un administrateur. |

## Première connexion

1. Accédez à `https://scan.rtb.cat` (ou l'URL de votre déploiement).
2. La page de connexion s'affiche avec les options d'authentification disponibles.
3. Choisissez votre méthode et authentifiez-vous.
4. Lors de la première connexion, le système crée automatiquement votre
   enregistrement utilisateur (pour les méthodes OAuth). Votre administrateur
   devra peut-être vous accorder l'accès à des sièges acheteurs spécifiques.

## Le sélecteur de siège

Après connexion, vous verrez la barre latérale avec un **sélecteur de siège**
en haut. Si votre compte a accès à plusieurs sièges acheteurs, utilisez le
menu déroulant pour basculer entre eux. Toutes les données de chaque page sont
limitées au siège sélectionné.

- **Siège unique** : le sélecteur affiche directement le nom et l'identifiant
  de votre siège.
- **Sièges multiples** : un menu déroulant vous permet de basculer. Chaque
  entrée affiche le nom d'affichage de l'acheteur, le `buyer_account_id` et un
  nombre de créations.
- **Bouton « Sync All »** : actualise les créations, les points d'accès et les
  configurations de préciblage depuis l'API de Google pour le siège sélectionné.

## En cas d'échec de connexion

| Symptôme | Cause probable | Action à entreprendre |
|----------|----------------|----------------------|
| Boucle de redirection (la page ne cesse de se recharger) | Base de données inaccessible, l'authentification échoue silencieusement | Vérifiez le conteneur Cloud SQL Proxy. Voir [Dépannage](15-troubleshooting.md). |
| « Server unavailable » (502/503/504) | Le conteneur API ou nginx est arrêté | Contactez votre équipe DevOps. Voir [Surveillance de la santé](13-health-monitoring.md). |
| « Authentication required » | Session expirée ou cookie supprimé | Reconnectez-vous. |
| « You don't have access to this buyer account » | Permissions non accordées pour ce siège | Demandez à votre administrateur. Voir [Administration des utilisateurs](16-user-admin.md). |

## Étapes suivantes

- [Naviguer dans le tableau de bord](02-navigating-the-dashboard.md)

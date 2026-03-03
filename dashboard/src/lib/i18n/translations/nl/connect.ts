import type { PartialTranslations } from '../../types';

const value: PartialTranslations['connect'] = {
  title: 'Koppelen',
  connectAccount: 'Account koppelen',
  serviceAccount: 'Service-account',
  instructions: 'Volg de instructies om je account te koppelen',
  setupComplete: 'Setup voltooid!',
  setUpCatScan: 'Cat-Scan instellen',
  accountConnectedReady:
    'Je account is gekoppeld en klaar om te analyseren',
  stepOf: 'Stap {current} van {total}: {title}',
  uploadCredentials: 'Credentials uploaden',
  syncCreatives: 'Creatives synchroniseren',
  readyToGo: 'Klaar om te starten',
  optionalInstallFfmpeg: 'Optioneel: ffmpeg installeren',
  ffmpegRequired:
    'ffmpeg is vereist voor het genereren van videominiaturen. Zonder ffmpeg tonen video-creatives placeholder-iconen in plaats van previewframes.',
  googleCredentials: 'Google-credentials',
  connected: 'Verbonden',
  serviceAccountConfigured: 'Service-account geconfigureerd',
  change: 'Wijzigen',
  uploading: 'Uploaden...',
  dropFileHere: 'Bestand hier neerzetten',
  uploadServiceAccountJson: 'Service-account JSON uploaden',
  dragAndDropOrClick: 'Sleep en zet neer of klik om te bladeren',
  howToGetServiceAccountKey: 'Hoe krijg je een service-account sleutel',
  goToGcpServiceAccounts: 'Ga naar de GCP Service Accounts-pagina',
  selectYourProject: 'Selecteer je project (of maak er een)',
  clickCreateServiceAccount: 'Klik op + Create Service Account',
  nameIt: 'Geef het een naam (bijv. "catscan-service-account")',
  clickCreateContinue:
    'Klik Create and Continue, sla rollen over, klik Done',
  clickOnServiceAccountEmail:
    'Klik op het e-mailadres van het nieuwe service-account',
  goToKeysTab: 'Ga naar tab Keys -> Add Key -> Create new key',
  selectJsonClick: 'Selecteer JSON en klik Create',
  uploadDownloadedFile: 'Upload het gedownloade bestand hierboven',
  importantAddServiceAccount:
    'Belangrijk: voeg ook het service-account e-mailadres toe als gebruiker in je Authorized Buyers-account met RTB-toegang.',
  noBuyerSeatsFound: 'Geen buyer seats gevonden',
  makeSureServiceAccountHasAccess:
    'Controleer of het service-account toegang heeft tot je Authorized Buyers-account',
  completeStep1: 'Voltooi stap 1 om je creatives te synchroniseren',
  creatives: 'creatives',
  lastSynced: 'Laatst gesynchroniseerd',
  syncing: 'Synchroniseren...',
  syncNow: 'Nu synchroniseren',
  readyToAnalyze: 'Klaar om te analyseren',
  accountSetUpCreativesSynced:
    'Je account is ingesteld en creatives zijn gesynchroniseerd. Je kunt nu:',
  viewCreativeStatus: 'Creative-status en goedkeuringen bekijken',
  importRtbPerformance: 'RTB-performancedata importeren',
  analyzeQpsWaste: 'QPS-verspilling en optimalisatiemogelijkheden analyseren',
  goToDashboard: 'Ga naar Dashboard',
  completeSteps1And2: 'Voltooi stap 1 en 2 om verder te gaan',
  discoveredSeats: '{count} buyer seat(s) ontdekt',
  failedToDiscoverSeats: 'Seats ontdekken mislukt',
  connectedAs: 'Verbonden als {email}',
  uploadFailed: 'Upload mislukt',
  syncedCreatives: '{count} creatives gesynchroniseerd',
  syncFailed: 'Synchronisatie mislukt',
  pleaseSelectJsonFile: 'Selecteer een JSON-bestand',
  invalidJsonFile:
    'Ongeldig JSON-bestand. Upload een geldige service-account sleutel.',
  invalidServiceAccountFormat:
    'Ongeldig service-account formaat. Verplichte velden ontbreken.',
  invalidCredentialType:
    'Ongeldig credentialtype: "{type}". Verwacht "service_account".',
  account: 'Account',
};

export default value;

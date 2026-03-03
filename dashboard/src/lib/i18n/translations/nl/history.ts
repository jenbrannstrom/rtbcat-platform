import type { PartialTranslations } from '../../types';

const value: PartialTranslations['history'] = {
  title: 'Wijzigingsgeschiedenis',
  changeHistory: 'Wijzigingsgeschiedenis',
  trackAndRollback:
    'Volg en rol wijzigingen in pretargeting-configuratie terug',
  noChanges: 'Geen wijzigingen geregistreerd',
  noChangesFound: 'Geen wijzigingen gevonden',
  tryAdjustingFilters: 'Probeer je filters aan te passen.',
  changesWillAppear: 'Configuratiewijzigingen verschijnen hier.',
  change: 'Wijziging',
  user: 'Gebruiker',
  timestamp: 'Tijdstip',
  export: 'Exporteren',
  filters: 'Filters:',
  period: 'Periode:',
  lastDays: 'Laatste {count} dagen',
  config: 'Config:',
  allConfigs: 'Alle configs',
  type: 'Type:',
  allTypes: 'Alle types',
  clearFilters: 'Filters wissen',
  showingChanges:
    'Toont {count} wijziging van de laatste {days} dagen',
  showingChangesPlural:
    'Toont {count} wijzigingen van de laatste {days} dagen',
  rollback: 'Rollback',
  rollbackChange: 'Wijziging terugrollen',
  aboutToRollback: 'Je staat op het punt terug te rollen:',
  field: 'Veld:',
  current: 'Huidig:',
  restoreTo: 'Herstellen naar:',
  empty: '(leeg)',
  rollbackWarning:
    'Dit herstelt de vorige instelling. Je moet de wijziging nog handmatig toepassen in Google Authorized Buyers.',
  noSnapshotAvailableForChange:
    'Geen snapshot beschikbaar voor deze wijziging. Rollback vereist een auto-snapshot die voor de push is gemaakt. Oudere wijzigingen hebben mogelijk geen snapshots.',
  previewingRollback: 'Rollback-preview laden...',
  failedToPreviewRollback: 'Rollback-preview laden mislukt',
  noDifferencesFoundBetweenCurrentAndSnapshot:
    'Geen verschillen gevonden tussen huidige config en snapshot. De config kan sindsdien al zijn gewijzigd.',
  changesWillBeReversedOnGoogle:
    'Deze wijzigingen worden in Google teruggedraaid:',
  rollbackPushesToGoogleImmediately:
    'Dit pusht direct naar Google. Een nieuwe "ROLLBACK"-entry wordt in de geschiedenis geregistreerd.',
  reasonForRollback: 'Reden voor rollback',
  whyRollingBack: 'Waarom rol je deze wijziging terug?',
  cancel: 'Annuleren',
  rollbackNow: 'Nu terugrollen',
  on: 'op',
  value: 'Waarde:',
  manual: 'handmatig',
  daysAgo: 'd geleden',
  hoursAgo: 'u geleden',
  minutesAgo: 'm geleden',
  justNow: 'zojuist',
  rollbackFailed: 'Rollback mislukt',
};

export default value;

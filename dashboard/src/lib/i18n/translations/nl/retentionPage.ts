import type { PartialTranslations } from '../../types';

const value: PartialTranslations['retentionPage'] = {
  title: 'Dataretentie-instellingen',
  subtitle: 'Configureer hoe lang performancedata wordt bewaard.',
  saveSuccess: 'Retentie-instellingen succesvol opgeslagen.',
  saveFailed: 'Retentie-instellingen opslaan mislukt.',
  runCompleted:
    'Retentietaak voltooid: {aggregatedRows} rijen geaggregeerd, {deletedRawRows} ruwe rijen verwijderd.',
  runFailed: 'Retentietaak uitvoeren mislukt.',
  currentStorage: 'Huidige opslag',
  rawPerformanceRows: 'Ruwe performance-rijen',
  dailySummaryRows: 'Dagelijkse samenvattingsrijen',
  dateRangeSpan: '{start} tot {end}',
  keepDetailedDataFor: 'Gedetailleerde data bewaren voor:',
  keepDailySummariesFor: 'Dagelijkse samenvattingen bewaren voor:',
  autoAggregateAfter: 'Automatisch aggregeren na:',
  option7Days: '7 dagen',
  option14Days: '14 dagen',
  option30Days: '30 dagen',
  option30DaysRecommended: '30 dagen (aanbevolen)',
  option60Days: '60 dagen',
  option90DaysRecommended: '90 dagen (aanbevolen)',
  option180Days: '180 dagen',
  option1Year: '1 jaar',
  option6Months: '6 maanden',
  option1YearRecommended: '1 jaar (aanbevolen)',
  option2Years: '2 jaar',
  optionForever: 'Altijd',
  detailedDataHelp:
    'Gedetailleerde data toont performance per app, land en creative. Na deze periode wordt data geaggregeerd naar dagelijkse samenvattingen.',
  summaryDataHelp:
    'Samenvattingen tonen dagelijkse totalen per creative. Goed voor trendanalyse.',
  autoAggregateHelp:
    'Maak samenvattingen voor data ouder dan deze grens voordat die wordt verwijderd.',
  warningIrreversible:
    'Het verkorten van retentie verwijdert oude data permanent. Dit kan niet ongedaan worden gemaakt.',
  howItWorks: 'Hoe het werkt:',
  howItWorksItem1: 'Gedetailleerde rijen worden geaggregeerd naar dagelijkse samenvattingen',
  howItWorksItem2:
    'Samenvattingen behouden totale metrics per creative/dag',
  howItWorksItem3:
    'Na aggregatie worden gedetailleerde rijen verwijderd',
  howItWorksItem4:
    'Dit vermindert de opslagvereisten aanzienlijk',
  saving: 'Opslaan...',
  saveSettings: 'Instellingen opslaan',
  running: 'Bezig...',
  runRetentionJobNow: 'Retentietaak nu uitvoeren',
};

export default value;

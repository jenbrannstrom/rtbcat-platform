// Supported languages
export type Language = 'en';

// Translation structure - all strings organized by namespace
export interface Translations {
  common: {
    loading: string;
    error: string;
    save: string;
    cancel: string;
    delete: string;
    edit: string;
    create: string;
    search: string;
    filter: string;
    refresh: string;
    sync: string;
    syncing: string;
    synced: string;
    failed: string;
    copy: string;
    copied: string;
    close: string;
    back: string;
    next: string;
    previous: string;
    submit: string;
    yes: string;
    no: string;
    all: string;
    none: string;
    select: string;
    selected: string;
    actions: string;
    status: string;
    name: string;
    description: string;
    date: string;
    time: string;
    never: string;
    version: string;
  };

  relativeTime: {
    justNow: string;
    minutesAgo: string;
    hoursAgo: string;
    daysAgo: string;
  };

  navigation: {
    wasteOptimizer: string;
    creatives: string;
    campaigns: string;
    changeHistory: string;
    import: string;
    setup: string;
    admin: string;
    docs: string;
    logout: string;
    collapse: string;
    expand: string;
    settings: string;
  };

  sidebar: {
    noSeatsConnected: string;
    goToSettingsToConnect: string;
    allSeats: string;
    creatives: string;
    syncCreatives: string;
    buyer: string;
  };

  auth: {
    catScan: string;
    creativeIntelligenceDashboard: string;
    signInToYourAccount: string;
    email: string;
    emailAddress: string;
    password: string;
    enterYourPassword: string;
    signIn: string;
    signingIn: string;
    loginFailed: string;
    cannotConnectToServer: string;
    contactAdministrator: string;
  };

  dashboard: {
    title: string;
    subtitle: string;
    rtbFunnel: string;
    rtbFunnelDescription: string;
    reachedYourBidder: string;
    winRate: string;
    impressionsWon: string;
    yourEfficiency: string;
    thisIsHealthy: string;
    roomToImprove: string;
    ofReachedTraffic: string;
    qps: string;
    ips: string;
    reached: string;
    impressions: string;
    win: string;
    needRtbReport: string;
    period: string;
    days: string;
  };

  publishers: {
    title: string;
    subtitle: string;
    publishers: string;
    highWinRate: string;
    moderateWinRate: string;
    lowWinRate: string;
    blockedByPretargeting: string;
    impr: string;
    publisherDataNotAvailable: string;
    importPublisherReport: string;
  };

  sizes: {
    title: string;
    subtitle: string;
    coverage: string;
    requests: string;
    trafficDistribution: string;
    creatives: string;
    noCreative: string;
    ads: string;
    noCreativesForSizes: string;
    receivingTrafficNoCreatives: string;
    copySizes: string;
    noSizeDataAvailable: string;
    importCsvWithSize: string;
    util: string;
  };

  geo: {
    title: string;
    subtitle: string;
    winRatesByCountry: string;
    avgWinRate: string;
    countries: string;
    reached: string;
    bids: string;
    wins: string;
    highWinRate: string;
    lowerWinRate: string;
    optimizeThese: string;
    geoDataNotAvailable: string;
    importCreativeBiddingReport: string;
    country: string;
  };

  pretargeting: {
    configs: string;
    active: string;
    syncFromGoogle: string;
    noPretargetingConfigs: string;
    clickSyncToFetch: string;
    waste: string;
    suspended: string;
  };

  import: {
    title: string;
    upload: string;
    preview: string;
    importing: string;
    success: string;
    dragAndDrop: string;
    orClickToUpload: string;
    failedToParseCSV: string;
    importFailed: string;
    columnMapping: string;
    startImport: string;
    goToImport: string;
  };

  campaigns: {
    title: string;
    newCampaign: string;
    dropToCreateCampaign: string;
    releaseToCreate: string;
    grid: string;
    list: string;
    high: string;
    medium: string;
    low: string;
    noData: string;
  };

  creatives: {
    title: string;
    defaultOrder: string;
    spendYesterday: string;
    spend7Days: string;
    spend30Days: string;
    spendAllTime: string;
    video: string;
    display: string;
    native: string;
    generatingThumbnails: string;
  };

  admin: {
    dashboard: string;
    manageUsers: string;
    totalUsers: string;
    activeUsers: string;
    adminUsers: string;
    userManagement: string;
    systemSettings: string;
    systemConfiguration: string;
    apiStatus: string;
    systemStatus: string;
    python: string;
    nodejs: string;
    configured: string;
    retention: string;
    unlimited: string;
    auditLog: string;
    role: string;
    permissions: string;
    lastLogin: string;
    createUser: string;
    editUser: string;
    deleteUser: string;
  };

  settings: {
    title: string;
    systemConfiguration: string;
    apiStatus: string;
    systemStatus: string;
    seats: string;
    seatsManagement: string;
    connectNewSeat: string;
    retentionSettings: string;
    dataRetention: string;
    daysRetention: string;
  };

  errors: {
    somethingWentWrong: string;
    pageNotFound: string;
    unauthorized: string;
    forbidden: string;
    serverError: string;
    networkError: string;
    tryAgain: string;
    goBack: string;
    goHome: string;
  };

  reports: {
    reportName: string;
    dimensions: string;
    metrics: string;
    schedule: string;
    daily: string;
    yesterday: string;
    day: string;
    billingId: string;
    creativeId: string;
    creativeSize: string;
    creativeFormat: string;
    reachedQueries: string;
    bidRequests: string;
    publisherId: string;
    publisherName: string;
    bidsInAuction: string;
  };

  history: {
    title: string;
    changeHistory: string;
    noChanges: string;
    change: string;
    user: string;
    timestamp: string;
  };

  connect: {
    title: string;
    connectAccount: string;
    serviceAccount: string;
    instructions: string;
  };

  wasteAnalysis: {
    title: string;
    subtitle: string;
  };

  setup: {
    title: string;
    gettingStarted: string;
    configurationGuide: string;
    step: string;
  };

  language: {
    title: string;
    select: string;
    english: string;
  };
}

// Helper type for nested key access
export type TranslationKey = keyof Translations;

/**
 * React Query 的 query key 集中定義。
 *
 * 各領域一律提供 `root`（供 invalidateQueries 以 prefix 失效整個資料域）
 * 與具體的 key 建構函式。過去這些 key 以字面量散在各 hook，
 * invalidate 端與 query 端必須靠人工比對字串才能對上，
 * 是「操作成功但畫面沒更新」這類問題的主要來源。
 *
 * MSA 領域的 key 另見 useMsaEquipment.ts 的 `msaKeys`
 * 與 useMsaStudies.ts 的 `msaStudyKeys`。
 */

/** 主鍵型別；查詢未啟用時常為 null/undefined，key 仍需可建構。 */
type Id = number | string | null | undefined;

// ---------- 出貨檢驗 ----------
export const shippingKeys = {
    root: ['shippingList'] as const,
    list: (params: unknown) => ['shippingList', params] as const,
    detailRoot: ['shippingDetail'] as const,
    detail: (id: Id) => ['shippingDetail', id] as const,
    statsRoot: ['shippingStats'] as const,
    stats: (params: unknown) => ['shippingStats', params] as const,
    measurementsRoot: ['shipping-measurements'] as const,
    measurements: (shippingId: Id) => ['shipping-measurements', shippingId] as const,
    toleranceMap: (combos: unknown) => ['shippingToleranceMap', combos] as const,
    vendors: ['vendors'] as const,
};

// ---------- 巡檢 ----------
export const patrolKeys = {
    root: ['patrolList'] as const,
    list: (params: unknown) => ['patrolList', params] as const,
    detailRoot: ['patrolDetail'] as const,
    detail: (id: Id) => ['patrolDetail', id] as const,
    statsRoot: ['patrolStats'] as const,
    stats: (params: unknown) => ['patrolStats', params] as const,
    detailsRoot: ['patrol-details'] as const,
    details: (mainId: Id) => ['patrol-details', mainId] as const,
    liveLimits: (params: unknown) => ['patrolLiveLimits', params] as const,
    options: ['patrolOptions'] as const,
};

// ---------- NCMR ----------
export const ncmrKeys = {
    root: ['ncmrList'] as const,
    list: (params: unknown) => ['ncmrList', params] as const,
    detailRoot: ['ncmrDetail'] as const,
    detail: (id: Id) => ['ncmrDetail', id] as const,
    dispositionsRoot: ['ncmrDispositions'] as const,
    dispositions: (ncmrId: Id) => ['ncmrDispositions', ncmrId] as const,
    reworks: (ncmrId: Id) => ['ncmrReworks', ncmrId] as const,
    riskReleases: ['riskReleases'] as const,
};

// ---------- CAPA / 8D ----------
export const capaKeys = {
    root: ['capaList'] as const,
    list: (params: unknown) => ['capaList', params] as const,
    detailRoot: ['capaDetail'] as const,
    detail: (id: Id) => ['capaDetail', id] as const,
    closeGateRoot: ['capaCloseGate'] as const,
    closeGate: (capaId: Id) => ['capaCloseGate', capaId] as const,
    d6GateRoot: ['d6Gate'] as const,
    d6Gate: (capaId: Id) => ['d6Gate', capaId] as const,
    overdue: ['overdueCapas'] as const,
};

// ---------- 重工 ----------
export const reworkKeys = {
    root: ['rework'] as const,
    applicationsRoot: ['rework', 'applications'] as const,
    applications: (params: unknown) => ['rework', 'applications', params] as const,
    statistics: ['rework', 'statistics'] as const,
    application: (id: Id) => ['reworkApplication', id] as const,
    executions: (id: Id) => ['reworkExecutions', id] as const,
    inspections: (id: Id) => ['reworkInspections', id] as const,
    costs: (id: Id) => ['reworkCosts', id] as const,
};

// ---------- 客訴 ----------
export const complaintKeys = {
    root: ['complaintList'] as const,
    list: (params: unknown) => ['complaintList', params] as const,
    detailRoot: ['complaintDetail'] as const,
    detail: (id: Id) => ['complaintDetail', id] as const,
    statsRoot: ['complaintStats'] as const,
    stats: (kind: 'customer' | 'month' | 'product' | 'warranty', params: unknown) =>
        ['complaintStats', kind, params] as const,
    overdue: ['overdueComplaints'] as const,
    recentRepeats: (days: number) => ['recentRepeats', days] as const,
};

// ---------- 廠商公差 ----------
export const toleranceKeys = {
    root: ['toleranceList'] as const,
    list: (params: unknown) => ['toleranceList', params] as const,
    detailRoot: ['toleranceDetail'] as const,
    detail: (id: Id) => ['toleranceDetail', id] as const,
    options: ['toleranceOptions'] as const,
};

// ---------- 擠壓公差 ----------
export const extrusionToleranceKeys = {
    root: ['extrusionToleranceList'] as const,
    list: (params: unknown) => ['extrusionToleranceList', params] as const,
    detailRoot: ['extrusionToleranceDetail'] as const,
    detail: (id: Id) => ['extrusionToleranceDetail', id] as const,
    options: ['extrusionToleranceOptions'] as const,
    check: (material: string, spec: string, vendorId: Id) =>
        ['extrusionToleranceCheck', material, spec, vendorId] as const,
};

// ---------- SPC ----------
export const spcKeys = {
    studiesRoot: ['spcStudies'] as const,
    studies: (filter: unknown) => ['spcStudies', filter] as const,
    studyRoot: ['spcStudy'] as const,
    study: (studyId: Id) => ['spcStudy', studyId] as const,
    historyRoot: ['spcStudyHistory'] as const,
    history: (studyId: Id, page?: number, perPage?: number) => (
        page === undefined
            ? (['spcStudyHistory', studyId] as const)
            : (['spcStudyHistory', studyId, page, perPage] as const)
    ),
    assignees: ['spcAssignees'] as const,
};

// ---------- 機械性質檢驗 ----------
export const mechanicalKeys = {
    root: ['mechanical-tests'] as const,
    list: (params: unknown) => ['mechanical-tests', params] as const,
    detail: (testId: Id) => ['mechanical-test', testId] as const,
    options: (vendorId: Id) => ['mechanical-options', vendorId] as const,
    spec: (material: string, size: string, vendorId: Id) =>
        ['mechanical-spec', material, size, vendorId] as const,
    stats: (params: unknown) => ['mechanical-stats', params] as const,
};

// ---------- 任務 ----------
export const taskKeys = {
    root: ['taskList'] as const,
    list: (params: unknown) => ['taskList', params] as const,
    myTasks: ['myTasks'] as const,
    bySourceRoot: ['tasks'] as const,
    bySource: (sourceType: string, sourceId: Id) =>
        ['tasks', sourceType, sourceId] as const,
    closeGate: (sourceType: string, sourceId: Id) =>
        ['closeGate', sourceType, sourceId] as const,
};

// ---------- 附件 ----------
export const attachmentKeys = {
    root: ['attachments'] as const,
    list: (entityType: string, entityId: Id, dStep?: string) => (
        dStep === undefined
            ? (['attachments', entityType, entityId] as const)
            : (['attachments', entityType, entityId, dStep] as const)
    ),
};

// ---------- 儀表板 ----------
export const dashboardKeys = {
    stats: (period: unknown, customDateRange: unknown) =>
        ['dashboardStats', period, customDateRange] as const,
    trends: ['dashboardTrends'] as const,
    todos: ['dashboardTodos'] as const,
};

// ---------- 品質分析 ----------
export const qualityAnalyticsKeys = {
    root: ['qualityAnalytics'] as const,
    defectTrends: (source: string, params: unknown) =>
        ['qualityAnalytics', 'defectTrends', source, params] as const,
    pareto: (source: string, params: unknown) =>
        ['qualityAnalytics', 'pareto', source, params] as const,
    repeatIssues: (params: unknown) => ['qualityAnalytics', 'repeatIssues', params] as const,
    vendorRanking: (period: unknown) => ['qualityAnalytics', 'vendorRanking', period] as const,
    capaAging: ['qualityAnalytics', 'capaAging'] as const,
};

// ---------- 廠商績效 ----------
export const vendorPerformanceKeys = {
    root: ['vendorPerformance'] as const,
    byPeriod: (period: unknown) => ['vendorPerformance', period] as const,
    historyRoot: ['vendorPerformanceHistory'] as const,
    history: (vendorId: Id, months: number) =>
        ['vendorPerformanceHistory', vendorId, months] as const,
};

// ---------- 共用主檔 ----------
export const masterDataKeys = {
    vendors: ['vendors'] as const,
    inspectors: (group?: string) => ['inspectors', group ?? 'all'] as const,
    roles: ['roles'] as const,
};

import type { ActiveDataPoint } from 'chart.js';

const HIDDEN_SIGMA_LEGEND_LABELS = new Set(['+1σ', '-1σ', '+2σ', '-2σ']);

export const shouldShowControlLegendLabel = (label: string) =>
    !HIDDEN_SIGMA_LEGEND_LABELS.has(label);

export const getClickedPointId = (ids: unknown[], elements: Pick<ActiveDataPoint, 'index'>[]) => {
    if (elements.length === 0 || ids.length === 0) return null;
    const id = ids[elements[0].index];
    return id == null ? null : Number(id);
};

export const setChartPointCursor = (event: unknown, elements: Pick<ActiveDataPoint, 'index'>[]) => {
    const nativeEvent = (event as { native?: { target?: HTMLElement } })?.native;
    if (nativeEvent?.target) {
        nativeEvent.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
    }
};

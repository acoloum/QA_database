import type { ReworkCostDetail } from '../../types';

export const getReworkStatusBadge = (status: string) => {
  switch (status) {
    case '已完成': return 'bg-info text-dark';
    case '已核准': return 'bg-success';
    case '已拒絕': return 'bg-danger';
    case '執行中': return 'bg-primary';
    default: return 'bg-warning text-dark';
  }
};

export const parseReworkDetailCost = (value: unknown): number => {
  if (value == null || String(value).trim() === '') return 0;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

export const formatReworkCurrency = (value: unknown): string =>
  `$${parseReworkDetailCost(value).toFixed(2)}`;

export const calculateReworkCostTotal = (costs: ReworkCostDetail[]): number =>
  costs.reduce((sum, cost) => sum + parseReworkDetailCost(cost.總成本), 0);

import type { MsaStudy, MsaStudyStatus } from '../../types/msa';

/**
 * 預設排序刻意不是「最近更新」：待核准擋住流程、逾期代表結論已失效，
 * 這兩類必須先被看到。
 */
const STATUS_RANK: Record<MsaStudyStatus, number> = {
  submitted: 0,
  rejected: 1,
  collecting: 2,
  ready_for_analysis: 2,
  ready: 3,
  analyzed: 3,
  draft: 4,
  approved: 5,
  voided: 6,
  superseded: 6,
};

const today = () => new Date().toISOString().slice(0, 10);

export const isOverdue = (study: MsaStudy) =>
  study.next_due_date != null && study.next_due_date < today();

export const sortStudies = (studies: MsaStudy[]): MsaStudy[] =>
  [...studies].sort((left, right) => {
    if (left.status === 'submitted' || right.status === 'submitted') {
      const bySubmitted =
        (left.status === 'submitted' ? 0 : 1)
        - (right.status === 'submitted' ? 0 : 1);
      if (bySubmitted !== 0) return bySubmitted;
    }
    const byOverdue = (isOverdue(left) ? 0 : 1) - (isOverdue(right) ? 0 : 1);
    if (byOverdue !== 0) return byOverdue;
    const byStatus = STATUS_RANK[left.status] - STATUS_RANK[right.status];
    if (byStatus !== 0) return byStatus;
    return right.updated_at.localeCompare(left.updated_at);
  });

import { Link } from 'react-router';

import { SEVERITY_META, type MsaSeverity } from './msaRiskMeta';

/**
 * 工作類別決定佇列優先序：設備阻擋讓研究完全無法放行，排最前；
 * 待核准是流程瓶頸；再研究與進行中研究屬後續追蹤。
 */
export type MsaWorkCategory =
  | 'equipment_block' | 'approval' | 'restudy' | 'study_progress';

const CATEGORY_ORDER: Record<MsaWorkCategory, number> = {
  equipment_block: 0, approval: 1, restudy: 2, study_progress: 3,
};

export interface MsaWorkItem {
  id: string;
  category: MsaWorkCategory;
  severity: MsaSeverity;
  /** 阻擋原因；工作佇列以「為什麼卡住」而不是「有幾件」為主軸 */
  title: string;
  subject: string;
  owner: string | null;
  dueDate: string | null;
  nextStep: string;
  href: string | null;
}

// 先看類別，同類別再看期限先後；沒有期限的排在有期限之後
const sortWorkItems = (items: MsaWorkItem[]): MsaWorkItem[] =>
  [...items].sort((left, right) => {
    const byCategory =
      CATEGORY_ORDER[left.category] - CATEGORY_ORDER[right.category];
    if (byCategory !== 0) return byCategory;
    if (left.dueDate && right.dueDate) {
      return left.dueDate.localeCompare(right.dueDate);
    }
    if (left.dueDate) return -1;
    if (right.dueDate) return 1;
    return left.title.localeCompare(right.title);
  });

interface MsaWorkQueueProps {
  items: MsaWorkItem[];
  emptyMessage?: string;
}

export default function MsaWorkQueue({
  items, emptyMessage = '目前沒有待處理的 MSA 工作。',
}: MsaWorkQueueProps) {
  if (items.length === 0) {
    return <div className="msa-state">{emptyMessage}</div>;
  }

  return (
    <ul className="msa-queue" aria-label="MSA 工作佇列">
      {sortWorkItems(items).map((item) => {
        const meta = SEVERITY_META[item.severity];
        return (
          <li
            key={item.id}
            className="msa-queue__item"
            data-severity={item.severity}
            data-testid="msa-work-item"
            aria-label={`${meta.label}：${item.title}`}
          >
            <span className="msa-queue__icon" aria-hidden="true">
              {meta.icon}
            </span>
            <div className="msa-queue__body">
              <span className="msa-queue__title">{item.title}</span>
              <span className="msa-queue__meta">
                <span>{item.subject}</span>
                <span>{item.owner ? `負責人：${item.owner}` : '未指派負責人'}</span>
                <span className="msa-num">
                  {item.dueDate ? `期限 ${item.dueDate}` : '無期限'}
                </span>
              </span>
              <span className="msa-queue__next">下一步：{item.nextStep}</span>
            </div>
            {item.href
              ? <Link to={item.href}>前往處理</Link>
              : <span>需校正檢視權限</span>}
          </li>
        );
      })}
    </ul>
  );
}

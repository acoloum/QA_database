import type { MsaStudyType } from '../../types/msa';

import {
  MSA_METHODS,
  type MsaMethodOption,
} from './msaMethods';

interface MsaMethodSelectorProps {
  value: MsaStudyType | null;
  onChange: (option: MsaMethodOption) => void;
}

export default function MsaMethodSelector({
  value, onChange,
}: MsaMethodSelectorProps) {
  return (
    <fieldset className="msa-method-grid">
      <legend>選擇量測系統分析方法</legend>
      {MSA_METHODS.map((method) => (
        <label
          key={method.studyType}
          className="msa-method-card"
          data-selected={method.studyType === value}
        >
          <span className="msa-method-card__head">
            <input
              type="radio"
              name="msa-method"
              value={method.studyType}
              checked={method.studyType === value}
              onChange={() => onChange(method)}
              // 不讓整張卡片的文字成為 radio 的無障礙名稱
              aria-label={method.label}
            />
            <strong>{method.label}</strong>
          </span>
          <p>{method.scenario}</p>
          <dl className="msa-method-card__facts">
            <div>
              <dt>最低資料需求</dt>
              <dd>{method.minimumDesign}</dd>
            </div>
            <div>
              <dt>需要的設備</dt>
              <dd>{method.requires}</dd>
            </div>
          </dl>
          <div className="msa-method-card__answers">
            <h4>可以回答</h4>
            <ul>
              {method.answers.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
          <div className="msa-method-card__limits">
            <h4>不能回答</h4>
            <ul>
              {method.cannotAnswer.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>
        </label>
      ))}
    </fieldset>
  );
}

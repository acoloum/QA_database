import { useEffect, useRef, useState } from 'react';

import type { MsaBlindTask } from '../../types/msa';

interface MsaBlindEntryProps {
  task: MsaBlindTask;
  position: number;
  total: number;
  /** 已記錄的任務數；進度以「完成／總數」呈現而不是只給百分比 */
  completed: number;
  unit: string;
  /** 計數型研究的判定類別；為空代表計量型 */
  categories: string[];
  isSaving: boolean;
  errorMessage: string | null;
  onSubmit: (value: string) => void;
}

/**
 * 盲測輸入畫面只使用後端 tasks DTO：畫面上不存在真實件號、參考值或
 * 前次讀值，因此不可能被誰不小心顯示出來。
 */
export default function MsaBlindEntry({
  task, position, total, completed, unit, categories,
  isSaving, errorMessage, onSubmit,
}: MsaBlindEntryProps) {
  const [value, setValue] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // 換到下一個任務時清空並把焦點帶回輸入欄，讓連續量測不必動滑鼠
  useEffect(() => {
    setValue('');
    inputRef.current?.focus();
  }, [task.requested_order]);

  const isAttribute = categories.length > 0;

  return (
    <form
      className="msa-panel msa-blind-entry"
      onSubmit={(event) => {
        event.preventDefault();
        if (!value.trim() || isSaving) return;
        onSubmit(value.trim());
      }}
    >
      <p className="msa-eyebrow">
        量測 {position} / {total}（已完成 {completed} / {total} 件）
      </p>
      <h2>盲碼 {task.part_blind_code}</h2>
      <p>
        評價人 {task.appraiser_blind_code}｜第 {task.trial_no} 次試驗
      </p>

      {isAttribute ? (
        <fieldset>
          <legend>判定結果</legend>
          {categories.map((category) => (
            <label key={category}>
              <input
                type="radio"
                name="attribute-value"
                value={category}
                checked={value === category}
                onChange={() => setValue(category)}
              />
              {category}
            </label>
          ))}
        </fieldset>
      ) : (
        <label>
          量測讀值（{unit}）
          <input
            ref={inputRef}
            inputMode="decimal"
            autoComplete="off"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </label>
      )}

      {errorMessage && (
        <p className="msa-inline-error" role="alert">{errorMessage}</p>
      )}

      <button type="submit" disabled={isSaving || !value.trim()}>
        {isSaving ? '儲存中…' : '儲存並前往下一件'}
      </button>
    </form>
  );
}

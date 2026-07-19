import { fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';
import MachineConditionForm, { type MachineConditionInput } from './MachineConditionForm';
import MachinePerformancePanel from './MachinePerformancePanel';

const preliminaryResult = {
  available: false,
  preliminary: true,
  index_family: 'machine' as const,
  method: 'G' as const,
  n: 32,
  reason_code: 'MACHINE_SAMPLE_INSUFFICIENT',
  distribution: { model: 'normal', label: '常態分布', accepted: true, reason_code: null },
  quantiles: { q_0_135: 9.7, q_50: 10, q_99_865: 10.3 },
  usl: 11,
  lsl: 9,
  pm: 3.33,
  pmu: 3.33,
  pml: 3.33,
  pmk: 3.33,
  targets: { class: '關鍵', pm: 2.33, pmk: 2 },
  approvable: false,
  evidence: {
    source_semantics: 'patrol_min_max_observations', operators: [7, 8],
    record_ids: [10], detail_ids: [20, 21], date_span: { start: '2026-07-01', end: '2026-07-02' },
    conditions_confirmed: true, condition_reason: '已確認機台設定與治具狀態',
  },
};

const completeCondition: MachineConditionInput = {
  m_id: '7', mat: '6061', spec: '10x1', item: '外徑', pos: 'A',
  conditions_confirmed: true, condition_reason: '已確認機台設定與治具狀態',
};

describe('MachineConditionForm', () => {
  it('未鎖定單一機台、材質、規格、項目與位置時禁止建立研究並說明原因', () => {
    render(<MachineConditionForm value={{ ...completeCondition, m_id: '', pos: '' }} onChange={vi.fn()} onAnalyze={vi.fn()} disabled={false} />);

    expect(screen.getByRole('button', { name: '分析機器績效' })).toBeDisabled();
    expect(screen.getByText(/必須鎖定單一機台、材質、規格、項目與位置/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '分析機器績效' })).toHaveAttribute('aria-describedby');
  });

  it('只在條件已確認且理由符合長度時送出精確 filters 與 options', () => {
    const onAnalyze = vi.fn();
    const Harness = () => {
      const [value, setValue] = useState(completeCondition);
      return <MachineConditionForm value={value} onChange={setValue} onAnalyze={onAnalyze} disabled={false} />;
    };
    render(<Harness />);

    fireEvent.click(screen.getByRole('button', { name: '分析機器績效' }));

    expect(onAnalyze).toHaveBeenCalledWith({
      filters: { m_id: 7, mat: '6061', spec: '10x1', item: '外徑', pos: 'A' },
      options: { conditions_confirmed: true, condition_reason: '已確認機台設定與治具狀態' },
    });
  });
});

describe('MachinePerformancePanel', () => {
  it('顯示初步 Pm／Pmk 與可稽核證據，但不宣告正式達標或可核准', () => {
    render(<MachinePerformancePanel result={preliminaryResult} />);

    expect(screen.getByText('初步結果')).toBeInTheDocument();
    expect(screen.getByText('MACHINE_SAMPLE_INSUFFICIENT')).toBeInTheDocument();
    expect(screen.getByText('Pm 3.330／目標 2.330')).toBeInTheDocument();
    expect(screen.getByText('Pmk 3.330／目標 2.000')).toBeInTheDocument();
    expect(screen.getByText('巡檢 min/max 原始觀測值')).toBeInTheDocument();
    expect(screen.getByText('2026-07-01 ～ 2026-07-02')).toBeInTheDocument();
    expect(screen.queryByText('正式達標')).not.toBeInTheDocument();
    expect(screen.queryByText('可核准研究結果')).not.toBeInTheDocument();
  });
});

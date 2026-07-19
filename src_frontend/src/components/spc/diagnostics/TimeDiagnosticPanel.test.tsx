import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { SpcStudyResult, SpcTimeModel } from '../../../types';
import TimeDiagnosticPanel from './TimeDiagnosticPanel';

const diagnostic: SpcTimeModel = {
  candidate: 'C3', candidate_options: ['A1', 'A2', 'B', 'C1', 'C2', 'C3', 'C4', 'D'],
  confirmed: false, statistically_controlled: false, diagnostic_version: '2026.2', alpha: 0.05,
  evidence: {
    subgroup_count: 30,
    trend: { method: 'Kendall_tau_Theil_Sen', indexes: [0, 1], tau: 0.8, slope: 0.12, detected: true },
    change_points: { method: 'recursive_welch', min_segment: 5, detected: true, change_points: [12], windows: [] },
    variance_change: { method: 'Levene_median_windows', min_segment: 5, detected: false, change_indexes: [], windows: [] },
    random_location: { method: 'one_way_random_effect_f', statistic: 8.1, raw_p_value: 0.002, adjusted_p_value: 0.002, threshold: 0.05, statistical_reject: true, omega_squared: 0.3, effect_threshold: 0.05, reject: true, subgroup_sizes: [3], grand_mean: 10, ss_between: 2, ss_within: 1, df_between: 29, df_within: 60 },
    formal_stability: { evaluated: true, stable: false, rules_used: ['1'], location: { evaluated: true, stable: false, rules_used: ['1'], violations: [] }, variation: { evaluated: true, stable: true, rules_used: ['1'], violations: [] } },
    instantaneous_distribution: { available: true, accepted: true, unimodal: true, normal: true, method: 'AD', statistic: 0.3, p_value: 0.4, adjusted_p_value: 0.4, threshold: 0.05, residual_scale: 0.2, sample_count: 90, acceptance_method: 'normal_fit_or_unimodal_shape', reason_code: null },
    aggregate_modality: { available: true, method: 'fixed_grid_kde', grid_points: 512, bandwidth: 0.4, peak_indexes: [100], peak_values: [10], peak_threshold: 0.1, peak_count: 1, unimodal: true },
    aggregate_normality: { available: true, method: 'normal_candidate', p_value: 0.3, threshold: 0.05, normal: true },
    multiple_testing: { method: 'Holm', families: { trend: [{ raw_p_value: 0.001, adjusted_p_value: 0.001, threshold: 0.05, reject: true }] } },
    thresholds: { alpha: 0.05, minimum_subgroups: 25, min_segment: 5, random_location_omega_squared: 0.05 },
  },
};

const version = (timeModel: SpcTimeModel = diagnostic): SpcStudyResult => ({
  id: 1, study_id: 2, source: 'shipping', study_type: 'retrospective', analysis_family: 'variable',
  process_stream_key: 'stream', filters: {}, version_no: 1, method_version: '2026.2', code_version: null,
  data_hash: 'a'.repeat(64), specification: { found: true }, charts: null,
  stability: { evaluated: true, stable: false, violations: [], rules_used: [] },
  distribution: { model: 'normal', label: '常態', params: [], accepted: true, normal_ok: true, unimodal: true, reason_code: null, candidates: [], fit_method: null, alpha: 0.05 },
  time_model: timeModel, capability: { available: false }, applicability: { applicable: true },
  status: 'draft', audit_incomplete: false, created_by: 1, created_at: '2026-07-19',
});

describe('TimeDiagnosticPanel', () => {
  it('改判時保留系統候選、顯示完整證據並要求 2 到 500 字理由', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<TimeDiagnosticPanel version={version()} canApprove onConfirm={onConfirm} />);

    expect(screen.getByText('系統候選：C3')).toBeInTheDocument();
    const evidence = screen.getByLabelText('時間模型診斷證據');
    expect(evidence).toHaveTextContent(/趨勢：已偵測/);
    expect(evidence).toHaveTextContent(/變點：已偵測索引 12/);
    expect(evidence).toHaveTextContent(/變異變化：未偵測/);
    expect(evidence).toHaveTextContent(/瞬時分布：常態已接受/);
    expect(evidence).toHaveTextContent(/合成分布：單峰常態/);
    expect(evidence).toHaveTextContent(/多重檢定：Holm/);
    expect(evidence).toHaveTextContent(/正式穩定性：不穩定/);

    await user.selectOptions(screen.getByLabelText('確認模型'), 'C4');
    expect(screen.getByRole('button', { name: '確認模型' })).toBeDisabled();
    await user.type(screen.getByLabelText('確認理由'), '已');
    expect(screen.getByRole('button', { name: '確認模型' })).toBeDisabled();
    await user.type(screen.getByLabelText('確認理由'), '核對批次切換紀錄');
    expect(screen.getByRole('button', { name: '確認模型' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: '確認模型' }));
    expect(onConfirm).toHaveBeenCalledWith('C4', '已核對批次切換紀錄');
  });

  it('證據不足或沒有核准權限時不可確認', () => {
    const insufficient = version({
      candidate: null, candidate_options: [], confirmed: false, statistically_controlled: false,
      diagnostic_version: '2026.2', reason_code: 'TIME_DIAGNOSTIC_SAMPLE_INSUFFICIENT',
      evidence: { subgroup_count: 12, minimum_subgroups: 25 },
    });
    const { rerender } = render(<TimeDiagnosticPanel version={insufficient} canApprove onConfirm={vi.fn()} />);
    expect(screen.getByText(/TIME_DIAGNOSTIC_SAMPLE_INSUFFICIENT/)).toBeInTheDocument();
    expect(screen.queryByLabelText('確認模型')).not.toBeInTheDocument();

    rerender(<TimeDiagnosticPanel version={version()} canApprove={false} onConfirm={vi.fn()} />);
    expect(screen.getByText(/需要 SPC 核准權限/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '確認模型' })).toBeDisabled();
  });

  it('顯示後繼版本的人工確認與改判稽核證據', () => {
    render(<TimeDiagnosticPanel version={version({
      ...diagnostic, model: 'C4', system_candidate: 'C3', overridden: true, confirmed: true,
      confirmed_by: 7, confirmed_at: '2026-07-19T08:00:00+00:00', confirmation_reason: '已核對批次切換紀錄',
    })} canApprove onConfirm={vi.fn()} />);
    expect(screen.getByText(/確認模型：C4/)).toBeInTheDocument();
    expect(screen.getByText(/人工改判/)).toBeInTheDocument();
    expect(screen.getByText(/確認者：7/)).toBeInTheDocument();
    expect(screen.getByText('已核對批次切換紀錄')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '確認模型' })).not.toBeInTheDocument();
  });
});

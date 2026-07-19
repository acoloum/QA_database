import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { ProcessCapability, SpcStudyResult, SpcTransformationCandidate } from '../../../types';
import TransformationPanel from './TransformationPanel';

const accepted: SpcTransformationCandidate = {
  model: 'johnson_su', label: 'Johnson SU', params: { a: 1, b: 2, loc: 3, scale: 4 },
  epsilon: 2.22e-16, fit_method: 'johnson_su_mle', ad_statistic: 0.21, ad_p_value: 0.42,
  tail_quantiles: [1, 3, 8], monotonic: true, roundtrip_relative_error: 1e-12,
  accepted: true, reason_code: null, rank: 1,
};
const rejected: SpcTransformationCandidate = {
  model: 'boxcox', label: 'Box-Cox', params: {}, epsilon: 2.22e-16, fit_method: null,
  ad_statistic: null, ad_p_value: null, tail_quantiles: [], monotonic: false,
  roundtrip_relative_error: null, accepted: false, reason_code: 'BOXCOX_POSITIVE_VALUES_REQUIRED', rank: null,
};

const version = (distribution: SpcStudyResult['distribution'], capability: ProcessCapability = { available: false }): SpcStudyResult => ({
  id: 11, study_id: 3, source: 'patrol', study_type: 'retrospective', analysis_family: 'variable',
  process_stream_key: 'stream', filters: {}, version_no: 1, method_version: '2026.2', code_version: null,
  data_hash: 'b'.repeat(64), specification: { found: true }, charts: null,
  stability: { evaluated: true, stable: true, violations: [], rules_used: [] }, distribution,
  time_model: { candidate: 'A2', confirmed: false, statistically_controlled: false }, capability,
  applicability: { applicable: true }, status: 'draft', audit_incomplete: false, created_by: 1, created_at: '2026-07-19',
});

const originalDistribution: SpcStudyResult['distribution'] = {
  model: null, label: '分布模型未確認', params: [], accepted: false, normal_ok: false, unimodal: true,
  reason_code: 'DISTRIBUTION_UNCONFIRMED', candidates: [], fit_method: null, alpha: 0.05, scale: 'original',
  transformation_candidates: [accepted, rejected], transformation_recommendation: accepted,
  transformation_reason_code: null,
  transformation_evidence: { available: true, reason_code: null, n: 90, minimum_sample_size: 25, alpha: 0.05, fit_bias_note: '必須人工確認。' },
};

describe('TransformationPanel', () => {
  it('只讓通過候選可選，並完整顯示參數、AD、尾端與往返證據', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<TransformationPanel version={version(originalDistribution)} canApprove onConfirm={onConfirm} />);

    expect(screen.getByRole('radio', { name: /Johnson SU/ })).toBeEnabled();
    expect(screen.queryByRole('radio', { name: /Box-Cox/ })).not.toBeInTheDocument();
    expect(screen.getByText(/a=1/)).toBeInTheDocument();
    expect(screen.getByText(/AD p.*0.42/)).toBeInTheDocument();
    expect(screen.getByText(/尾端分位數.*1.*3.*8/)).toBeInTheDocument();
    expect(screen.getByText(/嚴格單調.*是/)).toBeInTheDocument();
    expect(screen.getByText(/往返誤差.*1e-12/)).toBeInTheDocument();
    expect(screen.getByText(/BOXCOX_POSITIVE_VALUES_REQUIRED/)).toBeInTheDocument();
    expect(screen.getAllByText(/epsilon/)).toHaveLength(2);

    await user.click(screen.getByRole('radio', { name: /Johnson SU/ }));
    await user.type(screen.getByLabelText('轉換確認理由'), '已');
    expect(screen.getByRole('button', { name: '確認轉換' })).toBeDisabled();
    await user.type(screen.getByLabelText('轉換確認理由'), '複核配適及尾端風險');
    await user.click(screen.getByRole('button', { name: '確認轉換' }));
    expect(onConfirm).toHaveBeenCalledWith('johnson_su', '已複核配適及尾端風險');
  });

  it('原始分布已接受時抑制自動轉換建議', () => {
    render(<TransformationPanel version={version({ ...originalDistribution, model: 'normal', label: '常態分布', accepted: true, transformation_recommendation: null, transformation_reason_code: 'ORIGINAL_DISTRIBUTION_ACCEPTED' })} canApprove onConfirm={vi.fn()} />);
    expect(screen.getByText(/原始分布已通過/)).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Johnson SU/ })).not.toBeChecked();
    expect(screen.getByRole('radio', { name: /Johnson SU/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: '確認轉換' })).toBeDisabled();
  });

  it('轉換後繼版本顯示原始與轉換尺度及確認證據', () => {
    render(<TransformationPanel version={version({
      ...originalDistribution, scale: 'transformed', model: 'normal', label: '常態分布', accepted: true,
      original_model: 'lognormal', transformation_decision: {
        ...accepted, confirmed: true, confirmed_by: 9, confirmed_at: '2026-07-19T08:30:00+00:00',
        confirmation_reason: '已複核配適及尾端風險', original_model: 'lognormal',
      },
    }, { available: true, scale: 'transformed', original_scale: { scale: 'original', quantiles: [1, 3, 8], ppm: { upper: 12, lower: 8, total: 20 }, model: 'johnson_su', transformed_distribution_params: [0, 1] } })} canApprove onConfirm={vi.fn()} />);
    expect(screen.getByText(/目前尺度：轉換尺度/)).toBeInTheDocument();
    expect(screen.getByText(/原始模型：lognormal/)).toBeInTheDocument();
    expect(screen.getByText(/確認者：9/)).toBeInTheDocument();
    expect(screen.getByText('已複核配適及尾端風險')).toBeInTheDocument();
    expect(screen.getByText(/原始尺度分位數：1／3／8/)).toBeInTheDocument();
    expect(screen.getByText(/原始尺度 PPM：上側 12；下側 8；合計 20/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '確認轉換' })).not.toBeInTheDocument();
  });
});

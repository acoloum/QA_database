import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MachinePerformanceResult, SpcStudyResult } from '../../types';
import SpcStudyWorkflowBar from './SpcStudyWorkflowBar';

const machineCapability: MachinePerformanceResult = {
  available: true, approvable: false, preliminary: false, index_family: 'machine', method: 'G', n: 60, reason_code: 'SOURCE_SEMANTICS_UNAUDITABLE',
  distribution: { model: 'normal', label: '常態分布', accepted: true, reason_code: null },
  quantiles: { q_0_135: 9.7, q_50: 10, q_99_865: 10.3 }, usl: 11, lsl: 9,
  pm: 3.33, pmu: 3.33, pml: 3.33, pmk: 3.33, targets: { class: '關鍵', pm: 2.33, pmk: 2 },
  evidence: { source_semantics: 'patrol_min_max_observations', operators: [], record_ids: [], detail_ids: [], date_span: { start: null, end: null }, conditions_confirmed: true, condition_reason: '條件已確認' },
};

const machineVersion = (capability = machineCapability): SpcStudyResult => ({
  id: 8, study_id: 2, source: 'patrol', study_type: 'retrospective', analysis_family: 'machine', process_stream_key: 'machine-stream', filters: {}, options: {}, version_no: 1, method_version: '2026.2', code_version: null, data_hash: 'a'.repeat(64), specification: { found: true }, charts: null, stability: { evaluated: false, stable: null, violations: [], rules_used: [] }, distribution: { model: 'normal', label: '常態', params: [], accepted: true, normal_ok: true, unimodal: true, reason_code: null, candidates: [], fit_method: null, alpha: 0.05 }, time_model: { candidate: null, confirmed: false, statistically_controlled: false }, capability, applicability: { applicable: true }, status: 'submitted', audit_incomplete: false, created_by: 1, created_at: '2026-07-19',
});

describe('SpcStudyWorkflowBar 機器研究', () => {
  it('已送審但不可核准時不提供核准入口並顯示原因', () => {
    render(<SpcStudyWorkflowBar version={machineVersion()} canView canManage canApprove analyzing={false} onAnalyze={vi.fn()} onAction={vi.fn()} onShowHistory={vi.fn()} />);

    expect(screen.queryByRole('button', { name: '核准研究結果' })).not.toBeInTheDocument();
    expect(screen.getByText(/SOURCE_SEMANTICS_UNAUDITABLE/)).toBeInTheDocument();
  });

  it('已確認 B／C／D 的變數研究走研究核准且不提供生產界限生效', () => {
    const onAction = vi.fn();
    const researchVersion: SpcStudyResult = {
      ...machineVersion({ ...machineCapability, approvable: true, reason_code: null }),
      analysis_family: 'variable', capability: { available: false },
      time_model: { candidate: 'C3', model: 'C4', system_candidate: 'C3', overridden: true, confirmed: true, statistically_controlled: false },
    };
    render(<SpcStudyWorkflowBar version={researchVersion} canView canManage canApprove analyzing={false} onAnalyze={vi.fn()} onAction={onAction} onShowHistory={vi.fn()} />);
    screen.getByRole('button', { name: '核准研究結果' }).click();
    expect(onAction).toHaveBeenCalledWith('approve-research');
    expect(screen.queryByRole('button', { name: '核准生效' })).not.toBeInTheDocument();
    expect(screen.getByLabelText('研究生命週期')).toBeInTheDocument();
  });

  it('只有可核准的已送審機器研究才提供核准入口', () => {
    render(<SpcStudyWorkflowBar version={machineVersion({ ...machineCapability, approvable: true, reason_code: null })} canView canManage canApprove analyzing={false} onAnalyze={vi.fn()} onAction={vi.fn()} onShowHistory={vi.fn()} />);

    expect(screen.getByRole('button', { name: '核准研究結果' })).toBeInTheDocument();
  });

  it('機器重建條件無效時停用重建按鈕並保留原因', () => {
    render(<SpcStudyWorkflowBar version={machineVersion({ ...machineCapability, approvable: true, reason_code: null })} canView canManage canApprove analyzing={false} canAnalyze={false} analyzeDisabledReason="重建候選前必須重新完成固定機台與受控條件。" onAnalyze={vi.fn()} onAction={vi.fn()} onShowHistory={vi.fn()} />);

    expect(screen.getByRole('button', { name: '重建候選' })).toBeDisabled();
    expect(screen.getByText('重建候選前必須重新完成固定機台與受控條件。')).toBeInTheDocument();
  });

  it('時間模型確認入口只依核准權限顯示，管理權限不會重複授權', () => {
    const candidateVersion: SpcStudyResult = {
      ...machineVersion(), analysis_family: 'variable', status: 'draft',
      capability: { available: false },
      time_model: { candidate: 'A1', confirmed: false, statistically_controlled: false },
    };
    const manageOnly = render(<SpcStudyWorkflowBar version={candidateVersion} canView canManage canApprove={false} onAnalyze={vi.fn()} onAction={vi.fn()} onShowHistory={vi.fn()} />);
    expect(screen.queryByRole('button', { name: '確認 A1' })).not.toBeInTheDocument();

    manageOnly.rerender(<SpcStudyWorkflowBar version={candidateVersion} canView canManage={false} canApprove onAnalyze={vi.fn()} onAction={vi.fn()} onShowHistory={vi.fn()} />);
    expect(screen.getAllByRole('button', { name: '確認 A1' })).toHaveLength(1);
  });

  it('可關閉舊時間模型入口，避免與進階診斷面板重複', () => {
    const candidateVersion: SpcStudyResult = {
      ...machineVersion(), analysis_family: 'variable', status: 'draft',
      capability: { available: false },
      time_model: { candidate: 'A2', confirmed: false, statistically_controlled: false },
    };
    render(<SpcStudyWorkflowBar version={candidateVersion} canView canManage canApprove showTimeModelAction={false} onAnalyze={vi.fn()} onAction={vi.fn()} onShowHistory={vi.fn()} />);

    expect(screen.queryByRole('button', { name: '確認 A2' })).not.toBeInTheDocument();
  });

  it('未確認時間模型的變數研究不可送審並顯示原因', () => {
    const candidateVersion: SpcStudyResult = {
      ...machineVersion(), analysis_family: 'variable', status: 'draft',
      capability: { available: false },
      time_model: { candidate: 'C3', confirmed: false, statistically_controlled: false },
    };
    render(<SpcStudyWorkflowBar version={candidateVersion} canView canManage canApprove onAnalyze={vi.fn()} onAction={vi.fn()} onShowHistory={vi.fn()} />);

    expect(screen.queryByRole('button', { name: '送審' })).not.toBeInTheDocument();
    expect(screen.getByText('請先由具核准權限者確認時間模型，再送交審查。')).toBeInTheDocument();
  });

  it.each(['A1', 'A2'] as const)('已確認 %s 後管理者可送審正式基準', model => {
    const confirmedVersion: SpcStudyResult = {
      ...machineVersion(), analysis_family: 'variable', status: 'draft',
      capability: { available: true },
      time_model: { candidate: model, model, confirmed: true, statistically_controlled: true },
    };
    render(<SpcStudyWorkflowBar version={confirmedVersion} canView canManage canApprove={false} onAnalyze={vi.fn()} onAction={vi.fn()} onShowHistory={vi.fn()} />);

    expect(screen.getByRole('button', { name: '送審' })).toBeInTheDocument();
    expect(screen.queryByText('請先由具核准權限者確認時間模型，再送交審查。')).not.toBeInTheDocument();
  });
});

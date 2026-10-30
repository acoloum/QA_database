import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ProcessCapabilityCard from './ProcessCapabilityCard';

const targets = {
  class: '主要', confidence: '95%',
  base_p_target: 1.33, base_pk_target: 1.33,
  p_target: 1.35, pk_target: 1.35,
  adjusted: true, insufficient_sample: false,
};

describe('ProcessCapabilityCard (AIAG-VDA 2026)', () => {
  it('穩定製程顯示 Cp/Cpk 為適用指數', () => {
    render(<ProcessCapabilityCard statsItem="外徑" processCapability={{
      available: true, applicable: 'capability', method: 'G',
      cp: 1.5, cpk: 1.4, pp: 1.5, ppk: 1.4, usl: 11, lsl: 9,
      targets, achieved: true, preliminary: false, stability_stable: true,
    }} />);
    expect(screen.getByText('Cpk.G')).toBeInTheDocument();
    expect(screen.getByText(/穩定.*能力/)).toBeInTheDocument();
    expect(screen.getByText(/達標/)).toBeInTheDocument();
  });

  it('不穩定製程只顯示 Pp/Ppk 並標示不穩定', () => {
    render(<ProcessCapabilityCard statsItem="外徑" processCapability={{
      available: true, applicable: 'performance', method: 'G',
      cp: null, cpk: null, pp: 1.2, ppk: 1.1, usl: 11, lsl: 9,
      targets, achieved: false, preliminary: true, stability_stable: false,
    }} />);
    expect(screen.getByText('Ppk.G')).toBeInTheDocument();
    expect(screen.queryByText('Cpk.G')).not.toBeInTheDocument();
    expect(screen.getByText(/未達標/)).toBeInTheDocument();
    expect(screen.getByText(/初步值/)).toBeInTheDocument();
  });

  it('象限 II:具績效但不穩定', () => {
    render(<ProcessCapabilityCard statsItem="外徑" processCapability={{
      available: true, applicable: 'performance', method: 'G',
      cp: null, cpk: null, pp: 1.5, ppk: 1.4, usl: 11, lsl: 9,
      targets, achieved: true, preliminary: false, stability_stable: false,
    }} />);
    expect(screen.getByText(/具績效但不穩定/)).toBeInTheDocument();
  });

  it('象限 III:無能力但穩定', () => {
    render(<ProcessCapabilityCard statsItem="外徑" processCapability={{
      available: true, applicable: 'capability', method: 'G',
      cp: 1.1, cpk: 0.9, pp: 1.1, ppk: 0.9, usl: 11, lsl: 9,
      targets, achieved: false, preliminary: false, stability_stable: true,
    }} />);
    expect(screen.getByText(/無能力但穩定/)).toBeInTheDocument();
  });
  it('無規格時提示到公差管理設定', () => {
    render(<ProcessCapabilityCard statsItem="厚度" processCapability={{ available: false, reason: 'no_tolerance' }} />);
    expect(screen.getByText(/公差管理/)).toBeInTheDocument();
  });

  it('分布未確認時不誤導使用者去設定公差', () => {
    render(<ProcessCapabilityCard statsItem="厚度" processCapability={{
      available: false, reason: 'distribution_unconfirmed', capability_reason: 'NO_ACCEPTED_DISTRIBUTION',
    }} />);
    expect(screen.getByText(/分布模型尚未確認/)).toBeInTheDocument();
    expect(screen.queryByText(/公差管理/)).not.toBeInTheDocument();
  });

  it('規格界限不一致時提示縮小篩選', () => {
    render(<ProcessCapabilityCard statsItem="厚度" processCapability={{ available: false, reason: 'specification_inconsistent' }} />);
    expect(screen.getByText(/不同的/)).toBeInTheDocument();
    expect(screen.queryByText(/公差管理/)).not.toBeInTheDocument();
  });
});

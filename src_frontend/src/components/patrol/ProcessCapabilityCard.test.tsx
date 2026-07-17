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
});

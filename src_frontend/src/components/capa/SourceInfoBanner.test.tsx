import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import SourceInfoBanner from './SourceInfoBanner';
import type { CAPADetail } from '../../types';

const capa = {
  id: 1,
  no: 'CAPA-001',
  source_type: 'ncmr',
  source_id: 99,
  source_info: {
    廠商: '測試廠商',
    材質: 'SUS304',
    規格: '10x20',
    不良: '尺寸NG',
    備註: '第五個欄位不顯示',
  },
  rigor: '完整8D',
  status: '進行中',
  progress: { total_steps: 9, completed_steps: 1, percent: 11, step_status: {} },
} as CAPADetail;

describe('SourceInfoBanner', () => {
  it('顯示來源類型、來源編號與前四個來源欄位', () => {
    render(<SourceInfoBanner capa={capa} />);

    expect(screen.getByText('NCMR')).toBeInTheDocument();
    expect(screen.getByText('#99')).toBeInTheDocument();
    expect(screen.getByText('測試廠商')).toBeInTheDocument();
    expect(screen.getByText('SUS304')).toBeInTheDocument();
    expect(screen.getByText('10x20')).toBeInTheDocument();
    expect(screen.getByText('尺寸NG')).toBeInTheDocument();
    expect(screen.queryByText('第五個欄位不顯示')).not.toBeInTheDocument();
  });
});

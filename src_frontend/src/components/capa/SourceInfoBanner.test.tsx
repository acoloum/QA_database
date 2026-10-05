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

describe('SourceInfoBanner 共用客訴', () => {
  const linkedCapa = {
    ...capa,
    source_type: 'complaint',
    source_id: 5,
    source_info: {},
    linked_complaints: [
      { id: 5, complaint_no: 'CC-001', customer: '甲客戶', material: '6063', spec: 'Φ20', status: '處理中' },
      { id: 6, complaint_no: 'CC-002', customer: '甲客戶', material: '6061', spec: 'Φ30', status: '處理中' },
    ],
  } as CAPADetail;

  it('多張客訴共用此 CAPA 時列出每張客訴單號與規格', () => {
    render(<SourceInfoBanner capa={linkedCapa} />);

    expect(screen.getByText(/共用此 CAPA 的客訴（2）/)).toBeInTheDocument();
    expect(screen.getByText('CC-001')).toBeInTheDocument();
    expect(screen.getByText('CC-002')).toBeInTheDocument();
    expect(screen.getByText(/6061｜Φ30/)).toBeInTheDocument();
  });

  it('只有來源客訴一張時不顯示共用清單', () => {
    render(<SourceInfoBanner capa={{ ...linkedCapa, linked_complaints: linkedCapa.linked_complaints!.slice(0, 1) }} />);

    expect(screen.queryByText(/共用此 CAPA 的客訴/)).not.toBeInTheDocument();
  });
});

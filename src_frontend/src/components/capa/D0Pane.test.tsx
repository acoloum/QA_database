import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import D0Pane from './D0Pane';

vi.mock('../common/AttachmentList', () => ({
  default: ({ dStep }: { dStep: string }) => <div>附件列表 {dStep}</div>,
}));

vi.mock('../common/AttachmentUploader', () => ({
  default: ({ dStep }: { dStep: string }) => <div>附件上傳 {dStep}</div>,
}));

const noop = () => undefined;

describe('D0Pane', () => {
  it('渲染緊急應對欄位、附件區並可儲存', () => {
    const setCriteria = vi.fn();
    const onSave = vi.fn();

    render(
      <D0Pane
        symptom="異常症狀"
        setSymptom={noop}
        criteria={[]}
        setCriteria={setCriteria}
        severity=""
        setSeverity={noop}
        rigor="完整8D"
        setRigor={noop}
        deadline=""
        setDeadline={noop}
        capaId={42}
        onSave={onSave}
        saving={false}
      />,
    );

    expect(screen.getByLabelText('症狀描述')).toHaveValue('異常症狀');
    expect(screen.getByLabelText('嚴重度')).toBeInTheDocument();
    expect(screen.getByLabelText('嚴格度（可 Override）')).toBeInTheDocument();
    expect(screen.getByLabelText('客戶要求結案日')).toBeInTheDocument();
    expect(screen.getByText('附件列表 D0')).toBeInTheDocument();
    expect(screen.getByText('附件上傳 D0')).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText('客戶端發現'));
    expect(setCriteria).toHaveBeenCalledWith(['客戶端發現']);

    fireEvent.click(screen.getByRole('button', { name: '儲存此步驟' }));
    expect(onSave).toHaveBeenCalled();
  });
});

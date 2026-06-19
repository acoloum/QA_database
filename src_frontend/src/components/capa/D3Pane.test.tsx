import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import D3Pane from './D3Pane';

vi.mock('../common/AttachmentList', () => ({
  default: ({ dStep }: { dStep: string }) => <div>附件列表 {dStep}</div>,
}));

vi.mock('../common/AttachmentUploader', () => ({
  default: ({ dStep }: { dStep: string }) => <div>附件上傳 {dStep}</div>,
}));

const noop = () => undefined;

describe('D3Pane', () => {
  it('渲染暫時對策欄位、附件區並可儲存', () => {
    const onSave = vi.fn();

    render(
      <D3Pane
        action=""
        setAction={noop}
        effectiveDate=""
        setEffectiveDate={noop}
        verification=""
        setVerification={noop}
        capaId={42}
        onSave={onSave}
        saving={false}
      />,
    );

    expect(screen.getByLabelText('暫時對策內容')).toBeInTheDocument();
    expect(screen.getByLabelText('生效日期')).toBeInTheDocument();
    expect(screen.getByLabelText('有效性驗證')).toBeInTheDocument();
    expect(screen.getByText('附件列表 D3')).toBeInTheDocument();
    expect(screen.getByText('附件上傳 D3')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '儲存此步驟' }));
    expect(onSave).toHaveBeenCalled();
  });
});

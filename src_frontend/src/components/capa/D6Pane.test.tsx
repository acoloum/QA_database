import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import D6Pane from './D6Pane';

vi.mock('../common/AttachmentList', () => ({
  default: ({ dStep }: { dStep: string }) => <div>附件列表 {dStep}</div>,
}));

vi.mock('../common/AttachmentUploader', () => ({
  default: ({ dStep }: { dStep: string }) => <div>附件上傳 {dStep}</div>,
}));

const noop = () => undefined;

describe('D6Pane', () => {
  it('渲染實施驗證欄位、通過提示與附件區', () => {
    const setVerified = vi.fn();

    render(
      <D6Pane
        implDate=""
        setImplDate={noop}
        result=""
        setResult={noop}
        verified
        setVerified={setVerified}
        capaId={42}
        onSave={noop}
        saving={false}
      />,
    );

    expect(screen.getByLabelText('實施日期')).toBeInTheDocument();
    expect(screen.getByLabelText('驗證結果')).toBeInTheDocument();
    expect(screen.getByText('D6 驗證已通過，可進行 D8 結案。')).toBeInTheDocument();
    expect(screen.getByText('附件列表 D6')).toBeInTheDocument();
    expect(screen.getByText('附件上傳 D6')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox', { name: /確認驗證通過/ }));
    expect(setVerified).toHaveBeenCalledWith(false);
  });
});

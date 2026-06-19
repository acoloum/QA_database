import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import D2Pane from './D2Pane';

vi.mock('../common/AttachmentList', () => ({
  default: ({ dStep }: { dStep: string }) => <div>附件列表 {dStep}</div>,
}));

vi.mock('../common/AttachmentUploader', () => ({
  default: ({ dStep }: { dStep: string }) => <div>附件上傳 {dStep}</div>,
}));

const noop = () => undefined;

describe('D2Pane', () => {
  it('渲染 5W2H 欄位與 D2 附件區', () => {
    render(
      <D2Pane
        what=""
        setWhat={noop}
        where=""
        setWhere={noop}
        when=""
        setWhen={noop}
        who=""
        setWho={noop}
        why=""
        setWhy={noop}
        how=""
        setHow={noop}
        howMany=""
        setHowMany={noop}
        capaId={42}
        onSave={noop}
        saving={false}
      />,
    );

    expect(screen.getByLabelText('What（是什麼）')).toBeInTheDocument();
    expect(screen.getByLabelText('How Many（數量）')).toBeInTheDocument();
    expect(screen.getByText('附件列表 D2')).toBeInTheDocument();
    expect(screen.getByText('附件上傳 D2')).toBeInTheDocument();
  });
});

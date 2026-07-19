import { fireEvent, render, screen } from '@testing-library/react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import SpcOcapOffcanvas from './SpcOcapOffcanvas';

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: false,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

describe('SpcOcapOffcanvas', () => {
  it('提供 6M、重新量測、製程調整、產品處置、責任人與有效性欄位', () => {
    const onSave = vi.fn();
    const assignees = [
      { id: 8, username: 'qa-user', role: 'qa_supervisor' as const, role_name: 'QA主管' },
      { id: 9, username: 'qc-user', role: 'qc_manager' as const, role_name: '品管經理' },
    ];
    render(
      <SpcOcapOffcanvas
        show
        eventId={81}
        assignees={assignees}
        onHide={vi.fn()}
        onSave={onSave}
      />,
    );

    expect(screen.getByLabelText('6M 調查')).toBeInTheDocument();
    expect(screen.getByLabelText('重新量測')).toBeInTheDocument();
    expect(screen.getByLabelText('製程調整')).toBeInTheDocument();
    expect(screen.getByLabelText('產品處置')).toBeInTheDocument();
    expect(screen.getByLabelText('責任人')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'qa-user（QA主管）' })).toBeInTheDocument();
    expect(screen.getByLabelText('有效性確認')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('責任人'), { target: { value: '9' } });

    fireEvent.click(screen.getByLabelText('結案'));
    expect(screen.getByRole('button', { name: '儲存 OCAP' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('有效性確認'), { target: { value: '連續三批未再發生' } });
    fireEvent.click(screen.getByRole('button', { name: '儲存 OCAP' }));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      eventId: 81,
      payload: expect.objectContaining({
        status: 'closed', effectiveness: '連續三批未再發生', owner_id: 9,
      }),
    }));
  });

  it('保留不在清單中的歷史責任人但禁止重新選取', () => {
    const assignees = [
      { id: 8, username: 'qa-user', role: 'qa_supervisor' as const, role_name: 'QA主管' },
      { id: 9, username: 'qc-user', role: 'qc_manager' as const, role_name: '品管經理' },
    ];
    render(
      <SpcOcapOffcanvas
        show
        eventId={81}
        assignees={assignees}
        initialValue={{ owner_id: 77 } as never}
        onHide={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    const historical = screen.getByRole('option', {
      name: '原責任人 ID：77（目前不可指派）',
    });
    expect(historical).toBeDisabled();
    expect(screen.getByLabelText('責任人')).toHaveValue('77');
  });

  it('責任人清單載入失敗時不把現有責任人誤判為不可指派', () => {
    render(
      <SpcOcapOffcanvas
        show
        eventId={81}
        assigneesError
        initialValue={{ owner_id: 77 } as never}
        onHide={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    expect(screen.getByRole('option', {
      name: '原責任人 ID：77（無法確認指派狀態）',
    })).toBeInTheDocument();
    expect(screen.queryByText(/目前不可指派/)).not.toBeInTheDocument();
  });

  it('儲存失敗時顯示提示並保留目前輸入', () => {
    const onSave = vi.fn();
    const view = render(
      <SpcOcapOffcanvas
        show
        eventId={81}
        onHide={vi.fn()}
        onSave={onSave}
      />,
    );

    fireEvent.change(screen.getByLabelText('製程調整'), {
      target: { value: '保留的調整內容' },
    });
    fireEvent.click(screen.getByRole('button', { name: '儲存 OCAP' }));
    view.rerender(
      <SpcOcapOffcanvas
        show
        eventId={81}
        saveError
        onHide={vi.fn()}
        onSave={onSave}
      />,
    );

    expect(screen.getByText('OCAP 儲存失敗，已保留目前輸入，請確認資料後再試。')).toBeInTheDocument();
    expect(screen.getByLabelText('製程調整')).toHaveValue('保留的調整內容');
  });

  it('儲存中阻止標頭、取消、背景與 Escape 關閉', () => {
    const onHide = vi.fn();
    const { container } = render(
      <SpcOcapOffcanvas
        show
        eventId={81}
        pending
        onHide={onHide}
        onSave={vi.fn()}
      />,
    );

    expect(container.ownerDocument.querySelector('.btn-close')).not.toBeInTheDocument();
    const cancel = screen.getByRole('button', { name: '取消' });
    expect(cancel).toBeDisabled();
    fireEvent.click(cancel);
    fireEvent.keyDown(document, { key: 'Escape', code: 'Escape' });
    const backdrop = container.ownerDocument.querySelector('.offcanvas-backdrop');
    if (backdrop) fireEvent.click(backdrop);

    expect(onHide).not.toHaveBeenCalled();
  });
});

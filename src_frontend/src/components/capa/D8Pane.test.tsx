import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import D8Pane from './D8Pane';

const noop = () => undefined;

describe('D8Pane', () => {
  it('顯示結案 gate 提示並在條件滿足且有聲明時可結案', () => {
    const onClose = vi.fn();

    const { rerender } = render(
      <D8Pane
        confirmation=""
        setConfirmation={noop}
        recognition=""
        setRecognition={noop}
        closeGateData={{
          can_close: false,
          d6_passed: false,
          blocking_tasks: [{ id: 1 }],
          missing_steps: ['D4', 'D5'],
        }}
        closeGateLoading={false}
        isClosed={false}
        onClose={onClose}
        closing={false}
      />,
    );

    expect(screen.getByText('D6 尚未勾選「驗證通過」，無法結案。')).toBeInTheDocument();
    expect(screen.getByText('以下步驟尚未完成，無法結案：D4、D5')).toBeInTheDocument();
    expect(screen.getByText('尚有 1 個 D7 任務未完成或豁免，無法結案。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '確認結案（不可逆）' })).toBeDisabled();

    rerender(
      <D8Pane
        confirmation="所有改善措施均已確認有效"
        setConfirmation={noop}
        recognition="感謝團隊完成改善"
        setRecognition={noop}
        closeGateData={{
          can_close: true,
          d6_passed: true,
          blocking_tasks: [],
          missing_steps: [],
        }}
        closeGateLoading={false}
        isClosed={false}
        onClose={onClose}
        closing={false}
      />,
    );

    expect(screen.getByText('所有結案條件已滿足，可以結案。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '確認結案（不可逆）' }));
    expect(onClose).toHaveBeenCalled();
  });

  it('已結案時只顯示結案日期', () => {
    render(
      <D8Pane
        confirmation=""
        setConfirmation={noop}
        recognition=""
        setRecognition={noop}
        closeGateData={null}
        closeGateLoading={false}
        isClosed
        closeDate="2026-06-20"
        onClose={noop}
        closing={false}
      />,
    );

    expect(screen.getByText('此 CAPA 已於 2026-06-20 結案。')).toBeInTheDocument();
  });
});

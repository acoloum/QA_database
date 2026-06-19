import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import D4Pane from './D4Pane';

const noop = () => undefined;

describe('D4Pane', () => {
  it('渲染 5 Why 分析並可儲存', () => {
    const onSave = vi.fn();

    render(
      <D4Pane
        tool="5why"
        setTool={noop}
        fiveWhy={[{ why: '為什麼發生', answer: '原因一' }]}
        setFiveWhy={noop}
        fishbone={{}}
        setFishbone={noop}
        rootCause="根本原因"
        setRootCause={noop}
        onSave={onSave}
        saving={false}
      />,
    );

    expect(screen.getByRole('radio', { name: '5 Why' })).toBeChecked();
    expect(screen.getByText('Why 1')).toBeInTheDocument();
    expect(screen.getByDisplayValue('根本原因')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '儲存此步驟' }));
    expect(onSave).toHaveBeenCalled();
  });

  it('切換魚骨圖工具時顯示 6M 編輯區', () => {
    const setTool = vi.fn();

    render(
      <D4Pane
        tool="fishbone"
        setTool={setTool}
        fiveWhy={[]}
        setFiveWhy={noop}
        fishbone={{ man: ['人員訓練不足'] }}
        setFishbone={noop}
        rootCause=""
        setRootCause={noop}
        onSave={noop}
        saving={false}
      />,
    );

    expect(screen.getByRole('radio', { name: '魚骨圖（6M）' })).toBeChecked();
    expect(screen.getByText('人員（Man）')).toBeInTheDocument();
    expect(screen.getByDisplayValue('人員訓練不足')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('radio', { name: '5 Why' }));
    expect(setTool).toHaveBeenCalledWith('5why');
  });
});

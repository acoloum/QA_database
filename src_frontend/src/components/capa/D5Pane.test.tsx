import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import D5Pane from './D5Pane';

const noop = () => undefined;

describe('D5Pane', () => {
  it('渲染永久對策欄位並可儲存', () => {
    const onSave = vi.fn();

    render(
      <D5Pane
        action=""
        setAction={noop}
        plannedDate=""
        setPlannedDate={noop}
        verifyPlan=""
        setVerifyPlan={noop}
        onSave={onSave}
        saving={false}
      />,
    );

    expect(screen.getByLabelText('永久對策內容')).toBeInTheDocument();
    expect(screen.getByLabelText('預計實施日')).toBeInTheDocument();
    expect(screen.getByLabelText('驗證計畫')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '儲存此步驟' }));
    expect(onSave).toHaveBeenCalled();
  });
});

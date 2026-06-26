import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ComplaintResponseSection, ComplaintWarrantySection } from './ComplaintSections';

describe('ComplaintSections', () => {
  it('renders warranty fields when complaint type needs warranty information', () => {
    render(
      <ComplaintWarrantySection
        complaintType="warranty"
        deviceSerial="SN-1"
        usageEnv="戶外"
        failureHours="12"
        onDeviceSerialChange={vi.fn()}
        onUsageEnvChange={vi.fn()}
        onFailureHoursChange={vi.fn()}
      />,
    );

    expect(screen.getByText('Warranty 申請資訊')).toBeInTheDocument();
    expect(screen.getByDisplayValue('SN-1')).toBeInTheDocument();
  });

  it('renders edit response controls', () => {
    render(
      <ComplaintResponseSection
        status="處理中"
        initialReply="初步"
        finalReply="結論"
        onStatusChange={vi.fn()}
        onInitialReplyChange={vi.fn()}
        onFinalReplyChange={vi.fn()}
      />,
    );

    expect(screen.getByText('處理回覆')).toBeInTheDocument();
    expect(screen.getByDisplayValue('初步')).toBeInTheDocument();
  });
});

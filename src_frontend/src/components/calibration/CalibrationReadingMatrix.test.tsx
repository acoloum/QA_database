import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import CalibrationReadingMatrix from './CalibrationReadingMatrix';

const point = {
  id: 31,
  point_code: 'P01',
  measurement_mode: '外徑',
  unit: 'mm',
  reference_input_mode: 'certified_value' as const,
  required_repetitions: 3,
  reference_value: '10.0000',
};

function MatrixHarness({
  onChange,
}: {
  onChange: (values: Record<string, string>) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  return (
    <CalibrationReadingMatrix
      points={[{ ...point, reference_input_mode: 'paired_reading' }]}
      values={values}
      onChange={(next) => {
        setValues(next);
        onChange(next);
      }}
    />
  );
}

describe('校正原始讀值矩陣', () => {
  it('Excel 貼上維度不符時不部分覆寫既有讀值', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <CalibrationReadingMatrix
        points={[point]}
        values={{
          'P01:1:indicated': '10.001',
          'P01:2:indicated': '10.002',
          'P01:3:indicated': '10.003',
        }}
        onChange={onChange}
      />,
    );

    const firstCell = screen.getByLabelText('P01 試驗 1 受校件器示值');
    await user.click(firstCell);
    fireEvent.paste(firstCell, {
      clipboardData: { getData: () => '11.1\t11.2\n12.1\t12.2' },
    });

    expect(screen.getByRole('alert')).toHaveTextContent('貼上資料為 2 列 2 欄');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('paired mode 顯示標準器與受校件兩欄並保留 Decimal 字串', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<MatrixHarness onChange={onChange} />);

    await user.type(
      screen.getByLabelText('P01 試驗 1 標準器讀值'),
      '9.9990',
    );
    await user.type(
      screen.getByLabelText('P01 試驗 1 受校件器示值'),
      '10.0010',
    );

    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      'P01:1:standard': '9.9990',
      'P01:1:indicated': '10.0010',
    }));
  });

  it('certified mode 顯示唯讀參考值與受校件讀值', () => {
    render(
      <CalibrationReadingMatrix
        points={[point]}
        values={{}}
        onChange={vi.fn()}
      />,
    );

    const table = screen.getByRole('table', { name: 'P01 原始讀值' });
    expect(screen.getByLabelText('P01 認證參考值'))
      .toHaveValue('10.0000');
    expect(table).toBeInTheDocument();
    expect(screen.queryByLabelText('P01 試驗 1 標準器讀值'))
      .not.toBeInTheDocument();
  });

  it('模板要求時保存擴充不確定度與涵蓋因子的 Decimal 字串', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    function UncertaintyHarness() {
      const [values, setValues] = useState<Record<string, string>>({});
      return (
        <CalibrationReadingMatrix
          points={[{ ...point, uncertainty_required: true }]}
          values={values}
          onChange={(next) => {
            setValues(next);
            onChange(next);
          }}
        />
      );
    }
    render(<UncertaintyHarness />);

    await user.type(screen.getByLabelText('P01 擴充不確定度'), '0.00050');
    await user.type(screen.getByLabelText('P01 涵蓋因子'), '2.000');

    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({
      'P01:uncertainty': '0.00050',
      'P01:coverage': '2.000',
    }));
  });

  it('方向鍵與 Enter 在矩陣儲存格間移動焦點', async () => {
    const user = userEvent.setup();
    render(
      <CalibrationReadingMatrix
        points={[{ ...point, reference_input_mode: 'paired_reading' }]}
        values={{}}
        onChange={vi.fn()}
      />,
    );

    const standard1 = screen.getByLabelText('P01 試驗 1 標準器讀值');
    const indicated1 = screen.getByLabelText('P01 試驗 1 受校件器示值');
    const indicated2 = screen.getByLabelText('P01 試驗 2 受校件器示值');
    standard1.focus();
    await user.keyboard('{ArrowRight}');
    expect(indicated1).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(indicated2).toHaveFocus();
    await user.keyboard('{ArrowLeft}');
    expect(screen.getByLabelText('P01 試驗 2 標準器讀值')).toHaveFocus();
  });
});

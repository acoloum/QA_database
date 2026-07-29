import type { EquipmentCalibrationPoint } from '../../types/calibration';

const resultLabel = (result: EquipmentCalibrationPoint['result']) => ({
  pending: '待判定',
  pass: '合格',
  fail: '不合格',
  limited_use: '限制使用',
}[result]);

export default function CalibrationPointSummary({
  point,
}: { point: EquipmentCalibrationPoint }) {
  return (
    <article className="cal-point-summary" data-result={point.result}>
      <header>
        <div>
          <code>{point.point_code}</code>
          <h3>{point.measurement_mode}</h3>
        </div>
        <span>{resultLabel(point.result)}</span>
      </header>
      <dl>
        <div><dt>名目值</dt><dd>{point.nominal_value ?? '—'} {point.unit}</dd></div>
        <div><dt>平均器差</dt><dd>{point.mean_error ?? '—'} {point.unit}</dd></div>
        <div><dt>重複性</dt><dd>{point.repeatability_value ?? '—'} {point.unit}</dd></div>
        <div><dt>完成讀值</dt><dd>{point.completed_reading_count}/{point.required_repetitions}</dd></div>
      </dl>
    </article>
  );
}

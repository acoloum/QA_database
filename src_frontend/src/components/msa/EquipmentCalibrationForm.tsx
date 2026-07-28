import { useState } from 'react';

import { useAuth } from '../../context/useAuth';
import {
  useApproveMsaCalibration,
  useCreateMsaCalibration,
} from '../../hooks/useMsaEquipment';
import type {
  CalibrationResult,
  CalibrationType,
  EquipmentCalibration,
  EquipmentCorrectionPointInput,
} from '../../types/msa';

interface EquipmentCalibrationFormProps {
  equipmentId: number;
  calibrations: EquipmentCalibration[];
}

const emptyPoint = (): EquipmentCorrectionPointInput => ({
  measurement_mode: '',
  nominal_value: '',
  indicated_value: '',
  correction_value: '',
  unit: '',
});

const errorMessage = (error: unknown) => (
  error instanceof Error ? error.message : '操作未完成，請檢查校驗內容。'
);

export default function EquipmentCalibrationForm({
  equipmentId,
  calibrations,
}: EquipmentCalibrationFormProps) {
  const { hasPermission } = useAuth();
  const createCalibration = useCreateMsaCalibration();
  const approveCalibration = useApproveMsaCalibration();
  const [approvalReason, setApprovalReason] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [points, setPoints] = useState<EquipmentCorrectionPointInput[]>([
    emptyPoint(),
  ]);
  const [calibrationType, setCalibrationType] = useState<CalibrationType>('external');
  const [result, setResult] = useState<CalibrationResult>('pass');

  const updatePoint = (
    index: number,
    field: keyof EquipmentCorrectionPointInput,
    value: string,
  ) => {
    setPoints((current) => current.map((point, pointIndex) => (
      pointIndex === index ? { ...point, [field]: value } : point
    )));
  };

  const submitDraft = async (form: HTMLFormElement) => {
    const data = new FormData(form);
    setFormError(null);
    try {
      await createCalibration.mutateAsync({
        equipmentId,
        calibration_type: calibrationType,
        calibration_date: String(data.get('calibration_date')),
        effective_date: String(data.get('effective_date') || '') || null,
        next_due_date: String(data.get('next_due_date') || '') || null,
        calibration_provider: String(data.get('calibration_provider') || '') || null,
        certificate_no: String(data.get('certificate_no') || '') || null,
        reference_standard_no: String(data.get('reference_standard_no') || '') || null,
        reference_standard_due_date: String(data.get('reference_standard_due_date') || '') || null,
        traceability_standard: String(data.get('traceability_standard') || '') || null,
        uncertainty_statement: String(data.get('uncertainty_statement') || '') || null,
        result,
        restriction_conditions: String(data.get('restriction_conditions') || '') || null,
        applicable_modes: String(data.get('applicable_modes') || '')
          .split(',')
          .map((value) => value.trim())
          .filter(Boolean),
        correction_points: points,
      });
      form.reset();
      setPoints([emptyPoint()]);
    } catch (error) {
      setFormError(errorMessage(error));
    }
  };

  const approve = async (calibration: EquipmentCalibration) => {
    setFormError(null);
    try {
      await approveCalibration.mutateAsync({
        calibrationId: calibration.id,
        equipmentId,
        expected_status: 'draft',
        reason: approvalReason.trim(),
      });
      setApprovalReason('');
    } catch (error) {
      setFormError(errorMessage(error));
    }
  };

  return (
    <div className="msa-calibration-control">
      {hasPermission('msa.manage') && (
        <form
          className="msa-calibration-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submitDraft(event.currentTarget);
          }}
        >
          <h3>建立校驗草稿</h3>
          <p className="msa-help">草稿不會成為正式資格證據，必須由核准者另行確認。</p>
          <div className="msa-form-grid">
            <label>
              校驗類型
              <select
                value={calibrationType}
                onChange={(event) => setCalibrationType(event.target.value as CalibrationType)}
              >
                <option value="external">外校</option>
                <option value="internal">內校</option>
                <option value="exempt">免校</option>
              </select>
            </label>
            <label>
              校驗結果
              <select
                value={result}
                onChange={(event) => setResult(event.target.value as CalibrationResult)}
              >
                <option value="pass">通過</option>
                <option value="limited_use">限制使用</option>
                <option value="fail">失敗</option>
                <option value="pending">待確認</option>
              </select>
            </label>
            <label>
              校驗日期
              <input name="calibration_date" type="date" required />
            </label>
            <label>
              有效日期
              <input name="effective_date" type="date" />
            </label>
            <label>
              下次校驗日
              <input name="next_due_date" type="date" />
            </label>
            <label>
              校驗機構
              <input name="calibration_provider" />
            </label>
            <label>
              證書編號
              <input name="certificate_no" />
            </label>
            <label>
              參考標準器編號
              <input name="reference_standard_no" placeholder="標準件 / 量塊編號" />
            </label>
            <label>
              標準器有效期
              <input name="reference_standard_due_date" type="date" />
            </label>
            <label>
              適用量測模式
              <input name="applicable_modes" placeholder="以逗號分隔" />
            </label>
            <label className="msa-form-grid__wide">
              追溯標準
              <textarea name="traceability_standard" rows={2} />
            </label>
            <label className="msa-form-grid__wide">
              不確定度說明
              <textarea name="uncertainty_statement" rows={2} />
            </label>
            <label className="msa-form-grid__wide">
              限制條件
              <textarea name="restriction_conditions" rows={2} />
            </label>
          </div>
          <fieldset className="msa-points">
            <legend>補正點</legend>
            {points.map((point, index) => (
              <div className="msa-point-row" key={`point-${index + 1}`}>
                <label>
                  量測模式
                  <input
                    value={String(point.measurement_mode ?? '')}
                    onChange={(event) => updatePoint(index, 'measurement_mode', event.target.value)}
                  />
                </label>
                <label>
                  名目值
                  <input
                    inputMode="decimal"
                    required
                    value={String(point.nominal_value)}
                    onChange={(event) => updatePoint(index, 'nominal_value', event.target.value)}
                  />
                </label>
                <label>
                  器示值
                  <input
                    inputMode="decimal"
                    required
                    value={String(point.indicated_value)}
                    onChange={(event) => updatePoint(index, 'indicated_value', event.target.value)}
                  />
                </label>
                <label>
                  補正值
                  <input
                    inputMode="decimal"
                    value={String(point.correction_value ?? '')}
                    onChange={(event) => updatePoint(index, 'correction_value', event.target.value)}
                  />
                </label>
                <label>
                  單位
                  <input
                    value={String(point.unit ?? '')}
                    onChange={(event) => updatePoint(index, 'unit', event.target.value)}
                  />
                </label>
                <button
                  type="button"
                  className="msa-button msa-button--quiet"
                  onClick={() => setPoints((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                >
                  移除補正點
                </button>
              </div>
            ))}
            <button
              type="button"
              className="msa-button msa-button--quiet"
              onClick={() => setPoints((current) => [...current, emptyPoint()])}
            >
              新增補正點
            </button>
          </fieldset>
          <button
            className="msa-button msa-button--primary"
            type="submit"
            disabled={createCalibration.isPending}
          >
            儲存校驗草稿
          </button>
        </form>
      )}

      {hasPermission('msa.approve') && calibrations.some((item) => item.status === 'draft') && (
        <section className="msa-approval" aria-labelledby="calibration-approval-title">
          <h3 id="calibration-approval-title">草稿核准</h3>
          <label>
            校驗核准理由
            <textarea
              value={approvalReason}
              onChange={(event) => setApprovalReason(event.target.value)}
              rows={2}
              required
            />
          </label>
          {calibrations.filter((item) => item.status === 'draft').map((item) => (
            <button
              key={item.id}
              type="button"
              className="msa-button msa-button--primary"
              disabled={!approvalReason.trim() || approveCalibration.isPending}
              onClick={() => void approve(item)}
            >
              核准校驗 {item.certificate_no || `#${item.id}`}
            </button>
          ))}
        </section>
      )}
      {formError && <p className="msa-inline-error" role="alert">{formError}</p>}
    </div>
  );
}

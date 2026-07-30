import { useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router';

import MsaMethodSelector, {
  findMethod,
  type MsaMethodOption,
} from '../../components/msa/MsaMethodSelector';
import MsaPlanReview, {
  type MsaPlanBlocker,
} from '../../components/msa/MsaPlanReview';
import { useMsaCriteria } from '../../hooks/useMsaCriteria';
import { useMsaEquipment } from '../../hooks/useMsaEquipment';
import { useAuth } from '../../context/useAuth';
import {
  useCreateMsaPlan,
  useCreateMsaStudy,
  useFreezeMsaPlan,
} from '../../hooks/useMsaStudies';
import type {
  MeasurementEquipment,
  MsaMeasurementPurpose,
  MsaPercentBasis,
  MsaStudyType,
} from '../../types/msa';
import './msa.css';

const STEPS = [
  '研究目的與方法',
  '品質特性與規格',
  '設備與參考標準',
  '零件、評價人與假設',
  '判定準則',
  '檢閱與凍結',
] as const;

const PHYSICAL_ASSUMPTIONS = [
  { key: 'sample_homogeneity', label: '樣本同質性成立' },
  { key: 'shelf_life', label: '樣本在有效期內' },
  { key: 'process_stability', label: '製程於研究期間穩定' },
  { key: 'pairing_assumption', label: '配對／分組假設成立' },
] as const;

interface WizardState {
  studyType: MsaStudyType | null;
  measurementPurpose: MsaMeasurementPurpose;
  characteristic: string;
  unit: string;
  lsl: string;
  usl: string;
  noToleranceReason: string;
  processSigma: string;
  percentBasis: MsaPercentBasis;
  primaryGaugeId: string;
  referenceStandardId: string;
  partCount: string;
  appraiserCount: string;
  trialCount: string;
  randomSeed: string;
  hasReferenceValues: boolean;
  categorySet: string;
  assumptions: Record<string, boolean>;
  criteriaProfileId: string;
}

const initialState: WizardState = {
  studyType: null,
  measurementPurpose: 'product_control',
  characteristic: '',
  unit: '',
  lsl: '',
  usl: '',
  noToleranceReason: '',
  processSigma: '',
  percentBasis: 'tolerance',
  primaryGaugeId: '',
  referenceStandardId: '',
  partCount: '10',
  appraiserCount: '3',
  trialCount: '3',
  randomSeed: '20260728',
  hasReferenceValues: false,
  categorySet: 'pass, fail',
  assumptions: {},
  criteriaProfileId: '',
};

interface StepError {
  field: string;
  message: string;
}

/** 每一步都在前端做完整性檢查，正式資格仍由後端判定。 */
const validateStep = (
  step: number, state: WizardState, method: MsaMethodOption | null,
): StepError[] => {
  const errors: StepError[] = [];

  if (step === 0 && !state.studyType) {
    errors.push({ field: 'msa-method', message: '請選擇一種分析方法' });
  }

  if (step === 1) {
    if (!state.characteristic.trim()) {
      errors.push({ field: 'characteristic', message: '請填寫品質特性' });
    }
    if (!state.unit.trim()) {
      errors.push({ field: 'unit', message: '請填寫量測單位' });
    }
    const lsl = Number(state.lsl);
    const usl = Number(state.usl);
    if (state.lsl && state.usl && lsl >= usl) {
      errors.push({ field: 'lsl', message: '規格下限必須小於規格上限' });
    }
    if (
      state.measurementPurpose === 'product_control'
      && !state.lsl && !state.usl
      && !state.noToleranceReason.trim()
    ) {
      errors.push({
        field: 'no-tolerance-reason',
        message: '產品判定用研究必須有規格，或明確記錄無公差原因',
      });
    }
  }

  if (step === 2) {
    if (!state.primaryGaugeId) {
      errors.push({ field: 'primary-gauge', message: '請指定主量具' });
    }
    if (
      method?.needsReference
      && !state.referenceStandardId && !state.hasReferenceValues
    ) {
      errors.push({
        field: 'reference-standard',
        message: `${method.label}研究需要可追溯參考值或參考標準`,
      });
    }
  }

  if (step === 3) {
    const parts = Number(state.partCount);
    const appraisers = Number(state.appraiserCount);
    const trials = Number(state.trialCount);
    if (!Number.isInteger(parts) || parts < 1) {
      errors.push({ field: 'part-count', message: '零件數必須是正整數' });
    }
    if (!Number.isInteger(appraisers) || appraisers < 1) {
      errors.push({ field: 'appraiser-count', message: '評價人數必須是正整數' });
    }
    if (!Number.isInteger(trials) || trials < 1) {
      errors.push({ field: 'trial-count', message: '試驗次數必須是正整數' });
    }
    if (method?.needsCategories && !state.categorySet.trim()) {
      errors.push({
        field: 'category-set', message: '計數型研究必須先定義判定類別',
      });
    }
    if (method?.needsAssumptions) {
      const missing = PHYSICAL_ASSUMPTIONS.filter(
        (item) => !state.assumptions[item.key],
      );
      if (missing.length > 0) {
        errors.push({
          field: 'assumptions',
          message: `不可重複研究必須確認全部物理假設（尚缺 ${missing.length} 項）`,
        });
      }
    }
  }

  if (step === 4 && !state.criteriaProfileId) {
    errors.push({ field: 'criteria-profile', message: '請選擇判定準則設定' });
  }

  return errors;
};

export default function MsaStudyWizardPage() {
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const [step, setStep] = useState(0);
  const [state, setState] = useState<WizardState>(initialState);
  const [errors, setErrors] = useState<StepError[]>([]);
  const [planId, setPlanId] = useState<number | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const formRef = useRef<HTMLDivElement>(null);

  const equipment = useMsaEquipment({
    page: 1, page_size: 100, sort: 'equipment_no', order: 'asc',
  });
  const criteria = useMsaCriteria({
    page: 1, page_size: 100, sort: 'name', order: 'asc',
  });
  const createStudy = useCreateMsaStudy();
  const createPlan = useCreateMsaPlan();
  const freezePlan = useFreezeMsaPlan();

  const method = useMemo(() => findMethod(state.studyType), [state.studyType]);
  const equipmentItems: MeasurementEquipment[] = equipment.data?.items ?? [];
  const selectedGauge = equipmentItems.find(
    (item) => String(item.id) === state.primaryGaugeId,
  );

  const update = <K extends keyof WizardState>(key: K, value: WizardState[K]) =>
    setState((current) => ({ ...current, [key]: value }));

  const focusField = (field: string) => {
    const target = formRef.current?.querySelector<HTMLElement>(
      `[data-field="${field}"]`,
    );
    target?.focus();
    target?.scrollIntoView({ block: 'center' });
  };

  const goNext = () => {
    const found = validateStep(step, state, method);
    setErrors(found);
    if (found.length === 0) setStep((current) => current + 1);
  };

  const blockers: MsaPlanBlocker[] = useMemo(() => {
    if (!selectedGauge) return [];
    if (selectedGauge.calibration_block_reason) {
      return [{
        code: 'MSA_EQUIPMENT_BLOCKED',
        message: (
          `${selectedGauge.equipment_no} ${selectedGauge.calibration_block_reason}`
        ),
      }];
    }
    return [];
  }, [selectedGauge]);

  const submitPlan = async () => {
    if (!method) return;
    setSubmitError(null);
    try {
      const study = await createStudy.mutateAsync({
        study_type: method.studyType,
        measurement_purpose: state.measurementPurpose,
        characteristic: state.characteristic.trim(),
        unit: state.unit.trim(),
        lsl: state.lsl ? Number(state.lsl) : null,
        usl: state.usl ? Number(state.usl) : null,
        no_tolerance_reason: state.noToleranceReason.trim() || null,
        process_sigma: state.processSigma ? Number(state.processSigma) : null,
        criteria_profile_id: Number(state.criteriaProfileId),
      });
      const plan = await createPlan.mutateAsync({
        studyId: study.id,
        method_code: method.methodCode,
        part_count: Number(state.partCount),
        appraiser_count: Number(state.appraiserCount),
        trial_count: Number(state.trialCount),
        random_seed: Number(state.randomSeed),
        percent_basis: state.percentBasis,
        category_set: method.needsCategories
          ? state.categorySet.split(',').map((item) => item.trim()).filter(Boolean)
          : undefined,
        equipment: [
          {
            equipment_id: Number(state.primaryGaugeId),
            role: 'primary_gauge' as const,
          },
          ...(state.referenceStandardId ? [{
            equipment_id: Number(state.referenceStandardId),
            role: 'reference_standard' as const,
          }] : []),
        ],
        parts: Array.from(
          { length: Number(state.partCount) },
          (_unused, index) => ({ part_identifier: `件-${index + 1}` }),
        ),
        appraisers: Array.from(
          { length: Number(state.appraiserCount) },
          (_unused, index) => ({ name: `評價人${index + 1}` }),
        ),
      });
      setPlanId(plan.id);
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : '計畫尚未建立，請稍後再試。',
      );
    }
  };

  const freeze = async () => {
    if (planId == null) {
      await submitPlan();
      return;
    }
    setSubmitError(null);
    try {
      const frozen = await freezePlan.mutateAsync({ planId });
      navigate(`/msa/studies/${frozen.study_id}`);
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : '凍結未完成，請重新載入。',
      );
    }
  };

  return (
    <main className="msa-shell" aria-labelledby="msa-wizard-title">
      <header className="msa-shell__header">
        <div>
          <p className="msa-eyebrow">量測系統分析 / 研究設計</p>
          <h1 id="msa-wizard-title">建立 MSA 研究</h1>
          <p>先確認方法能回答你的問題，再往下決定設計與判定準則。</p>
        </div>
      </header>

      <ol className="msa-stepper" aria-label="研究建立步驟">
        {STEPS.map((label, index) => (
          <li
            key={label}
            aria-current={index === step ? 'step' : undefined}
            data-state={
              index === step ? 'current' : index < step ? 'complete' : 'upcoming'
            }
          >
            <span className="msa-num">{index + 1}</span>
            {label}
          </li>
        ))}
      </ol>

      {errors.length > 0 && (
        <div className="msa-state msa-state--error" role="alert">
          <p>這個步驟還有 {errors.length} 個項目需要處理：</p>
          <ul>
            {errors.map((error) => (
              <li key={error.field}>
                <button type="button" onClick={() => focusField(error.field)}>
                  {error.message}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
      {submitError && (
        <div className="msa-state msa-state--error" role="alert">
          {submitError}
        </div>
      )}

      <div className="msa-panel" ref={formRef}>
        {step === 0 && (
          <>
            <label data-field="measurement-purpose">
              量測目的
              <select
                value={state.measurementPurpose}
                onChange={(event) => update(
                  'measurementPurpose',
                  event.target.value as MsaMeasurementPurpose,
                )}
              >
                <option value="product_control">產品判定</option>
                <option value="process_control">製程管制</option>
              </select>
            </label>
            <div data-field="msa-method" tabIndex={-1}>
              <MsaMethodSelector
                value={state.studyType}
                onChange={(option) => update('studyType', option.studyType)}
              />
            </div>
          </>
        )}

        {step === 1 && (
          <div className="msa-form-grid">
            <label>
              品質特性
              <input
                data-field="characteristic"
                value={state.characteristic}
                onChange={(event) => update('characteristic', event.target.value)}
              />
            </label>
            <label>
              單位
              <input
                data-field="unit"
                value={state.unit}
                onChange={(event) => update('unit', event.target.value)}
              />
            </label>
            <label>
              規格下限
              <input
                data-field="lsl"
                inputMode="decimal"
                value={state.lsl}
                onChange={(event) => update('lsl', event.target.value)}
              />
            </label>
            <label>
              規格上限
              <input
                data-field="usl"
                inputMode="decimal"
                value={state.usl}
                onChange={(event) => update('usl', event.target.value)}
              />
            </label>
            <label className="msa-form-grid__wide">
              無公差原因（沒有規格時必填）
              <textarea
                data-field="no-tolerance-reason"
                rows={2}
                value={state.noToleranceReason}
                onChange={(event) => update(
                  'noToleranceReason', event.target.value,
                )}
              />
            </label>
            <label>
              製程標準差（選填）
              <input
                data-field="process-sigma"
                inputMode="decimal"
                value={state.processSigma}
                onChange={(event) => update('processSigma', event.target.value)}
              />
            </label>
            <label>
              百分比口徑
              <select
                data-field="percent-basis"
                value={state.percentBasis}
                onChange={(event) => update(
                  'percentBasis', event.target.value as MsaPercentBasis,
                )}
              >
                <option value="tolerance">相對公差 %Tolerance</option>
                <option value="study_variation">相對研究變差 %StudyVar</option>
                <option value="process_variation">相對製程變差 %ProcessVar</option>
              </select>
            </label>
          </div>
        )}

        {step === 2 && (
          <div className="msa-form-grid">
            <label>
              主量具
              <select
                data-field="primary-gauge"
                value={state.primaryGaugeId}
                onChange={(event) => update('primaryGaugeId', event.target.value)}
              >
                <option value="">請選擇</option>
                {equipmentItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.equipment_no}｜{item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              參考標準{method?.needsReference ? '（必要）' : '（選填）'}
              <select
                data-field="reference-standard"
                value={state.referenceStandardId}
                onChange={(event) => update(
                  'referenceStandardId', event.target.value,
                )}
              >
                <option value="">未使用</option>
                {equipmentItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.equipment_no}｜{item.name}
                  </option>
                ))}
              </select>
            </label>
            {method?.needsReference && (
              <label className="msa-form-grid__wide">
                <input
                  type="checkbox"
                  checked={state.hasReferenceValues}
                  onChange={(event) => update(
                    'hasReferenceValues', event.target.checked,
                  )}
                />
                零件已具備可追溯的參考值
              </label>
            )}
            {selectedGauge && (
              <p className="msa-form-grid__wide">
                解析度 {selectedGauge.resolution ?? '未登錄'} {selectedGauge.unit ?? ''}
                ；校驗狀態 {selectedGauge.calibration_status}
                {selectedGauge.calibration_block_reason
                  ? `；${selectedGauge.calibration_block_reason}` : ''}
                {hasPermission('calibration.view')
                  && selectedGauge.calibration_record_id !== null && (
                    <>
                      {'；'}
                      <Link to={`/calibrations/${selectedGauge.calibration_record_id}`}>
                        查看校正證據
                      </Link>
                    </>
                  )}
              </p>
            )}
          </div>
        )}

        {step === 3 && (
          <div className="msa-form-grid">
            <label>
              零件數
              <input
                data-field="part-count"
                inputMode="numeric"
                value={state.partCount}
                onChange={(event) => update('partCount', event.target.value)}
              />
            </label>
            <label>
              評價人數
              <input
                data-field="appraiser-count"
                inputMode="numeric"
                value={state.appraiserCount}
                onChange={(event) => update('appraiserCount', event.target.value)}
              />
            </label>
            <label>
              試驗次數
              <input
                data-field="trial-count"
                inputMode="numeric"
                value={state.trialCount}
                onChange={(event) => update('trialCount', event.target.value)}
              />
            </label>
            <label>
              隨機種子
              <input
                data-field="random-seed"
                inputMode="numeric"
                value={state.randomSeed}
                onChange={(event) => update('randomSeed', event.target.value)}
              />
            </label>
            {method && (
              <p className="msa-form-grid__wide">
                {method.label}建議：{method.minimumDesign}
              </p>
            )}
            {method?.needsCategories && (
              <label className="msa-form-grid__wide">
                判定類別（以逗號分隔）
                <input
                  data-field="category-set"
                  value={state.categorySet}
                  onChange={(event) => update('categorySet', event.target.value)}
                />
              </label>
            )}
            {method?.needsAssumptions && (
              <fieldset className="msa-form-grid__wide" data-field="assumptions">
                <legend>物理假設確認（全部確認才能繼續）</legend>
                {PHYSICAL_ASSUMPTIONS.map((item) => (
                  <label key={item.key}>
                    <input
                      type="checkbox"
                      checked={Boolean(state.assumptions[item.key])}
                      onChange={(event) => update('assumptions', {
                        ...state.assumptions, [item.key]: event.target.checked,
                      })}
                    />
                    {item.label}
                  </label>
                ))}
              </fieldset>
            )}
          </div>
        )}

        {step === 4 && (
          <label>
            判定準則設定
            <select
              data-field="criteria-profile"
              value={state.criteriaProfileId}
              onChange={(event) => update('criteriaProfileId', event.target.value)}
            >
              <option value="">請選擇</option>
              {(criteria.data?.items ?? []).map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}
                </option>
              ))}
            </select>
          </label>
        )}

        {step === 5 && method && (
          <MsaPlanReview
            summary={{
              methodLabel: method.label,
              methodCode: method.methodCode,
              partCount: Number(state.partCount),
              appraiserCount: Number(state.appraiserCount),
              trialCount: Number(state.trialCount),
              randomSeed: Number(state.randomSeed),
              percentBasis: state.percentBasis,
              criteriaProfileName: (criteria.data?.items ?? []).find(
                (profile) => String(profile.id) === state.criteriaProfileId,
              )?.name ?? null,
              equipment: selectedGauge ? [{
                equipmentNo: selectedGauge.equipment_no,
                name: selectedGauge.name,
                role: 'primary_gauge',
                calibrationStatus: selectedGauge.calibration_status,
                blockReason: selectedGauge.calibration_block_reason,
              }] : [],
            }}
            blockers={blockers}
            isFreezing={
              createStudy.isPending || createPlan.isPending
              || freezePlan.isPending
            }
            onFreeze={() => void freeze()}
          />
        )}
      </div>

      <nav className="msa-wizard-nav" aria-label="步驟導覽">
        <button
          type="button"
          disabled={step === 0}
          onClick={() => { setErrors([]); setStep((current) => current - 1); }}
        >
          上一步
        </button>
        {step < STEPS.length - 1 && (
          <button type="button" onClick={goNext}>下一步</button>
        )}
      </nav>
    </main>
  );
}

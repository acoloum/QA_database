import {
  type Dispatch,
  type SetStateAction,
  useEffect,
  useRef,
  useState,
} from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Button, Col, Form, Modal, Row, Table } from 'react-bootstrap';
import toast from 'react-hot-toast';

import { mechanicalApi } from '../../services/mechanicalApi';
import { apiErrorMessage, apiErrorNeedsToast } from '../../services/apiError';
import type {
  MechItem,
  MechLocation,
  MechanicalTestPayload,
  MechanicalTraceNumber,
} from '../../types';
import {
  ALL_ITEMS,
  JUDGED_ITEMS,
  LOCATIONS,
  SAMPLES,
  buildMeasurements,
  buildTraceNumbers,
  buildWaivedItems,
  duplicateTraceNumberIndexes,
  emptyGrid,
  emptyTraceNumber,
  emptyWaived,
  hydrateGrid,
  hydrateTraceNumbers,
  hydrateWaivedItems,
  removeTraceNumber,
  waivedItemsMissingReason,
  type MechGrid,
  type MechWaivedState,
} from './mechanicalPayload';
import MechanicalTraceNumberPanel from './MechanicalTraceNumberPanel';

interface MechanicalTestFormProps {
  testId: number | null;
  onClose: () => void;
  onSaved: () => void;
}

interface BasicFields {
  產品尺寸: string;
  材質: string;
  測試日期: string;
  T4溫度時間: string;
  T6溫度時間: string;
  備註: string;
}

const EMPTY_BASIC: BasicFields = {
  產品尺寸: '',
  材質: '6061-T651',
  測試日期: '',
  T4溫度時間: '',
  T6溫度時間: '',
  備註: '',
};

const cellLabel = (item: MechItem, location: MechLocation, sample: number) =>
  `${item}－${location}－取樣 ${sample}`;

const ITEM_KEYS: Record<MechItem, string> = {
  EC值: 'ec',
  硬度: 'hardness',
  抗拉強度: 'tensile',
  降伏強度: 'yield',
  伸長率: 'elongation',
};

const LOCATION_KEYS: Record<MechLocation, string> = {
  爐門: 'door',
  爐頂: 'top',
};

const measurementErrorId = (item: MechItem, location: MechLocation, sample: number, kind: 'format' | 'ng') =>
  `mechanical-measurement-${ITEM_KEYS[item]}-${LOCATION_KEYS[location]}-${sample}-${kind}-error`;

const excludedSnapshotId = (item: MechItem, location: MechLocation, sample: number) =>
  `mechanical-measurement-${ITEM_KEYS[item]}-${LOCATION_KEYS[location]}-${sample}-excluded-snapshot`;

const NUMERIC_MAX = 99999999.9999;
const DECIMAL_VALUE_PATTERN = /^[+-]?(?:(?:\d+)(?:\.(\d*))?|\.(\d+))(?:[eE]([+-]?\d+))?$/;
const DUPLICATE_TRACE_ERROR = '請移除重複的追溯編號';

const measurementValidationError = (value: string) => {
  const trimmed = value.trim();
  if (trimmed === '') return null;
  const numeric = Number(trimmed);
  if (!Number.isFinite(numeric)) return '量測值必須為有限數字';
  if (Math.abs(numeric) > NUMERIC_MAX) return '量測值超出 NUMERIC(12,4) 可儲存範圍';
  const decimalMatch = DECIMAL_VALUE_PATTERN.exec(trimmed);
  if (!decimalMatch) return '量測值必須為有限數字';
  const fractionalDigits = (decimalMatch[1] ?? decimalMatch[2] ?? '').length;
  const exponent = Number(decimalMatch[3] ?? 0);
  if (fractionalDigits - exponent > 4) return '量測值最多只能有 4 位小數';
  return null;
};

const isInvalidMeasurement = (value: string) => measurementValidationError(value) !== null;

const invalidMeasurements = (grid: MechGrid) => ALL_ITEMS.flatMap((item) => (
  LOCATIONS.flatMap((location) => SAMPLES.flatMap((sample) => (
    isInvalidMeasurement(grid[item][location][sample] ?? '') ? [{ item, location, sample }] : []
  )))
));

export default function MechanicalTestForm({ testId, onClose, onSaved }: MechanicalTestFormProps) {
  const queryClient = useQueryClient();
  const [basic, setBasic] = useState<BasicFields>(EMPTY_BASIC);
  const [vendorId, setVendorId] = useState<number | null>(null);
  const [extrusionNumbers, setExtrusionNumbers] = useState<MechanicalTraceNumber[]>([
    emptyTraceNumber(1),
  ]);
  const [t4FurnaceNumbers, setT4FurnaceNumbers] = useState<MechanicalTraceNumber[]>([
    emptyTraceNumber(1),
  ]);
  const [grid, setGrid] = useState<MechGrid>(emptyGrid());
  const [waived, setWaived] = useState<MechWaivedState>(emptyWaived());
  const [showSecond, setShowSecond] = useState(false);
  const [showEc, setShowEc] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [hydratedTestId, setHydratedTestId] = useState<number | null>(null);
  const savingRef = useRef(false);
  const extrusionDuplicateIndexes = duplicateTraceNumberIndexes(extrusionNumbers);
  const t4FurnaceDuplicateIndexes = duplicateTraceNumberIndexes(t4FurnaceNumbers);
  const hasDuplicateTraceNumbers =
    extrusionDuplicateIndexes.size > 0 || t4FurnaceDuplicateIndexes.size > 0;

  useEffect(() => {
    if (hasDuplicateTraceNumbers) return;
    setValidationError((current) => (
      current === DUPLICATE_TRACE_ERROR ? '' : current
    ));
  }, [hasDuplicateTraceNumbers]);

  const {
    data: detail,
    isLoading: isDetailLoading,
    isError: isDetailError,
    refetch: refetchDetail,
  } = useQuery({
    queryKey: ['mechanical-test', testId],
    queryFn: () => mechanicalApi.getDetail(testId as number),
    enabled: testId !== null,
  });

  const { data: vendors = [], isError: isVendorsError } = useQuery({
    queryKey: ['vendors'],
    queryFn: mechanicalApi.getVendors,
  });

  const { data: options } = useQuery({
    queryKey: ['mechanical-options', vendorId],
    queryFn: () => mechanicalApi.getOptions(vendorId as number),
    enabled: vendorId !== null,
  });

  useEffect(() => {
    if (testId === null) {
      setBasic(EMPTY_BASIC);
      setVendorId(null);
      setExtrusionNumbers([emptyTraceNumber(1)]);
      setT4FurnaceNumbers([emptyTraceNumber(1)]);
      setGrid(emptyGrid());
      setWaived(emptyWaived());
      setShowSecond(false);
      setShowEc(false);
      setValidationError('');
      setSaveError('');
      setHydratedTestId(null);
      return;
    }

    if (!detail) return;

    setBasic({
      產品尺寸: detail.main.產品尺寸,
      材質: detail.main.材質,
      測試日期: detail.main.測試日期 ?? '',
      T4溫度時間: detail.main.T4溫度時間 ?? '',
      T6溫度時間: detail.main.T6溫度時間 ?? '',
      備註: detail.main.備註 ?? '',
    });
    setVendorId(detail.main.廠商ID);
    setExtrusionNumbers(hydrateTraceNumbers(detail.extrusion_numbers));
    setT4FurnaceNumbers(hydrateTraceNumbers(detail.t4_furnace_numbers));
    setGrid(hydrateGrid(detail.measurements));
    setWaived(hydrateWaivedItems(detail.waived_items ?? []));
    setShowSecond(detail.measurements.some((measurement) => measurement.取樣序 === 2));
    setShowEc(detail.measurements.some((measurement) => measurement.量測項目 === 'EC值'));
    setHydratedTestId(testId);
  }, [detail, testId]);

  const isEditReady = testId === null || hydratedTestId === testId;

  const {
    data: limits,
    isError: isSpecError,
  } = useQuery({
    queryKey: ['mechanical-spec', basic.材質, basic.產品尺寸, vendorId],
    queryFn: () => mechanicalApi.getSpec(basic.材質, basic.產品尺寸, vendorId ?? undefined),
    enabled: Boolean(isEditReady && vendorId !== null && basic.材質 && basic.產品尺寸),
  });

  const setBasicField = <Key extends keyof BasicFields>(field: Key, value: BasicFields[Key]) => {
    setBasic((current) => ({ ...current, [field]: value }));
    setValidationError('');
  };

  const setTraceValue = (
    setter: Dispatch<SetStateAction<MechanicalTraceNumber[]>>,
    index: number,
    value: string,
  ) => {
    setter((current) => current.map((row, rowIndex) => (
      rowIndex === index ? { ...row, 編號: value } : row
    )));
    setValidationError('');
  };

  const addTraceValue = (
    setter: Dispatch<SetStateAction<MechanicalTraceNumber[]>>,
  ) => setter((current) => [...current, emptyTraceNumber(current.length + 1)]);

  const setCell = (item: MechItem, location: MechLocation, sample: number, value: string) => {
    setGrid((current) => ({
      ...current,
      [item]: {
        ...current[item],
        [location]: {
          ...current[item][location],
          [sample]: value,
        },
      },
    }));
  };

  const toggleWaived = (item: MechItem, checked: boolean) => {
    setWaived((current) => ({
      ...current,
      [item]: { waived: checked, reason: checked ? current[item].reason : '' },
    }));
    if (checked) {
      // 免測項目清空該列量測值（無法量測故不留數值）
      setGrid((current) => ({
        ...current,
        [item]: { 爐門: { 1: '', 2: '' }, 爐頂: { 1: '', 2: '' } },
      }));
    }
    setValidationError('');
  };

  const setWaivedReason = (item: MechItem, reason: string) => {
    setWaived((current) => ({ ...current, [item]: { ...current[item], reason } }));
    setValidationError('');
  };

  const cellNg = (item: MechItem, value: string) => {
    const lowerLimit = limits?.[item];
    if (lowerLimit === undefined || value.trim() === '') return false;
    const numericValue = Number(value);
    return Number.isFinite(numericValue) && numericValue < lowerLimit;
  };

  const save = async () => {
    if (savingRef.current) return;

    if (!basic.產品尺寸.trim() || !basic.材質.trim()) {
      const message = '請填寫產品尺寸與材質';
      setValidationError(message);
      toast.error(message);
      return;
    }

    const invalid = invalidMeasurements(grid);
    if (invalid.length > 0) {
      setShowSecond((current) => current || invalid.some((measurement) => measurement.sample === 2));
      setShowEc((current) => current || invalid.some((measurement) => measurement.item === 'EC值'));
      toast.error('請修正量測值格式錯誤');
      return;
    }

    if (hasDuplicateTraceNumbers) {
      const message = DUPLICATE_TRACE_ERROR;
      setValidationError(message);
      toast.error(message);
      return;
    }

    const waivedMissingReason = waivedItemsMissingReason(waived);
    if (waivedMissingReason.length > 0) {
      const message = `免測項目請填寫原因：${waivedMissingReason.join('、')}`;
      setValidationError(message);
      toast.error(message);
      return;
    }

    const payload: MechanicalTestPayload = {
      產品尺寸: basic.產品尺寸,
      材質: basic.材質,
      測試日期: basic.測試日期 || null,
      T4溫度時間: basic.T4溫度時間,
      T6溫度時間: basic.T6溫度時間,
      備註: basic.備註,
      廠商ID: vendorId,
      extrusion_numbers: buildTraceNumbers(extrusionNumbers),
      t4_furnace_numbers: buildTraceNumbers(t4FurnaceNumbers),
      measurements: buildMeasurements(grid),
      waived_items: buildWaivedItems(waived),
    };

    savingRef.current = true;
    setSaving(true);
    setSaveError('');
    try {
      if (testId === null) {
        await mechanicalApi.create(payload);
      } else {
        await mechanicalApi.update(testId, payload);
        // 更新後讓該筆詳情快取失效，避免 30 秒 staleTime 內重開編輯仍讀到舊資料
        await queryClient.invalidateQueries({ queryKey: ['mechanical-test', testId] });
      }
      toast.success('已儲存');
      onSaved();
    } catch (error) {
      const message = apiErrorMessage(error, '儲存失敗，請稍後再試');
      setSaveError(message);
      if (apiErrorNeedsToast(error)) toast.error(message);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  const samples = showSecond ? [1, 2] : [1];
  const items: MechItem[] = showEc ? [...JUDGED_ITEMS, 'EC值'] : JUDGED_ITEMS;

  if (testId !== null && isDetailError) {
    return (
      <Modal show onHide={onClose} size="lg" backdrop="static" aria-label="機械性質檢驗表單">
        <Modal.Header closeButton>
          <Modal.Title>編輯機械性質檢驗</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <Alert variant="danger" role="alert">載入機械性質檢驗資料失敗，請稍後再試</Alert>
          <Button type="button" variant="outline-primary" onClick={() => void refetchDetail()}>重新載入</Button>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={onClose}>關閉</Button>
        </Modal.Footer>
      </Modal>
    );
  }

  if (testId !== null && !isEditReady) {
    return (
      <Modal show onHide={onClose} size="lg" backdrop="static" aria-label="機械性質檢驗表單">
        <Modal.Header closeButton>
          <Modal.Title>編輯機械性質檢驗</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <div className="text-center py-4" role="status">
            {isDetailLoading ? '載入檢驗資料中…' : '正在準備檢驗資料…'}
          </div>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={onClose}>取消</Button>
        </Modal.Footer>
      </Modal>
    );
  }

  return (
    <Modal show onHide={onClose} size="lg" backdrop="static" scrollable aria-label="機械性質檢驗表單">
      <Modal.Header closeButton>
        <Modal.Title>{testId === null ? '新增機械性質檢驗' : '編輯機械性質檢驗'}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {isSpecError && (
          <Alert variant="danger" role="alert">載入機械性質規格失敗，請稍後再試</Alert>
        )}
        {isVendorsError && (
          <Alert variant="danger" role="alert">載入廠商清單失敗，請稍後再試</Alert>
        )}
        {validationError && (
          <Alert variant="danger" role="alert">{validationError}</Alert>
        )}
        {saveError && (
          <Alert variant="danger" role="alert">{saveError}</Alert>
        )}

        <Form noValidate>
          <Row className="g-3">
            <Col md={3}>
              <Form.Group controlId="mechanical-form-product-size">
                <Form.Label>產品尺寸</Form.Label>
                <Form.Control
                  required
                  maxLength={50}
                  list="mechanical-product-size-options"
                  value={basic.產品尺寸}
                  isInvalid={Boolean(validationError && !basic.產品尺寸.trim())}
                  onChange={(event) => setBasicField('產品尺寸', event.target.value)}
                />
                <datalist id="mechanical-product-size-options">
                  {(options?.product_sizes ?? []).map((value) => (
                    <option key={value} value={value}>{value}</option>
                  ))}
                </datalist>
              </Form.Group>
            </Col>
            <Col md={3}>
              <Form.Group controlId="mechanical-form-material">
                <Form.Label>材質</Form.Label>
                <Form.Control
                  required
                  maxLength={50}
                  list="mechanical-material-options"
                  value={basic.材質}
                  isInvalid={Boolean(validationError && !basic.材質.trim())}
                  onChange={(event) => setBasicField('材質', event.target.value)}
                />
                <datalist id="mechanical-material-options">
                  {(options?.materials ?? []).map((value) => (
                    <option key={value} value={value}>{value}</option>
                  ))}
                </datalist>
              </Form.Group>
            </Col>
            <Col md={3}>
              <Form.Group controlId="mechanical-form-vendor">
                <Form.Label>廠商</Form.Label>
                <Form.Select
                  aria-label="廠商"
                  value={vendorId ?? ''}
                  onChange={(event) => setVendorId(event.target.value ? Number(event.target.value) : null)}
                >
                  <option value="">未指定（不套用規格）</option>
                  {vendors.map((vendor) => (
                    <option key={vendor.id} value={vendor.id}>{vendor.name}</option>
                  ))}
                </Form.Select>
              </Form.Group>
            </Col>
            <Col md={3}>
              <Form.Group controlId="mechanical-form-test-date">
                <Form.Label>測試日期</Form.Label>
                <Form.Control
                  type="date"
                  value={basic.測試日期}
                  onChange={(event) => setBasicField('測試日期', event.target.value)}
                />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group controlId="mechanical-form-t4">
                <Form.Label>T4溫度/時間</Form.Label>
                <Form.Control
                  maxLength={100}
                  value={basic.T4溫度時間}
                  onChange={(event) => setBasicField('T4溫度時間', event.target.value)}
                />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group controlId="mechanical-form-t6">
                <Form.Label>T6溫度/時間</Form.Label>
                <Form.Control
                  maxLength={100}
                  value={basic.T6溫度時間}
                  onChange={(event) => setBasicField('T6溫度時間', event.target.value)}
                />
              </Form.Group>
            </Col>
          </Row>

          <Row className="g-3 mt-1">
            <Col md={6}>
              <MechanicalTraceNumberPanel
                idPrefix="extrusion"
                title="擠製編號"
                addLabel="新增擠製編號"
                values={extrusionNumbers}
                duplicateIndexes={extrusionDuplicateIndexes}
                onChange={(index, value) => setTraceValue(setExtrusionNumbers, index, value)}
                onAdd={() => addTraceValue(setExtrusionNumbers)}
                onRemove={(index) => setExtrusionNumbers(
                  (current) => removeTraceNumber(current, index),
                )}
              />
            </Col>
            <Col md={6}>
              <MechanicalTraceNumberPanel
                idPrefix="t4-furnace"
                title="T4爐號"
                addLabel="新增T4爐號"
                values={t4FurnaceNumbers}
                duplicateIndexes={t4FurnaceDuplicateIndexes}
                onChange={(index, value) => setTraceValue(setT4FurnaceNumbers, index, value)}
                onAdd={() => addTraceValue(setT4FurnaceNumbers)}
                onRemove={(index) => setT4FurnaceNumbers(
                  (current) => removeTraceNumber(current, index),
                )}
              />
            </Col>
          </Row>

          <div className="d-flex flex-wrap gap-3 mt-4">
            <Form.Check
              id="mechanical-show-second-sample"
              label="異常加測（第2取樣）"
              checked={showSecond}
              onChange={(event) => setShowSecond(event.target.checked)}
            />
            <Form.Check
              id="mechanical-show-ec"
              label="顯示導電度 (EC)"
              checked={showEc}
              onChange={(event) => setShowEc(event.target.checked)}
            />
          </div>

          <section className="mt-3" aria-labelledby="mechanical-measurements-heading">
            <h3 id="mechanical-measurements-heading" className="h6">量測結果</h3>
            <div className="table-responsive">
              <Table bordered size="sm" className="align-middle mb-0" style={{ minWidth: 620 }}>
                <thead className="table-secondary">
                  <tr>
                    <th scope="col">項目</th>
                    {LOCATIONS.flatMap((location) => samples.map((sample) => (
                      <th key={`${location}-${sample}`} scope="col">{location} 取樣 {sample}</th>
                    )))}
                    <th scope="col">下限</th>
                    <th scope="col">免測</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => {
                    const canWaive = item !== 'EC值';
                    const isWaived = canWaive && waived[item].waived;
                    return (
                    <tr key={item}>
                      <th scope="row">{item}</th>
                      {LOCATIONS.flatMap((location) => samples.map((sample) => {
                        const value = grid[item][location][sample] ?? '';
                        const excludedMeasurement = detail?.measurements.find((measurement) => (
                          measurement.量測項目 === item
                          && measurement.測量位置 === location
                          && measurement.取樣序 === sample
                          && measurement.排除統計
                        ));
                        const isNg = excludedMeasurement
                          ? Boolean(excludedMeasurement.是否超差)
                          : cellNg(item, value);
                        const validationMessage = measurementValidationError(value);
                        const hasFormatError = validationMessage !== null;
                        const lowerLimit = excludedMeasurement
                          ? (excludedMeasurement.下限 ?? undefined)
                          : limits?.[item];
                        const errorId = excludedMeasurement
                          ? excludedSnapshotId(item, location, sample)
                          : hasFormatError
                            ? measurementErrorId(item, location, sample, 'format')
                            : isNg ? measurementErrorId(item, location, sample, 'ng') : undefined;
                        return (
                          <td key={`${location}-${sample}`} className={isNg || hasFormatError ? 'bg-danger-subtle' : undefined}>
                            <Form.Control
                              size="sm"
                              type="text"
                              inputMode="decimal"
                              maxLength={30}
                              aria-label={cellLabel(item, location, sample)}
                              aria-invalid={hasFormatError || isNg}
                              aria-describedby={errorId}
                              aria-errormessage={errorId}
                              isInvalid={hasFormatError || isNg}
                              disabled={Boolean(excludedMeasurement) || isWaived}
                              placeholder={isWaived ? '免測' : undefined}
                              value={value}
                              onChange={(event) => setCell(item, location, sample, event.target.value)}
                            />
                            {hasFormatError ? (
                              <Form.Text id={measurementErrorId(item, location, sample, 'format')} className="text-danger" role="alert">
                                {validationMessage}
                              </Form.Text>
                            ) : !excludedMeasurement && isNg && lowerLimit !== undefined && (
                              <Form.Text id={measurementErrorId(item, location, sample, 'ng')} className="text-danger">
                                NG：低於下限 {lowerLimit}
                              </Form.Text>
                            )}
                            {excludedMeasurement && (
                              <Form.Text
                                id={excludedSnapshotId(item, location, sample)}
                                className="text-warning-emphasis"
                              >
                                已排除：{excludedMeasurement.排除原因 || '未填原因'}
                                {excludedMeasurement.排除時間 ? `（${excludedMeasurement.排除時間}）` : ''}
                                <span>
                                  ；歷史快照：下限 {excludedMeasurement.下限 ?? '無規格'}，判定 {excludedMeasurement.是否超差 ? 'NG' : 'OK'}
                                </span>
                              </Form.Text>
                            )}
                          </td>
                        );
                      }))}
                      <td>{item === 'EC值' ? '—' : (limits?.[item] ?? '—')}</td>
                      <td style={{ minWidth: 160 }}>
                        {canWaive ? (
                          <>
                            <Form.Check
                              id={`mechanical-waive-${item}`}
                              label="免測"
                              checked={isWaived}
                              onChange={(event) => toggleWaived(item, event.target.checked)}
                            />
                            {isWaived && (
                              <Form.Control
                                size="sm"
                                className="mt-1"
                                maxLength={200}
                                placeholder="免測原因（必填）"
                                aria-label={`${item}免測原因`}
                                isInvalid={!waived[item].reason.trim()}
                                value={waived[item].reason}
                                onChange={(event) => setWaivedReason(item, event.target.value)}
                              />
                            )}
                          </>
                        ) : '—'}
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </Table>
            </div>
          </section>

          <Form.Group className="mt-3" controlId="mechanical-form-notes">
            <Form.Label>備註</Form.Label>
            <Form.Control
              as="textarea"
              rows={2}
              value={basic.備註}
              onChange={(event) => setBasicField('備註', event.target.value)}
            />
          </Form.Group>
        </Form>
      </Modal.Body>
      <Modal.Footer>
        <Button variant="secondary" onClick={onClose}>取消</Button>
        <Button variant="primary" disabled={saving || isDetailLoading} onClick={save}>
          {saving ? '儲存中…' : '儲存'}
        </Button>
      </Modal.Footer>
    </Modal>
  );
}

import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Col, Form, Modal, Row, Table } from 'react-bootstrap';
import toast from 'react-hot-toast';

import { mechanicalApi } from '../../services/mechanicalApi';
import type { MechItem, MechLocation, MechanicalBatch, MechanicalTestPayload } from '../../types';
import {
  JUDGED_ITEMS,
  LOCATIONS,
  buildMeasurements,
  emptyGrid,
  hydrateGrid,
  type MechGrid,
} from './mechanicalPayload';

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

const emptyBatch = (sequence: number): MechanicalBatch => ({
  序號: sequence,
  擠製編號: '',
  爐具編號: '',
});

const cellLabel = (item: MechItem, location: MechLocation, sample: number) =>
  `${item}－${location}－取樣 ${sample}`;

export default function MechanicalTestForm({ testId, onClose, onSaved }: MechanicalTestFormProps) {
  const [basic, setBasic] = useState<BasicFields>(EMPTY_BASIC);
  const [vendorId, setVendorId] = useState<number | null>(null);
  const [batches, setBatches] = useState<MechanicalBatch[]>([emptyBatch(1)]);
  const [grid, setGrid] = useState<MechGrid>(emptyGrid());
  const [showSecond, setShowSecond] = useState(false);
  const [showEc, setShowEc] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [saveError, setSaveError] = useState('');

  const {
    data: detail,
    isLoading: isDetailLoading,
    isError: isDetailError,
  } = useQuery({
    queryKey: ['mechanical-test', testId],
    queryFn: () => mechanicalApi.getDetail(testId as number),
    enabled: testId !== null,
  });

  useEffect(() => {
    if (testId === null) {
      setBasic(EMPTY_BASIC);
      setVendorId(null);
      setBatches([emptyBatch(1)]);
      setGrid(emptyGrid());
      setShowSecond(false);
      setShowEc(false);
      setValidationError('');
      setSaveError('');
      return;
    }

    if (!detail) return;

    setBasic({
      產品尺寸: detail.main.產品尺寸,
      材質: detail.main.材質,
      測試日期: detail.main.測試日期 ?? '',
      T4溫度時間: detail.main.T4溫度時間,
      T6溫度時間: detail.main.T6溫度時間,
      備註: detail.main.備註,
    });
    // 編輯表單沒有廠商欄位，仍須保留原關聯以維持規格追溯性。
    setVendorId(detail.main.廠商ID);
    setBatches(detail.batches.length > 0 ? detail.batches : [emptyBatch(1)]);
    setGrid(hydrateGrid(detail.measurements));
    setShowSecond(detail.measurements.some((measurement) => measurement.取樣序 === 2));
    setShowEc(detail.measurements.some((measurement) => measurement.量測項目 === 'EC值'));
  }, [detail, testId]);

  const {
    data: limits,
    isError: isSpecError,
  } = useQuery({
    queryKey: ['mechanical-spec', basic.材質, basic.產品尺寸, vendorId],
    queryFn: () => mechanicalApi.getSpec(basic.材質, basic.產品尺寸, vendorId ?? undefined),
    enabled: Boolean(basic.材質 && basic.產品尺寸),
  });

  const setBasicField = <Key extends keyof BasicFields>(field: Key, value: BasicFields[Key]) => {
    setBasic((current) => ({ ...current, [field]: value }));
    setValidationError('');
  };

  const setBatchField = (index: number, field: '擠製編號' | '爐具編號', value: string) => {
    setBatches((current) => current.map((batch, batchIndex) => (
      batchIndex === index ? { ...batch, [field]: value } : batch
    )));
  };

  const addBatch = () => setBatches((current) => [...current, emptyBatch(current.length + 1)]);

  const removeBatch = (index: number) => {
    setBatches((current) => {
      if (current.length <= 1) return current;
      return current
        .filter((_, batchIndex) => batchIndex !== index)
        .map((batch, batchIndex) => ({ ...batch, 序號: batchIndex + 1 }));
    });
  };

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

  const cellNg = (item: MechItem, value: string) => {
    const lowerLimit = limits?.[item];
    if (lowerLimit === undefined || value.trim() === '') return false;
    const numericValue = Number(value);
    return Number.isFinite(numericValue) && numericValue < lowerLimit;
  };

  const save = async () => {
    if (!basic.產品尺寸.trim() || !basic.材質.trim()) {
      const message = '請填寫產品尺寸與材質';
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
      batches: batches.filter((batch) => batch.擠製編號.trim() || batch.爐具編號.trim()),
      measurements: buildMeasurements(grid),
    };
    if (testId !== null) payload.廠商ID = vendorId;

    setSaving(true);
    setSaveError('');
    try {
      if (testId === null) await mechanicalApi.create(payload);
      else await mechanicalApi.update(testId, payload);
      toast.success('已儲存');
      onSaved();
    } catch {
      const message = '儲存失敗，請稍後再試';
      setSaveError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const samples = showSecond ? [1, 2] : [1];
  const items: MechItem[] = showEc ? [...JUDGED_ITEMS, 'EC值'] : JUDGED_ITEMS;

  return (
    <Modal show onHide={onClose} size="lg" backdrop="static" scrollable aria-label="機械性質檢驗表單">
      <Modal.Header closeButton>
        <Modal.Title>{testId === null ? '新增機械性質檢驗' : '編輯機械性質檢驗'}</Modal.Title>
      </Modal.Header>
      <Modal.Body>
        {isDetailLoading && (
          <div className="text-center py-4" role="status">載入檢驗資料中…</div>
        )}
        {isDetailError && (
          <Alert variant="danger" role="alert">載入機械性質檢驗資料失敗，請稍後再試</Alert>
        )}
        {isSpecError && (
          <Alert variant="danger" role="alert">載入機械性質規格失敗，請稍後再試</Alert>
        )}
        {validationError && (
          <Alert variant="danger" role="alert">{validationError}</Alert>
        )}
        {saveError && (
          <Alert variant="danger" role="alert">{saveError}</Alert>
        )}

        <Form noValidate>
          <Row className="g-3">
            <Col md={4}>
              <Form.Group controlId="mechanical-form-product-size">
                <Form.Label>產品尺寸</Form.Label>
                <Form.Control
                  required
                  value={basic.產品尺寸}
                  isInvalid={Boolean(validationError && !basic.產品尺寸.trim())}
                  onChange={(event) => setBasicField('產品尺寸', event.target.value)}
                />
              </Form.Group>
            </Col>
            <Col md={4}>
              <Form.Group controlId="mechanical-form-material">
                <Form.Label>材質</Form.Label>
                <Form.Control
                  required
                  value={basic.材質}
                  isInvalid={Boolean(validationError && !basic.材質.trim())}
                  onChange={(event) => setBasicField('材質', event.target.value)}
                />
              </Form.Group>
            </Col>
            <Col md={4}>
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
                  value={basic.T4溫度時間}
                  onChange={(event) => setBasicField('T4溫度時間', event.target.value)}
                />
              </Form.Group>
            </Col>
            <Col md={6}>
              <Form.Group controlId="mechanical-form-t6">
                <Form.Label>T6溫度/時間</Form.Label>
                <Form.Control
                  value={basic.T6溫度時間}
                  onChange={(event) => setBasicField('T6溫度時間', event.target.value)}
                />
              </Form.Group>
            </Col>
          </Row>

          <section className="mt-4" aria-labelledby="mechanical-batches-heading">
            <div className="d-flex justify-content-between align-items-center mb-2">
              <h3 id="mechanical-batches-heading" className="h6 mb-0">擠製編號／爐具編號</h3>
              <Button type="button" size="sm" variant="outline-primary" onClick={addBatch}>
                新增一組
              </Button>
            </div>
            {batches.map((batch, index) => (
              <Row key={`${batch.序號}-${index}`} className="g-2 align-items-end mb-2">
                <Col xs="auto" className="pb-1 text-muted">{index + 1}.</Col>
                <Col>
                  <Form.Control
                    aria-label={`第 ${index + 1} 組擠製編號`}
                    placeholder="擠製編號"
                    value={batch.擠製編號}
                    onChange={(event) => setBatchField(index, '擠製編號', event.target.value)}
                  />
                </Col>
                <Col>
                  <Form.Control
                    aria-label={`第 ${index + 1} 組爐具編號`}
                    placeholder="爐具編號"
                    value={batch.爐具編號}
                    onChange={(event) => setBatchField(index, '爐具編號', event.target.value)}
                  />
                </Col>
                <Col xs="auto">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline-danger"
                    aria-label="刪除批次"
                    disabled={batches.length <= 1}
                    onClick={() => removeBatch(index)}
                  >
                    刪除
                  </Button>
                </Col>
              </Row>
            ))}
          </section>

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
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item}>
                      <th scope="row">{item}</th>
                      {LOCATIONS.flatMap((location) => samples.map((sample) => {
                        const value = grid[item][location][sample] ?? '';
                        const isNg = cellNg(item, value);
                        const lowerLimit = limits?.[item];
                        return (
                          <td key={`${location}-${sample}`} className={isNg ? 'bg-danger-subtle' : undefined}>
                            <Form.Control
                              size="sm"
                              type="text"
                              inputMode="decimal"
                              aria-label={cellLabel(item, location, sample)}
                              aria-invalid={isNg}
                              isInvalid={isNg}
                              value={value}
                              onChange={(event) => setCell(item, location, sample, event.target.value)}
                            />
                            {isNg && lowerLimit !== undefined && (
                              <Form.Text className="text-danger">NG：低於下限 {lowerLimit}</Form.Text>
                            )}
                          </td>
                        );
                      }))}
                      <td>{item === 'EC值' ? '—' : (limits?.[item] ?? '—')}</td>
                    </tr>
                  ))}
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

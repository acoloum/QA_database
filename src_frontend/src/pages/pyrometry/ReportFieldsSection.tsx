import type { Dispatch, SetStateAction } from 'react';
import { Button, Col, Form, Row, Table } from 'react-bootstrap';

import { emptyItemRow, type ItemRow } from './pyrometryFormUtils';
import type { PyrometryTestType } from './pyrometryPayload';

interface Props {
  showReport: boolean;
  testType: PyrometryTestType;
  furnaceId: string;
  testDate: string;
  setpoint: string;
  reportMeta: Record<string, string>;
  itemRows: ItemRow[];
  onToggle: () => void;
  onInheritFromTus: () => void;
  onSetReportMeta: Dispatch<SetStateAction<Record<string, string>>>;
  onSetItemRows: Dispatch<SetStateAction<ItemRow[]>>;
  onUpdateItemRow: (idx: number, key: keyof ItemRow, value: string) => void;
}

const REPORT_META_FIELDS = ['客戶名稱', '預估總重量', '控制器型號', '控制器設定值', '控制器補償', '溫濕度', '執行單位', '核准', '製表'] as const;

const ReportFieldsSection = ({
  showReport,
  testType,
  furnaceId,
  testDate,
  setpoint,
  reportMeta,
  itemRows,
  onToggle,
  onInheritFromTus,
  onSetReportMeta,
  onSetItemRows,
  onUpdateItemRow,
}: Props) => (
  <div className="mb-3">
    <Button size="sm" variant="outline-secondary" className="mb-2" onClick={onToggle}>
      {showReport ? '隱藏報告欄位' : '報告欄位（客戶/料號/核准等，QRA073/074）'}
    </Button>
    {showReport && (
      <div className="p-2 bg-light rounded border">
        {testType === 'SAT' && (
          <div className="mb-2">
            <Button
              size="sm"
              variant="outline-info"
              disabled={!furnaceId || !testDate}
              onClick={onInheritFromTus}
            >
              從同日 TUS 繼承報告資料
            </Button>
            {(!furnaceId || !testDate) && (
              <span className="text-muted ms-2" style={{ fontSize: 12 }}>（需先填寫爐號與測試日期）</span>
            )}
          </div>
        )}
        <Row className="g-2 mb-2">
          <Col md={3}>
            <Form.Label className="mb-0" style={{ fontSize: 12 }}>爐具測試溫度 (°C)</Form.Label>
            <Form.Control size="sm" value={setpoint || ''} readOnly className="bg-white" aria-label="爐具測試溫度" />
          </Col>
          <Col md={4}>
            <Form.Label className="mb-0" style={{ fontSize: 12 }}>測試條件</Form.Label>
            <div className="d-flex gap-3 pt-1">
              {['空爐', '滿爐', '其他'].map(opt => (
                <Form.Check
                  key={opt}
                  type="radio"
                  inline
                  label={opt}
                  aria-label={opt}
                  checked={reportMeta['測試條件'] === opt}
                  onChange={() => onSetReportMeta(prev => ({ ...prev, 測試條件: opt }))}
                />
              ))}
            </div>
          </Col>
          {REPORT_META_FIELDS.map(key => (
            <Col md={3} key={key}>
              <Form.Label className="mb-0" style={{ fontSize: 12 }}>{key}</Form.Label>
              <Form.Control
                size="sm"
                value={reportMeta[key] || ''}
                aria-label={key}
                onChange={e => onSetReportMeta(prev => ({ ...prev, [key]: e.target.value }))}
              />
            </Col>
          ))}
        </Row>
        <Form.Label className="mb-1 fw-semibold" style={{ fontSize: 12 }}>工件明細</Form.Label>
        <Table bordered size="sm" className="mb-1">
          <thead className="table-secondary">
            <tr>
              <th>工件料號</th>
              <th>生產批號</th>
              <th style={{ width: 130 }}>內外徑尺寸</th>
              <th style={{ width: 100 }}>支數</th>
              <th style={{ width: 36 }}></th>
            </tr>
          </thead>
          <tbody>
            {itemRows.map((row, idx) => (
              <tr key={idx}>
                <td>
                  <Form.Control
                    size="sm"
                    value={row.工件料號}
                    aria-label={`工件料號 ${idx + 1}`}
                    onChange={e => onUpdateItemRow(idx, '工件料號', e.target.value)}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    value={row.生產批號}
                    aria-label={`生產批號 ${idx + 1}`}
                    onChange={e => onUpdateItemRow(idx, '生產批號', e.target.value)}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    value={row.內外徑尺寸}
                    aria-label={`內外徑尺寸 ${idx + 1}`}
                    onChange={e => onUpdateItemRow(idx, '內外徑尺寸', e.target.value)}
                  />
                </td>
                <td>
                  <Form.Control
                    size="sm"
                    value={row.支數}
                    aria-label={`支數 ${idx + 1}`}
                    onChange={e => onUpdateItemRow(idx, '支數', e.target.value)}
                  />
                </td>
                <td className="text-center align-middle">
                  {itemRows.length > 1 && (
                    <Button
                      size="sm"
                      variant="outline-danger"
                      onClick={() => onSetItemRows(prev => prev.filter((_, i) => i !== idx))}
                    >
                      ×
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
        <Button size="sm" variant="outline-secondary" onClick={() => onSetItemRows(prev => [...prev, emptyItemRow()])}>
          + 新增工件
        </Button>
      </div>
    )}
  </div>
);

export default ReportFieldsSection;

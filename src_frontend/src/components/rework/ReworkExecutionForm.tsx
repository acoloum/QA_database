import { Form, Row, Col } from 'react-bootstrap';
import type { Inspector } from '../../types';
import type { ReworkExecutionFormValues } from './reworkFormPayload';

interface ReworkExecutionFormProps {
    inspectors: Inspector[];
    values: ReworkExecutionFormValues;
    onChange: (field: keyof ReworkExecutionFormValues, value: string) => void;
    responsibleLabel: string;
}

const ReworkExecutionForm = ({
    inspectors,
    values,
    onChange,
    responsibleLabel,
}: ReworkExecutionFormProps) => (
    <Form>
        <Row>
            <Col md={6}>
                <Form.Group className="mb-3">
                    <Form.Label>{responsibleLabel}</Form.Label>
                    <Form.Select
                        aria-label={responsibleLabel}
                        value={values.responsiblePerson}
                        onChange={(e) => onChange('responsiblePerson', e.target.value)}
                    >
                        <option value="">請選擇</option>
                        {inspectors.map(i => (
                            <option key={i.id} value={i.name}>{i.name}</option>
                        ))}
                    </Form.Select>
                </Form.Group>
            </Col>
            <Col md={6}>
                <Form.Group className="mb-3">
                    <Form.Label>執行部門</Form.Label>
                    <Form.Select
                        aria-label="執行部門"
                        value={values.department}
                        onChange={(e) => onChange('department', e.target.value)}
                    >
                        <option value="製造部">製造部</option>
                        <option value="品保部">品保部</option>
                        <option value="工程部">工程部</option>
                    </Form.Select>
                </Form.Group>
            </Col>
        </Row>

        <Row>
            <Col md={6}>
                <Form.Group className="mb-3">
                    <Form.Label>開始時間</Form.Label>
                    <Form.Control
                        aria-label="開始時間"
                        type="datetime-local"
                        value={values.startTime}
                        onChange={(e) => onChange('startTime', e.target.value)}
                    />
                </Form.Group>
            </Col>
            <Col md={6}>
                <Form.Group className="mb-3">
                    <Form.Label>預計完成時間</Form.Label>
                    <Form.Control
                        aria-label="預計完成時間"
                        type="datetime-local"
                        value={values.expectedEndTime}
                        onChange={(e) => onChange('expectedEndTime', e.target.value)}
                    />
                </Form.Group>
            </Col>
        </Row>

        <Row>
            <Col md={6}>
                <Form.Group className="mb-3">
                    <Form.Label>實際完成時間</Form.Label>
                    <Form.Control
                        aria-label="實際完成時間"
                        type="datetime-local"
                        value={values.actualEndTime}
                        onChange={(e) => onChange('actualEndTime', e.target.value)}
                    />
                </Form.Group>
            </Col>
            <Col md={6}>
                <Form.Group className="mb-3">
                    <Form.Label>使用設備</Form.Label>
                    <Form.Control
                        aria-label="使用設備"
                        value={values.equipment}
                        onChange={(e) => onChange('equipment', e.target.value)}
                        placeholder="設備名稱"
                    />
                </Form.Group>
            </Col>
        </Row>

        <Row>
            <Col md={6}>
                <Form.Group className="mb-3">
                    <Form.Label>重工方式</Form.Label>
                    <Form.Control
                        aria-label="重工方式"
                        value={values.method}
                        onChange={(e) => onChange('method', e.target.value)}
                        placeholder="重工方式描述"
                    />
                </Form.Group>
            </Col>
            <Col md={6}>
                <Form.Group className="mb-3">
                    <Form.Label>SOP編號</Form.Label>
                    <Form.Control
                        aria-label="SOP編號"
                        value={values.sopNo}
                        onChange={(e) => onChange('sopNo', e.target.value)}
                        placeholder="SOP-XXX"
                    />
                </Form.Group>
            </Col>
        </Row>

        <Form.Group className="mb-3">
            <Form.Label>耗材記錄</Form.Label>
            <Form.Control
                aria-label="耗材記錄"
                as="textarea"
                rows={2}
                value={values.consumables}
                onChange={(e) => onChange('consumables', e.target.value)}
                placeholder="使用的耗材記錄"
            />
        </Form.Group>

        <Row>
            <Col md={4}>
                <Form.Group className="mb-3">
                    <Form.Label>完成數量</Form.Label>
                    <Form.Control
                        aria-label="完成數量"
                        type="number"
                        value={values.completedQty}
                        onChange={(e) => onChange('completedQty', e.target.value)}
                    />
                </Form.Group>
            </Col>
            <Col md={4}>
                <Form.Group className="mb-3">
                    <Form.Label>不良數量</Form.Label>
                    <Form.Control
                        aria-label="不良數量"
                        type="number"
                        value={values.defectQty}
                        onChange={(e) => onChange('defectQty', e.target.value)}
                    />
                </Form.Group>
            </Col>
            <Col md={4}>
                <Form.Group className="mb-3">
                    <Form.Label>協同人員</Form.Label>
                    <Form.Control
                        aria-label="協同人員"
                        value={values.collaborators}
                        onChange={(e) => onChange('collaborators', e.target.value)}
                        placeholder="協同人員"
                    />
                </Form.Group>
            </Col>
        </Row>

        <Form.Group className="mb-3">
            <Form.Label>執行狀況</Form.Label>
            <Form.Control
                aria-label="執行狀況"
                as="textarea"
                rows={2}
                value={values.status}
                onChange={(e) => onChange('status', e.target.value)}
                placeholder="執行狀況描述"
            />
        </Form.Group>

        <Form.Group className="mb-3">
            <Form.Label>異常狀況</Form.Label>
            <Form.Control
                aria-label="異常狀況"
                as="textarea"
                rows={2}
                value={values.abnormalStatus}
                onChange={(e) => onChange('abnormalStatus', e.target.value)}
                placeholder="異常狀況描述"
            />
        </Form.Group>
    </Form>
);

export default ReworkExecutionForm;

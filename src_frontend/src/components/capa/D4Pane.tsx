import { Button, Form, InputGroup, Row, Col, Table, Spinner } from 'react-bootstrap';

export interface FiveWhyRow {
    why: string;
    answer: string;
}

export interface D4PaneProps {
    tool: string;
    setTool: (v: string) => void;
    fiveWhy: FiveWhyRow[];
    setFiveWhy: (v: FiveWhyRow[]) => void;
    fishbone: Record<string, string[]>;
    setFishbone: (v: Record<string, string[]>) => void;
    rootCause: string;
    setRootCause: (v: string) => void;
    readonly?: boolean;
    onSave: () => void;
    saving: boolean;
}

const SIX_M = [
    { key: 'man', label: '人員（Man）' },
    { key: 'machine', label: '機器（Machine）' },
    { key: 'material', label: '材料（Material）' },
    { key: 'method', label: '方法（Method）' },
    { key: 'measurement', label: '量測（Measurement）' },
    { key: 'environment', label: '環境（Environment）' },
];

const SaveBar = ({ onSave, saving, readonly }: { onSave: () => void; saving: boolean; readonly?: boolean }) => {
    if (readonly) return null;
    return (
        <div className="d-flex justify-content-end mt-3">
            <Button variant="primary" onClick={onSave} disabled={saving}>
                {saving ? (
                    <>
                        <Spinner size="sm" className="me-2" />儲存中
                    </>
                ) : '儲存此步驟'}
            </Button>
        </div>
    );
};

const FiveWhyEditor = ({ value, onChange, readonly }: {
    value: FiveWhyRow[];
    onChange: (rows: FiveWhyRow[]) => void;
    readonly?: boolean;
}) => {
    const rows: FiveWhyRow[] = value?.length >= 3
        ? value
        : Array.from({ length: 3 }, (_, i) => value?.[i] ?? { why: '', answer: '' });

    const update = (idx: number, field: keyof FiveWhyRow, val: string) => {
        const next = rows.map((r, i) => i === idx ? { ...r, [field]: val } : r);
        onChange(next);
    };

    const addRow = () => {
        if (rows.length < 7) onChange([...rows, { why: '', answer: '' }]);
    };

    const removeRow = () => {
        if (rows.length > 3) onChange(rows.slice(0, -1));
    };

    return (
        <div>
            <Table size="sm" bordered className="mb-2">
                <thead className="table-light">
                    <tr>
                        <th style={{ width: '60px' }}>#</th>
                        <th>為什麼（Why）</th>
                        <th>原因（Answer）</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((r, i) => (
                        <tr key={i}>
                            <td className="text-center fw-bold text-primary">Why {i + 1}</td>
                            <td>
                                <Form.Control
                                    size="sm"
                                    aria-label={`Why ${i + 1} 問題`}
                                    value={r.why}
                                    onChange={e => update(i, 'why', e.target.value)}
                                    placeholder="請輸入為什麼…"
                                    disabled={readonly}
                                />
                            </td>
                            <td>
                                <Form.Control
                                    size="sm"
                                    aria-label={`Why ${i + 1} 原因`}
                                    value={r.answer}
                                    onChange={e => update(i, 'answer', e.target.value)}
                                    placeholder="請輸入原因…"
                                    disabled={readonly}
                                />
                            </td>
                        </tr>
                    ))}
                </tbody>
            </Table>
            {!readonly && (
                <div className="d-flex gap-2">
                    <Button size="sm" variant="outline-secondary" onClick={removeRow} disabled={rows.length <= 3}>
                        <i className="bi bi-dash" /> 移除一層
                    </Button>
                    <Button size="sm" variant="outline-primary" onClick={addRow} disabled={rows.length >= 7}>
                        <i className="bi bi-plus" /> 增加一層（最多 7）
                    </Button>
                </div>
            )}
        </div>
    );
};

const FishboneEditor = ({ value, onChange, readonly }: {
    value: Record<string, string[]>;
    onChange: (val: Record<string, string[]>) => void;
    readonly?: boolean;
}) => {
    const data: Record<string, string[]> = value ?? {};

    const updateItem = (m: string, idx: number, val: string) => {
        const arr = [...(data[m] ?? [])];
        arr[idx] = val;
        onChange({ ...data, [m]: arr });
    };

    const addItem = (m: string) => {
        const arr = [...(data[m] ?? []), ''];
        onChange({ ...data, [m]: arr });
    };

    const removeItem = (m: string, idx: number) => {
        const arr = (data[m] ?? []).filter((_, i) => i !== idx);
        onChange({ ...data, [m]: arr });
    };

    return (
        <Row className="g-3">
            {SIX_M.map(({ key, label }) => (
                <Col md={4} key={key}>
                    <div className="border rounded p-2">
                        <div className="fw-semibold small mb-2 text-primary">{label}</div>
                        {(data[key] ?? []).map((item, idx) => (
                            <InputGroup size="sm" className="mb-1" key={idx}>
                                <Form.Control
                                    value={item}
                                    aria-label={`${label} 原因 ${idx + 1}`}
                                    onChange={e => updateItem(key, idx, e.target.value)}
                                    placeholder="原因…"
                                    disabled={readonly}
                                />
                                {!readonly && (
                                    <Button
                                        variant="outline-danger"
                                        onClick={() => removeItem(key, idx)}
                                        tabIndex={-1}
                                        aria-label="刪除此原因"
                                    >
                                        <i className="bi bi-x-lg" />
                                    </Button>
                                )}
                            </InputGroup>
                        ))}
                        {!readonly && (
                            <Button size="sm" variant="outline-secondary" className="w-100 mt-1" onClick={() => addItem(key)}>
                                <i className="bi bi-plus" /> 新增
                            </Button>
                        )}
                    </div>
                </Col>
            ))}
        </Row>
    );
};

const D4Pane = ({
    tool,
    setTool,
    fiveWhy,
    setFiveWhy,
    fishbone,
    setFishbone,
    rootCause,
    setRootCause,
    readonly,
    onSave,
    saving,
}: D4PaneProps) => (
    <div>
        <Form.Group className="mb-3">
            <Form.Label className="fw-semibold">分析工具</Form.Label>
            <div className="d-flex gap-3">
                <Form.Check
                    type="radio"
                    id="tool-5why"
                    label="5 Why"
                    value="5why"
                    checked={tool === '5why'}
                    onChange={() => setTool('5why')}
                    disabled={readonly}
                />
                <Form.Check
                    type="radio"
                    id="tool-fishbone"
                    label="魚骨圖（6M）"
                    value="fishbone"
                    checked={tool === 'fishbone'}
                    onChange={() => setTool('fishbone')}
                    disabled={readonly}
                />
            </div>
        </Form.Group>

        {tool === '5why' ? (
            <FiveWhyEditor value={fiveWhy} onChange={setFiveWhy} readonly={readonly} />
        ) : (
            <FishboneEditor value={fishbone} onChange={setFishbone} readonly={readonly} />
        )}

        <Form.Group controlId="capa-d4-root-cause" className="mt-3">
            <Form.Label className="fw-semibold">根本原因（彙整）</Form.Label>
            <Form.Control
                as="textarea"
                rows={3}
                value={rootCause}
                onChange={e => setRootCause(e.target.value)}
                disabled={readonly}
                placeholder="請彙整根本原因…"
            />
        </Form.Group>

        <SaveBar onSave={onSave} saving={saving} readonly={readonly} />
    </div>
);

export default D4Pane;

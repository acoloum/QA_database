import { Alert, Badge, Card, Col, Row } from 'react-bootstrap';
import { formatPPM, getPpmGrade } from '../../utils/spcAnalysis';
import type { ProcessCapability } from '../../types';

interface ProcessCapabilityCardProps {
    processCapability?: ProcessCapability | null;
    statsItem: string;
}

/** 四象限狀態（AIAG-VDA 2026 圖 9-26）：穩定性 × 指數達標 */
const quadrantBadge = (pc: ProcessCapability) => {
    const stable = pc.stability_stable;
    const ok = pc.achieved;
    if (stable === true && ok) return { text: 'I：具能力且穩定', bg: '#d4edda', color: '#155724' };
    if (stable === true && !ok) return { text: 'III：無能力但穩定', bg: '#fff3cd', color: '#856404' };
    if (stable === false && ok) return { text: 'II：具績效但不穩定', bg: '#fff3cd', color: '#856404' };
    if (stable === false && !ok) return { text: 'IV：無績效且不穩定', bg: '#f8d7da', color: '#721c24' };
    return { text: '穩定性無法驗證', bg: '#e9ecef', color: '#6c757d' };
};

const ProcessCapabilityCard = ({ processCapability, statsItem }: ProcessCapabilityCardProps) => {
    const pc = processCapability;
    if (!pc?.available) {
        return (
            <Card className="mb-4" style={{ border: '2px solid #dee2e6' }}>
                <Card.Body>
                    <h5 className="mb-3">製程能力指標</h5>
                    {pc?.reason === 'insufficient_data' ? (
                        <Alert variant="warning" className="mb-0">
                            <i className="bi bi-exclamation-triangle me-2"></i>
                            資料筆數不足 — 「<strong>{statsItem}</strong>」僅有 <strong>{pc.valid_count ?? 0}</strong> 筆有效數據，
                            需要至少 <strong>5 筆</strong>才能進行分析。
                        </Alert>
                    ) : (
                        <Alert variant="info" className="mb-0">
                            <i className="bi bi-info-circle me-2"></i>
                            無法計算指數 — 需要在<strong>公差管理</strong>中設定「<strong>{statsItem}</strong>」的規格界限。
                        </Alert>
                    )}
                </Card.Body>
            </Card>
        );
    }

    const isCapability = pc.applicable === 'capability';
    const method = pc.method ?? 'G';
    const oneSided = pc.one_sided;
    // 依適用族取值：能力(C) 或 績效(P)
    const pkValue = isCapability ? pc.cpk : pc.ppk;
    const pValue = isCapability ? pc.cp : pc.pp;
    const pkLabel = `${isCapability ? 'Cpk' : 'Ppk'}.${method}`;
    const pLabel = `${isCapability ? 'Cp' : 'Pp'}.${method}`;
    const targets = pc.targets;
    const ppmData = pc.ppm || null;
    const ppmGrade = ppmData?.total != null ? getPpmGrade(ppmData.total) : null;
    const formatOptionalPpm = (value: number | null) => value == null ? '—' : formatPPM(value);
    const quad = quadrantBadge(pc);

    return (
        <Card className="mb-4" style={{ border: '2px solid #dee2e6' }}>
            <Card.Body>
                <div className="d-flex align-items-center gap-2 mb-3 flex-wrap">
                    <h5 className="mb-0">製程{isCapability ? '能力' : '績效'}指標</h5>
                    <Badge style={{ backgroundColor: quad.bg, color: quad.color }}>{quad.text}</Badge>
                    {pc.stability_stable === true && <Badge bg="success">穩定（統計受控）→ 能力指數</Badge>}
                    {pc.stability_stable === false && <Badge bg="warning" text="dark">不穩定 → 僅報告績效指數</Badge>}
                    {pc.preliminary && <Badge bg="secondary">初步值（樣本數未達 n≥125 / k≥25）</Badge>}
                </div>
                {oneSided && (
                    <Alert variant="info" className="py-1 px-2 mb-2 small">
                        單側{oneSided === 'lower' ? '下限' : '上限'}規格：僅計算對應側指數（AIAG-VDA §6.8.2.2）
                    </Alert>
                )}
                <Row className="text-center">
                    {!oneSided && (
                        <Col>
                            <div className="text-muted small">{pLabel}</div>
                            <div className="h4">{pValue?.toFixed(3) ?? 'N/A'}</div>
                            <div className="text-muted small">目標 ≥ {targets?.p_target?.toFixed(2) ?? '—'}</div>
                        </Col>
                    )}
                    <Col>
                        <div className="text-muted small">{pkLabel}</div>
                        <div className="h3 mb-1">{pkValue?.toFixed(3) ?? 'N/A'}</div>
                        {targets && pkValue != null && (
                            <Badge bg={pc.achieved ? 'success' : 'danger'}>
                                {pc.achieved ? '達標' : '未達標'}（目標 ≥ {targets.pk_target.toFixed(2)}）
                            </Badge>
                        )}
                    </Col>
                    <Col>
                        <div className="text-muted small">特性重要度</div>
                        <div className="h5">{targets?.class ?? '其他'}</div>
                        {targets?.adjusted && (
                            <div className="text-muted small">目標值已依樣本數上修（{targets.confidence}）</div>
                        )}
                        {targets?.insufficient_sample && (
                            <div className="text-danger small">樣本 &lt; 75，結果僅供參考</div>
                        )}
                    </Col>
                    <Col>
                        <div className="text-muted small">Cwk（組內參考）</div>
                        <div className="h5">{pc.cwk?.toFixed(3) ?? '—'}</div>
                    </Col>
                    <Col>
                        <div className="text-muted small">USL</div>
                        <div className="h5" style={{ color: '#e83e8c' }}>{pc.usl != null ? pc.usl.toFixed(3) : '—'}</div>
                    </Col>
                    <Col>
                        <div className="text-muted small">LSL</div>
                        <div className="h5" style={{ color: '#e83e8c' }}>{pc.lsl != null ? pc.lsl.toFixed(3) : '—'}</div>
                    </Col>
                </Row>

                {ppmData && (
                    <div className="mt-3 pt-3 border-top">
                        <Row className="text-center align-items-center">
                            <Col xs="auto"><strong>PPM 不良率估算</strong></Col>
                            <Col><span className="text-muted small me-1">超上限</span><strong>{formatOptionalPpm(ppmData.upper)}</strong></Col>
                            <Col><span className="text-muted small me-1">超下限</span><strong>{formatOptionalPpm(ppmData.lower)}</strong></Col>
                            <Col>
                                <span className="text-muted small me-1">總計</span>
                                <strong className="h5 mb-0">{formatOptionalPpm(ppmData.total)}</strong>
                                <span className="text-muted small ms-1">PPM</span>
                            </Col>
                            {ppmGrade && (
                                <Col xs="auto">
                                    <Badge style={{ backgroundColor: ppmGrade.bgColor, color: ppmGrade.color, fontSize: '0.8rem' }}>
                                        {ppmGrade.label}
                                    </Badge>
                                </Col>
                            )}
                        </Row>
                    </div>
                )}
            </Card.Body>
        </Card>
    );
};

export default ProcessCapabilityCard;

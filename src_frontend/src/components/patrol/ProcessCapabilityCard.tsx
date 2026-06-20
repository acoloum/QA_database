import { Alert, Badge, Card, Col, Row } from 'react-bootstrap';
import { formatPPM, getCpkGrade, getPpmGrade } from '../../utils/spcAnalysis';

interface ProcessCapability {
    available?: boolean;
    cp?: number | null;
    cpk?: number | null;
    cpl?: number | null;
    cpu?: number | null;
    pp?: number | null;
    ppk?: number | null;
    ppl?: number | null;
    ppu?: number | null;
    usl?: number | null;
    lsl?: number | null;
    one_sided?: 'lower' | 'upper' | null;
    reason?: string | null;
    valid_count?: number | null;
    ppm?: {
        upper: number;
        lower: number;
        total: number;
    } | null;
}

interface ProcessCapabilityCardProps {
    processCapability?: ProcessCapability | null;
    statsItem: string;
}

const ProcessCapabilityCard = ({ processCapability, statsItem }: ProcessCapabilityCardProps) => {
    const cpkGrade = processCapability?.cpk != null ? getCpkGrade(processCapability.cpk) : null;
    const ppkGrade = processCapability?.ppk != null ? getCpkGrade(processCapability.ppk) : null;
    const ppmData = processCapability?.ppm || null;
    const ppmGrade = ppmData ? getPpmGrade(ppmData.total) : null;
    const oneSided = processCapability?.one_sided;
    const capabilityLabel = oneSided === 'lower' ? 'CPL' : oneSided === 'upper' ? 'CPU' : 'Cp';
    const performanceLabel = oneSided === 'lower' ? 'PPL' : oneSided === 'upper' ? 'PPU' : 'Pp';
    const capabilityValue = oneSided === 'lower'
        ? processCapability?.cpl
        : oneSided === 'upper'
            ? processCapability?.cpu
            : processCapability?.cp;
    const performanceValue = oneSided === 'lower'
        ? processCapability?.ppl
        : oneSided === 'upper'
            ? processCapability?.ppu
            : processCapability?.pp;
    const oneSidedText = oneSided === 'lower'
        ? '單側下限規格（僅 LSL），顯示 CPL / PPL 作為製程能力指標'
        : oneSided === 'upper'
            ? '單側上限規格（僅 USL），顯示 CPU / PPU 作為製程能力指標'
            : null;

    return (
        <Card className="mb-4" style={{ border: '2px solid #dee2e6' }}>
            <Card.Body>
                <h5 className="mb-3">製程能力指標</h5>
                {processCapability?.available ? (
                    <>
                        {oneSidedText && (
                            <Alert variant="info" className="py-1 px-2 mb-2 small">
                                {oneSidedText}
                            </Alert>
                        )}
                        <Row className="text-center">
                            <Col>
                                <div className="text-muted small">{capabilityLabel}</div>
                                <div className="h4">{capabilityValue?.toFixed(3) ?? 'N/A'}</div>
                                <div className="text-muted small">製程能力</div>
                            </Col>
                            <Col>
                                <div className="text-muted small">{oneSided ? capabilityLabel : 'Cpk'}</div>
                                <div className="h3 mb-1">{processCapability.cpk?.toFixed(3) ?? 'N/A'}</div>
                                {cpkGrade && (
                                    <Badge style={{ backgroundColor: cpkGrade.bgColor, color: cpkGrade.color, fontSize: '0.85rem' }}>
                                        {cpkGrade.label} - {cpkGrade.description}
                                    </Badge>
                                )}
                            </Col>
                            <Col>
                                <div className="text-muted small">{performanceLabel}</div>
                                <div className="h4">{performanceValue?.toFixed(3) ?? 'N/A'}</div>
                                <div className="text-muted small">製程績效</div>
                            </Col>
                            <Col>
                                <div className="text-muted small">{oneSided ? performanceLabel : 'Ppk'}</div>
                                <div className="h3 mb-1">{processCapability.ppk?.toFixed(3) ?? 'N/A'}</div>
                                {ppkGrade && (
                                    <Badge style={{ backgroundColor: ppkGrade.bgColor, color: ppkGrade.color, fontSize: '0.85rem' }}>
                                        {ppkGrade.label} - {ppkGrade.description}
                                    </Badge>
                                )}
                            </Col>
                            <Col>
                                <div className="text-muted small">USL</div>
                                <div className="h5" style={{ color: '#e83e8c' }}>{processCapability.usl != null ? processCapability.usl.toFixed(3) : '—'}</div>
                            </Col>
                            <Col>
                                <div className="text-muted small">LSL</div>
                                <div className="h5" style={{ color: '#e83e8c' }}>{processCapability.lsl != null ? processCapability.lsl.toFixed(3) : '—'}</div>
                            </Col>
                        </Row>

                        {ppmData && (
                            <div className="mt-3 pt-3 border-top">
                                <Row className="text-center align-items-center">
                                    <Col xs="auto">
                                        <strong>PPM 不良率估算</strong>
                                    </Col>
                                    <Col>
                                        <span className="text-muted small me-1">超上限</span>
                                        <strong>{formatPPM(ppmData.upper)}</strong>
                                    </Col>
                                    <Col>
                                        <span className="text-muted small me-1">超下限</span>
                                        <strong>{formatPPM(ppmData.lower)}</strong>
                                    </Col>
                                    <Col>
                                        <span className="text-muted small me-1">總計</span>
                                        <strong className="h5 mb-0">{formatPPM(ppmData.total)}</strong>
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
                    </>
                ) : processCapability?.reason === 'insufficient_data' ? (
                    <Alert variant="warning" className="mb-0">
                        <i className="bi bi-exclamation-triangle me-2"></i>
                        資料筆數不足，無法計算 Cp/Cpk — 目前「<strong>{statsItem}</strong>」僅有 <strong>{processCapability.valid_count ?? 0}</strong> 筆有效數據，
                        需要至少 <strong>5 筆</strong>才能進行製程能力分析。
                    </Alert>
                ) : (
                    <Alert variant="info" className="mb-0">
                        <i className="bi bi-info-circle me-2"></i>
                        無法計算 Cp/Cpk — 需要在<strong>公差管理</strong>中設定該材質/規格的 USL（規格上限）和 LSL（規格下限）。
                        目前選擇的檢驗項目「<strong>{statsItem}</strong>」尚未找到對應的公差資料。
                    </Alert>
                )}
            </Card.Body>
        </Card>
    );
};

export default ProcessCapabilityCard;

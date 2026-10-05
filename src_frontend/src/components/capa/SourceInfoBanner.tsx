import { Alert, Badge, Col, Row } from 'react-bootstrap';

import type { CAPADetail } from '../../types';

export interface SourceInfoBannerProps {
    capa: CAPADetail;
}

const SourceInfoBanner = ({ capa }: SourceInfoBannerProps) => {
    const info = capa.source_info ?? {};
    const linked = capa.linked_complaints ?? [];
    return (
        <Alert variant="light" className="border mb-3 py-2">
            <Row className="small g-2 align-items-center">
                <Col xs="auto">
                    <Badge bg={capa.source_type === 'ncmr' ? 'warning' : 'info'} text="dark">
                        {capa.source_type === 'ncmr' ? 'NCMR' : '客訴'}
                    </Badge>
                    <span className="ms-1 fw-semibold">#{capa.source_id}</span>
                </Col>
                {Object.entries(info).slice(0, 4).map(([key, value]) => (
                    <Col xs="auto" key={key}>
                        <span className="text-muted">{key}：</span>
                        <span>{value ?? '-'}</span>
                    </Col>
                ))}
            </Row>
            {linked.length > 1 && (
                <div className="small mt-2 pt-2 border-top">
                    <span className="text-muted">共用此 CAPA 的客訴（{linked.length}）：</span>
                    {linked.map(c => (
                        <span key={c.id} className="ms-2 text-nowrap">
                            <Badge bg="info" text="dark">{c.complaint_no}</Badge>
                            <span className="ms-1 text-muted">
                                {[c.material, c.spec].filter(Boolean).join('｜') || '-'}
                            </span>
                        </span>
                    ))}
                </div>
            )}
        </Alert>
    );
};

export default SourceInfoBanner;

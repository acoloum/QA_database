import { Alert, Badge, Col, Row } from 'react-bootstrap';

import type { CAPADetail } from '../../types';

export interface SourceInfoBannerProps {
    capa: CAPADetail;
}

const SourceInfoBanner = ({ capa }: SourceInfoBannerProps) => {
    const info = capa.source_info ?? {};
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
        </Alert>
    );
};

export default SourceInfoBanner;

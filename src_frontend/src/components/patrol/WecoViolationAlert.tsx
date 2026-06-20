import { useState } from 'react';
import { Alert } from 'react-bootstrap';
import type { SpcViolation } from '../../types';

interface WecoViolationAlertProps {
    violations: SpcViolation[];
}

const WecoViolationAlert = ({ violations }: WecoViolationAlertProps) => {
    const [showWeco, setShowWeco] = useState(false);

    if (violations.length === 0) {
        return null;
    }

    return (
        <Alert variant="danger">
            <div
                className="d-flex justify-content-between align-items-center"
                style={{ cursor: 'pointer' }}
                onClick={() => setShowWeco(!showWeco)}
            >
                <Alert.Heading className="mb-0" style={{ fontSize: '1rem' }}>
                    偵測到 {violations.length} 個製程異常數據點 (WECO Rules) - 點擊展開/收合
                </Alert.Heading>
                <i className={`bi bi-chevron-${showWeco ? 'up' : 'down'}`}></i>
            </div>
            {showWeco && (
                <ul className="mb-0 mt-3">
                    {violations.map((violation, index) => (
                        <li key={`${violation.label}-${index}`}>
                            <strong>{violation.label}</strong>: {violation.reasons.join(', ')}
                        </li>
                    ))}
                </ul>
            )}
        </Alert>
    );
};

export default WecoViolationAlert;

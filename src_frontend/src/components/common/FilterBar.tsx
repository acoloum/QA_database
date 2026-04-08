import { Button, Col, Row } from 'react-bootstrap';

interface FilterBarProps {
    onReset: () => void;
    children: React.ReactNode;
}

const FilterBar = ({ onReset, children }: FilterBarProps) => {
    return (
        <div className="bg-light border rounded p-3 mb-3">
            <Row className="g-2 align-items-end">
                {children}
                <Col xs="auto">
                    <Button variant="outline-secondary" size="sm" onClick={onReset}>
                        <i className="bi bi-x-circle me-1"></i>清除篩選
                    </Button>
                </Col>
            </Row>
        </div>
    );
};

export default FilterBar;

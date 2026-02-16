import { useState } from 'react';
import { Button, ButtonGroup, Form } from 'react-bootstrap';
import type { DatePeriod } from '../../hooks/useDashboard';

interface DateFilterProps {
    period: DatePeriod;
    onPeriodChange: (period: DatePeriod) => void;
    customDateRange?: { start: string; end: string };
    onCustomDateChange?: (range: { start: string; end: string }) => void;
    dateRangeLabel?: string;
}

const DateFilter = ({ period, onPeriodChange, customDateRange, onCustomDateChange, dateRangeLabel }: DateFilterProps) => {
    const [showCustom, setShowCustom] = useState(false);

    const periods: { key: DatePeriod; label: string }[] = [
        { key: 'this_week', label: '本週' },
        { key: 'this_month', label: '本月' },
        { key: 'last_month', label: '上月' },
    ];

    return (
        <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
            <ButtonGroup size="sm">
                {periods.map(p => (
                    <Button
                        key={p.key}
                        variant={period === p.key && !showCustom ? 'primary' : 'outline-secondary'}
                        onClick={() => {
                            onPeriodChange(p.key);
                            setShowCustom(false);
                        }}
                    >
                        {p.label}
                    </Button>
                ))}
            </ButtonGroup>
            
            <Button
                size="sm"
                variant={showCustom ? 'primary' : 'outline-secondary'}
                onClick={() => setShowCustom(!showCustom)}
            >
                <i className="fa-solid fa-calendar me-1"></i>
                自訂
            </Button>

            {showCustom && onCustomDateChange && (
                <div className="d-flex align-items-center gap-2">
                    <Form.Control
                        type="date"
                        size="sm"
                        style={{ width: '140px' }}
                        value={customDateRange?.start || ''}
                        onChange={(e) => onCustomDateChange({
                            start: e.target.value,
                            end: customDateRange?.end || e.target.value
                        })}
                    />
                    <span className="text-muted">至</span>
                    <Form.Control
                        type="date"
                        size="sm"
                        style={{ width: '140px' }}
                        value={customDateRange?.end || ''}
                        onChange={(e) => onCustomDateChange({
                            start: customDateRange?.start || e.target.value,
                            end: e.target.value
                        })}
                    />
                    <Button
                        size="sm"
                        variant="primary"
                        onClick={() => onPeriodChange('custom')}
                    >
                        套用
                    </Button>
                </div>
            )}

            {dateRangeLabel && !showCustom && (
                <span className="text-muted small ms-2">
                    {dateRangeLabel}
                </span>
            )}
        </div>
    );
};

export default DateFilter;

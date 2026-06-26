import { formatToleranceRange, type ToleranceDisplayItem } from './toleranceFormat';

interface ToleranceBadgeListProps {
    tolerances: ToleranceDisplayItem[];
}

export const ToleranceBadgeList = ({ tolerances }: ToleranceBadgeListProps) => (
    <>
        {tolerances.map((tolerance, idx) => {
            const rangeDisplay = formatToleranceRange(tolerance);
            const unitDisplay = tolerance.單位 ? ` ${tolerance.單位}` : '';
            return (
                <span key={`${tolerance.項目 ?? 'tolerance'}-${idx}`} className="badge bg-primary">
                    {tolerance.項目}: {rangeDisplay}{unitDisplay}
                </span>
            );
        })}
    </>
);

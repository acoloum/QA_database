import { Fragment } from 'react';
import { Form, Table } from 'react-bootstrap';

import {
    getPatrolDetailValue,
    isPatrolCellNG,
    isPatrolConcentricityNG,
    type PatrolDetailInput,
    type PatrolLiveViolation,
    type PatrolTolerance,
} from './patrolFormUtils';

interface PatrolMeasurementTableProps {
    groupCount: number;
    showInner: boolean;
    details: PatrolDetailInput[];
    tolerances: PatrolTolerance[];
    specStdValues: Record<string, number>;
    onDetailChange: (group: string, pos: string, item: string, type: 'min' | 'max', value: string) => void;
    liveViolations?: Record<string, PatrolLiveViolation>;
}

const POSITIONS = ['前段', '中段', '後段'];
const ITEMS = ['外徑', '內徑', '厚度'];

const PatrolMeasurementTable = ({
    groupCount,
    showInner,
    details,
    tolerances,
    specStdValues,
    onDetailChange,
    liveViolations = {},
}: PatrolMeasurementTableProps) => {
    const isCellNG = (pos: string, item: string, type: 'min' | 'max', group: string) => isPatrolCellNG({
        details,
        tolerances,
        specStdValues,
        group,
        pos,
        item,
        type,
    });

    const isConcentricityNG = (pos: string, group: string) => isPatrolConcentricityNG({
        details,
        tolerances,
        specStdValues,
        group,
        pos,
    });

    const getLiveViolation = (pos: string, item: string, group: string) =>
        liveViolations[`${pos}|${item}|${group}`];

    return (
        <div className="table-responsive" style={{ overflow: 'auto', maxHeight: '50vh', display: 'block' }}>
            <Table bordered size="sm" className="text-center align-middle" style={{ minWidth: showInner ? '1550px' : '1050px', tableLayout: 'fixed' }}>
                <thead className="table-light">
                    <tr>
                        <th rowSpan={3} style={{ width: '50px' }}>組別</th>
                        <th colSpan={showInner ? 6 : 4}>前段</th>
                        <th colSpan={showInner ? 6 : 4}>中段</th>
                        <th colSpan={showInner ? 6 : 4}>後段</th>
                    </tr>
                    <tr>
                        {POSITIONS.map(pos =>
                            ITEMS.map(item => {
                                if (item === '內徑' && !showInner) return null;
                                return <th key={`${pos}-${item}`} colSpan={2}>{item}</th>;
                            })
                        )}
                    </tr>
                    <tr>
                        {POSITIONS.map(pos =>
                            ITEMS.map(item => {
                                if (item === '內徑' && !showInner) return null;
                                return <Fragment key={`${pos}-${item}-hd`}><th>MIN</th><th>MAX</th></Fragment>;
                            })
                        )}
                    </tr>
                </thead>
                <tbody>
                    {Array.from({ length: groupCount }, (_, idx) => {
                        const group = `第${idx + 1}組`;
                        return (
                            <tr key={group}>
                                <td className="fw-bold bg-light">{group}</td>
                                {POSITIONS.map(pos =>
                                    ITEMS.map(item => {
                                        if (item === '內徑' && !showInner) return null;
                                        const minNG = isCellNG(pos, item, 'min', group) || (item === '厚度' && isConcentricityNG(pos, group));
                                        const maxNG = isCellNG(pos, item, 'max', group) || (item === '厚度' && isConcentricityNG(pos, group));
                                        const liveViolation = getLiveViolation(pos, item, group);
                                        return (
                                            <Fragment key={`${pos}-${item}`}>
                                                <td style={{ padding: '2px' }}>
                                                    <Form.Control
                                                        size="sm"
                                                        type="number"
                                                        step="0.01"
                                                        value={getPatrolDetailValue(details, group, pos, item, 'min')}
                                                        onChange={e => onDetailChange(group, pos, item, 'min', e.target.value)}
                                                        className={`patrol-input${minNG ? ' is-invalid-breathing' : ''}${liveViolation ? ' patrol-live-warning' : ''}`}
                                                    />
                                                </td>
                                                <td style={{ padding: '2px' }}>
                                                    <Form.Control
                                                        size="sm"
                                                        type="number"
                                                        step="0.01"
                                                        value={getPatrolDetailValue(details, group, pos, item, 'max')}
                                                        onChange={e => onDetailChange(group, pos, item, 'max', e.target.value)}
                                                        className={`patrol-input${maxNG ? ' is-invalid-breathing' : ''}${liveViolation ? ' patrol-live-warning' : ''}`}
                                                    />
                                                    {liveViolation && (
                                                        <div className="small text-warning-emphasis" style={{ whiteSpace: 'normal', maxWidth: '160px' }}>
                                                            ⚠️ {liveViolation.hint}
                                                        </div>
                                                    )}
                                                </td>
                                            </Fragment>
                                        );
                                    })
                                )}
                            </tr>
                        );
                    })}
                </tbody>
            </Table>
        </div>
    );
};

export default PatrolMeasurementTable;

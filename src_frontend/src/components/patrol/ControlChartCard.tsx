import { Card } from 'react-bootstrap';
import { Line } from 'react-chartjs-2';
import type { ActiveDataPoint, ChartData, TooltipItem } from 'chart.js';

import { getClickedPointId, setChartPointCursor, shouldShowControlLegendLabel } from '../../utils/spcChartOptions';

interface ControlChartCardProps {
    title: string;
    data: ChartData<'line'>;
    ids: unknown[];
    getViolationReasons: (index: number) => string;
    filterLegendLabels?: boolean;
    onEditPoint?: (id: number) => void;
}

const ControlChartCard = ({
    title,
    data,
    ids,
    getViolationReasons,
    filterLegendLabels = false,
    onEditPoint,
}: ControlChartCardProps) => (
    <Card className="h-100 shadow-sm">
        <Card.Body>
            <h5 className="card-title text-center">{title}</h5>
            <div style={{ height: '300px' }}>
                <Line
                    data={data}
                    options={{
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                display: true,
                                position: 'bottom',
                                labels: {
                                    ...(filterLegendLabels ? { filter: item => shouldShowControlLegendLabel(item.text) } : {}),
                                    usePointStyle: true,
                                    pointStyle: 'line',
                                    font: { size: 10 }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    afterLabel: (ctx: TooltipItem<'line'>) => {
                                        if (ctx.datasetIndex !== 0) return '';
                                        const reasons = getViolationReasons(ctx.dataIndex);
                                        return reasons ? `\u26a0\ufe0f ${reasons}` : '';
                                    }
                                }
                            }
                        },
                        onClick: (_event: unknown, elements: ActiveDataPoint[]) => {
                            const id = getClickedPointId(ids, elements);
                            if (id && onEditPoint) onEditPoint(id);
                        },
                        onHover: (event: unknown, elements: ActiveDataPoint[]) => {
                            setChartPointCursor(event, elements);
                        }
                    }}
                />
            </div>
        </Card.Body>
    </Card>
);

export default ControlChartCard;

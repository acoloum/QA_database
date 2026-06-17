import { Table } from 'react-bootstrap';
import { sortChannels } from './channelSort';

interface Props {
  時間: string[];
  數值: Record<string, number[]>;
  設定溫度: number;
  公差: number;
  穩定開始: number;
  穩定結束: number;
}

/** 詳細時間×通道溫度表；恆溫穩定期內超出設定溫度±公差的點以紅底標示 */
const TusDataTable = ({ 時間, 數值, 設定溫度, 公差, 穩定開始, 穩定結束 }: Props) => {
  const channels = sortChannels(Object.keys(數值));
  const hi = 設定溫度 + 公差;
  const lo = 設定溫度 - 公差;

  return (
    <div style={{ maxHeight: 320, overflow: 'auto' }}>
      <Table bordered size="sm" className="text-center align-middle mb-0" style={{ fontSize: 11 }}>
        <thead className="table-secondary" style={{ position: 'sticky', top: 0, zIndex: 1 }}>
          <tr>
            <th style={{ position: 'sticky', left: 0 }}>時間</th>
            {channels.map(c => <th key={c}>{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {時間.map((t, j) => {
            const soak = j >= 穩定開始 && j <= 穩定結束;
            return (
              <tr key={j} className={soak ? 'table-light' : undefined}>
                <td style={{ position: 'sticky', left: 0, background: soak ? '#fcfcfd' : '#fff', whiteSpace: 'nowrap' }}>{t}</td>
                {channels.map(c => {
                  const v = 數值[c]?.[j];
                  const over = soak && v != null && v > hi;
                  const under = soak && v != null && v < lo;
                  const style = over
                    ? { background: '#f8d7da', color: '#842029', fontWeight: 600 }   // 超上限：紅
                    : under
                      ? { background: '#cfe2ff', color: '#084298', fontWeight: 600 } // 低於下限：藍
                      : undefined;
                  return (
                    <td key={c} style={style}>
                      {v == null ? '' : v}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </Table>
    </div>
  );
};

export default TusDataTable;

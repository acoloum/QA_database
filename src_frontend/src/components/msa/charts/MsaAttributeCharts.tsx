import type { MsaResultVersion } from '../../../types/msa';
import MsaAccessibleChart from './MsaAccessibleChart';
import {
  buildAttributeModel,
} from './msaChartModels';

interface Props {
  result: MsaResultVersion;
}

/** 計數型圖表；每張都附文字摘要與資料表。 */
export default function MsaAttributeCharts({ result }: Props) {
  const models = [
    buildAttributeModel(result),
  ];

  return (
    <section aria-label="計數型圖表">
      {models.map((model) => (
        <MsaAccessibleChart key={model.title} model={model} />
      ))}
    </section>
  );
}

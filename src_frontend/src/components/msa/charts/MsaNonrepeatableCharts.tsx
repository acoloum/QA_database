import type { MsaResultVersion } from '../../../types/msa';
import MsaAccessibleChart from './MsaAccessibleChart';
import {
  buildNonrepeatableModel,
} from './msaChartModels';

interface Props {
  result: MsaResultVersion;
}

/** 不可重複研究圖表；每張都附文字摘要與資料表。 */
export default function MsaNonrepeatableCharts({ result }: Props) {
  const models = [
    buildNonrepeatableModel(result),
  ];

  return (
    <section aria-label="不可重複研究圖表">
      {models.map((model) => (
        <MsaAccessibleChart key={model.title} model={model} />
      ))}
    </section>
  );
}

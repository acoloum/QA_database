import type { MsaResultVersion } from '../../../types/msa';
import MsaAccessibleChart from './MsaAccessibleChart';
import {
  buildStabilityModel,
} from './msaChartModels';

interface Props {
  result: MsaResultVersion;
}

/** 穩定性圖表；每張都附文字摘要與資料表。 */
export default function MsaStabilityCharts({ result }: Props) {
  const models = [
    buildStabilityModel(result),
  ];

  return (
    <section aria-label="穩定性圖表">
      {models.map((model) => (
        <MsaAccessibleChart key={model.title} model={model} />
      ))}
    </section>
  );
}

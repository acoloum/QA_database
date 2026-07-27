import type { MsaResultVersion } from '../../../types/msa';
import MsaAccessibleChart from './MsaAccessibleChart';
import {
  buildBiasModel,
  buildLinearityModel,
} from './msaChartModels';

interface Props {
  result: MsaResultVersion;
}

/** 偏倚與線性圖表；每張都附文字摘要與資料表。 */
export default function MsaBiasLinearityCharts({ result }: Props) {
  const models = [
    buildBiasModel(result),
    buildLinearityModel(result),
  ];

  return (
    <section aria-label="偏倚與線性圖表">
      {models.map((model) => (
        <MsaAccessibleChart key={model.title} model={model} />
      ))}
    </section>
  );
}

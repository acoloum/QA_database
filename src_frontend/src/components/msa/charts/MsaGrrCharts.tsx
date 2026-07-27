import type { MsaResultVersion } from '../../../types/msa';
import MsaAccessibleChart from './MsaAccessibleChart';
import {
  buildGrrVariationModel,
  buildGrrControlChartModel,
} from './msaChartModels';

interface Props {
  result: MsaResultVersion;
}

/** GRR 變差與管制圖圖表；每張都附文字摘要與資料表。 */
export default function MsaGrrCharts({ result }: Props) {
  const models = [
    buildGrrVariationModel(result),
    buildGrrControlChartModel(result),
  ];

  return (
    <section aria-label="GRR 變差與管制圖圖表">
      {models.map((model) => (
        <MsaAccessibleChart key={model.title} model={model} />
      ))}
    </section>
  );
}

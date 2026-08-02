/**
 * Chart.js 全域註冊（單一註冊點）。
 *
 * 註冊本身是冪等的，但過去 11 個檔案各自寫一份、且每份的元件清單都不同，
 * 新增圖表類型時得逐一猜要改哪份。這裡收斂為全庫所有圖表所需元件的聯集，
 * 使用端一律 `import '../../utils/chartSetup';` 即可，不再各自 register。
 */
import {
    Chart as ChartJS,
    // 座標軸
    CategoryScale,
    LinearScale,
    // 元素
    ArcElement,
    BarElement,
    LineElement,
    PointElement,
    // 控制器（供 SPC 報告等以 type 動態切換圖表的情境使用）
    BarController,
    LineController,
    ScatterController,
    // 外掛
    Filler,
    Legend,
    Title,
    Tooltip,
} from 'chart.js';
import annotationPlugin from 'chartjs-plugin-annotation';

ChartJS.register(
    CategoryScale,
    LinearScale,
    ArcElement,
    BarElement,
    LineElement,
    PointElement,
    BarController,
    LineController,
    ScatterController,
    Filler,
    Legend,
    Title,
    Tooltip,
    annotationPlugin,
);

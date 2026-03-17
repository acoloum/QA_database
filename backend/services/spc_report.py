import numpy as np
from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, BarChart, Reference
from openpyxl.chart.layout import Layout, ManualLayout


def detect_weco_violations(data, cl, ucl, lcl, labels, chart_type):
    """Detect WECO violations for Excel report generation."""
    violations = []
    if not data:
        return violations
    for i, val in enumerate(data):
        reasons = []
        # Rule 1: Beyond control limits
        if val > ucl or val < lcl:
            reasons.append("Rule 1: 超出控制限")
        # Rule 2: 9 consecutive on same side
        if i >= 8:
            last9 = data[i - 8:i + 1]
            if all(v > cl for v in last9) or all(v < cl for v in last9):
                reasons.append("Rule 2: 連續9點同側")
        # Rule 3: 6 consecutive trending
        if i >= 5:
            last6 = data[i - 5:i + 1]
            inc = all(last6[j] > last6[j - 1] for j in range(1, len(last6)))
            dec = all(last6[j] < last6[j - 1] for j in range(1, len(last6)))
            if inc or dec:
                reasons.append("Rule 3: 連續6點趨勢")
        if reasons:
            violations.append({
                'label': labels[i] if i < len(labels) else str(i),
                'chart_type': chart_type,
                'value': val,
                'reasons': reasons
            })
    return violations



class SpcReportService:
    @staticmethod
    def generate_report(stats_data: dict, field: str, filters: dict) -> BytesIO:
        """Generate an SPC report as Excel file with embedded charts"""
        wb = Workbook()

        # --- Sheet 1: Summary ---
        ws = wb.active
        ws.title = "SPC 統計摘要"

        # Styles
        title_font = Font(name="微軟正黑體", size=14, bold=True)
        header_font = Font(name="微軟正黑體", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="2B579A", end_color="2B579A", fill_type="solid")
        normal_font = Font(name="微軟正黑體", size=10)
        good_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        warn_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
        bad_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        thin_border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )

        # Title
        ws.merge_cells('A1:F1')
        ws['A1'] = f"SPC 統計分析報告 - {field}"
        ws['A1'].font = title_font

        # Report info
        ws['A3'] = "報告產生時間："
        ws['B3'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ws['A4'] = "檢驗項目："
        ws['B4'] = field
        ws['A5'] = "廠商："
        ws['B5'] = filters.get('vendor', '全部')
        ws['A6'] = "材質："
        ws['B6'] = filters.get('material', '全部')
        ws['A7'] = "規格："
        ws['B7'] = filters.get('spec', '全部')
        ws['A8'] = "日期範圍："
        ws['B8'] = f"{filters.get('start_date', '不限')} ~ {filters.get('end_date', '不限')}"
        for r in range(3, 9):
            ws[f'A{r}'].font = Font(name="微軟正黑體", size=10, bold=True)
            ws[f'B{r}'].font = normal_font

        # --- Basic Statistics ---
        row = 10
        ws.merge_cells(f'A{row}:F{row}')
        ws[f'A{row}'] = "基本統計量"
        ws[f'A{row}'].font = Font(name="微軟正黑體", size=12, bold=True)
        row += 1

        avgs = stats_data.get('avgs', [])
        if avgs:
            stats_items = [
                ("有效樣本數", len(avgs)),
                ("平均值 (X̄)", round(float(np.mean(avgs)), 4)),
                ("標準差 (σ)", round(float(np.std(avgs, ddof=1)), 4) if len(avgs) > 1 else "N/A"),
                ("最小值", round(min(avgs), 4)),
                ("最大值", round(max(avgs), 4)),
                ("全距 (R)", round(max(avgs) - min(avgs), 4)),
            ]

            # Add distribution stats if available
            dist_stats = stats_data.get('distribution_stats', {})
            if dist_stats:
                stats_items.append(("偏態係數 (Skewness)", dist_stats.get('skewness', 'N/A')))
                stats_items.append(("峰態係數 (Kurtosis)", dist_stats.get('kurtosis', 'N/A')))
                stats_items.append(("常態性評估", dist_stats.get('normality_label', 'N/A')))

            headers = ["統計項目", "數值"]
            for col_idx, h in enumerate(headers, 1):
                cell = ws.cell(row=row, column=col_idx, value=h)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')
            row += 1
            for name, value in stats_items:
                cell_name = ws.cell(row=row, column=1, value=name)
                cell_name.font = normal_font
                cell_name.border = thin_border
                cell_val = ws.cell(row=row, column=2, value=value)
                cell_val.font = normal_font
                cell_val.border = thin_border
                cell_val.alignment = Alignment(horizontal='center')
                # Highlight normality assessment
                if name == "常態性評估":
                    normality = dist_stats.get('normality', '')
                    if normality == 'good':
                        cell_val.fill = good_fill
                    elif normality == 'moderate':
                        cell_val.fill = warn_fill
                    elif normality == 'poor':
                        cell_val.fill = bad_fill
                row += 1

        # --- Control Limits ---
        row += 1
        ws.merge_cells(f'A{row}:F{row}')
        ws[f'A{row}'] = "管制界限"
        ws[f'A{row}'].font = Font(name="微軟正黑體", size=12, bold=True)
        row += 1

        avg_n = stats_data.get('avg_subgroup_size', 5)
        cl_items = [
            ("平均子群大小 (n)", avg_n),
            ("X̄ 中心線 (CL)", stats_data.get('x_cl', 0)),
            ("X̄ 管制上限 (UCL)", stats_data.get('x_ucl', 0)),
            ("X̄ 管制下限 (LCL)", stats_data.get('x_lcl', 0)),
            ("R̄ 中心線", stats_data.get('r_cl', 0)),
            ("R 管制上限 (UCL)", stats_data.get('r_ucl', 0)),
        ]
        for col_idx, h in enumerate(["管制項目", "數值"], 1):
            cell = ws.cell(row=row, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')
        row += 1
        for name, value in cl_items:
            ws.cell(row=row, column=1, value=name).font = normal_font
            ws.cell(row=row, column=1).border = thin_border
            cell_val = ws.cell(row=row, column=2, value=round(value, 4) if isinstance(value, (int, float)) else value)
            cell_val.font = normal_font
            cell_val.border = thin_border
            cell_val.alignment = Alignment(horizontal='center')
            row += 1

        # --- Process Capability ---
        pc = stats_data.get('process_capability', {})
        if pc.get('available'):
            row += 1
            ws.merge_cells(f'A{row}:F{row}')
            ws[f'A{row}'] = "製程能力指標"
            ws[f'A{row}'].font = Font(name="微軟正黑體", size=12, bold=True)
            row += 1

            for col_idx, h in enumerate(["指標", "數值", "等級"], 1):
                cell = ws.cell(row=row, column=col_idx, value=h)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')
            row += 1

            def get_cpk_grade(val):
                if val is None:
                    return ("N/A", None)
                if val >= 1.67:
                    return ("A (優秀)", good_fill)
                elif val >= 1.33:
                    return ("B (良好)", good_fill)
                elif val >= 1.0:
                    return ("C (可接受)", warn_fill)
                else:
                    return ("D (不足)", bad_fill)

            pc_items = [
                ("USL (規格上限)", pc.get('usl')),
                ("LSL (規格下限)", pc.get('lsl')),
                ("Cp (製程能力)", pc.get('cp')),
                ("Cpk (修正製程能力)", pc.get('cpk')),
                ("Pp (製程績效)", pc.get('pp')),
                ("Ppk (修正製程績效)", pc.get('ppk')),
                ("CPU (上限能力)", pc.get('cpu')),
                ("CPL (下限能力)", pc.get('cpl')),
                ("σ_within (組內標準差)", pc.get('sigma_within')),
                ("σ_overall (整體標準差)", pc.get('sigma_overall')),
            ]

            for name, value in pc_items:
                ws.cell(row=row, column=1, value=name).font = normal_font
                ws.cell(row=row, column=1).border = thin_border
                display_val = round(value, 4) if isinstance(value, (int, float)) else "N/A"
                cell_val = ws.cell(row=row, column=2, value=display_val)
                cell_val.font = normal_font
                cell_val.border = thin_border
                cell_val.alignment = Alignment(horizontal='center')

                # Grade column for Cp/Cpk/Pp/Ppk
                if name in ("Cpk (修正製程能力)", "Ppk (修正製程績效)"):
                    grade, fill = get_cpk_grade(value)
                    cell_grade = ws.cell(row=row, column=3, value=grade)
                    cell_grade.font = normal_font
                    cell_grade.border = thin_border
                    cell_grade.alignment = Alignment(horizontal='center')
                    if fill:
                        cell_grade.fill = fill
                row += 1

            # --- PPM Row ---
            ppm = pc.get('ppm', {})
            if ppm:
                row += 1
                ws.merge_cells(f'A{row}:F{row}')
                ws[f'A{row}'] = "PPM 不良率估算"
                ws[f'A{row}'].font = Font(name="微軟正黑體", size=12, bold=True)
                row += 1
                ppm_items = [
                    ("PPM 超上限", ppm.get('upper', 0)),
                    ("PPM 超下限", ppm.get('lower', 0)),
                    ("PPM 總計", ppm.get('total', 0)),
                ]
                for col_idx, h in enumerate(["項目", "數值"], 1):
                    cell = ws.cell(row=row, column=col_idx, value=h)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal='center')
                row += 1
                for name, value in ppm_items:
                    ws.cell(row=row, column=1, value=name).font = normal_font
                    ws.cell(row=row, column=1).border = thin_border
                    cell_val = ws.cell(row=row, column=2, value=round(value, 1) if isinstance(value, (int, float)) else value)
                    cell_val.font = normal_font
                    cell_val.border = thin_border
                    cell_val.alignment = Alignment(horizontal='center')
                    if name == "PPM 總計" and isinstance(value, (int, float)):
                        if value <= 3.4:
                            cell_val.fill = good_fill
                        elif value <= 6210:
                            cell_val.fill = warn_fill
                        else:
                            cell_val.fill = bad_fill
                    row += 1

            # --- Process Capability Conclusion ---
            row += 1
            ws.merge_cells(f'A{row}:F{row}')
            ws[f'A{row}'] = "製程能力結論"
            ws[f'A{row}'].font = Font(name="微軟正黑體", size=12, bold=True)
            row += 1

            cpk_val = pc.get('cpk')
            conclusion_lines = []
            if cpk_val is not None:
                if cpk_val >= 1.67:
                    conclusion_lines.append("✅ 製程能力優秀 (Cpk ≥ 1.67)，製程穩定且具備充裕的安全裕度。")
                    conclusion_lines.append("建議：維持現有製程管控，可考慮減少抽檢頻率。")
                elif cpk_val >= 1.33:
                    conclusion_lines.append("✅ 製程能力良好 (Cpk ≥ 1.33)，製程穩定且符合規格要求。")
                    conclusion_lines.append("建議：持續監控製程，維持現有管控水準。")
                elif cpk_val >= 1.0:
                    conclusion_lines.append("⚠️ 製程能力可接受 (Cpk ≥ 1.0)，但安全裕度較低。")
                    conclusion_lines.append("建議：加強製程監控，分析變異來源，尋求改善。")
                else:
                    conclusion_lines.append("❌ 製程能力不足 (Cpk < 1.0)，產品超出規格的風險較高。")
                    conclusion_lines.append("建議：立即進行製程改善，進行根本原因分析 (Root Cause Analysis)。")

                # Normality note
                dist_stats = stats_data.get('distribution_stats', {})
                normality = dist_stats.get('normality', '')
                if normality == 'poor':
                    conclusion_lines.append("⚠️ 注意：數據分佈明顯非常態，以上 Cpk 數值可能不準確，建議搭配其他分析方法。")
                elif normality == 'moderate':
                    conclusion_lines.append("📋 備註：數據分佈略偏常態，Cpk 數值僅供參考。")

            for line in conclusion_lines:
                ws.cell(row=row, column=1, value=line).font = normal_font
                ws.merge_cells(f'A{row}:F{row}')
                row += 1

        # Column widths
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 18
        ws.column_dimensions['C'].width = 15

        # --- Sheet 2: Control Chart Data ---
        ws2 = wb.create_sheet(title="管制圖數據")
        # Headers include control limit columns for chart references
        data_headers = ["序號", "標籤", "日期", "平均值 (X̄)", "全距 (R)", "UCL", "CL", "LCL", "R_UCL", "R̄"]
        for col_idx, h in enumerate(data_headers, 1):
            cell = ws2.cell(row=1, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')

        labels = stats_data.get('labels', [])
        dates = stats_data.get('dates', [])
        ranges = stats_data.get('ranges', [])
        x_ucl = stats_data.get('x_ucl', 0)
        x_cl = stats_data.get('x_cl', 0)
        x_lcl = stats_data.get('x_lcl', 0)
        r_ucl = stats_data.get('r_ucl', 0)
        r_cl = stats_data.get('r_cl', 0)

        # USL/LSL columns if available
        has_spec_limits = pc.get('available') and pc.get('usl') is not None and pc.get('lsl') is not None
        if has_spec_limits:
            for col_idx, h in enumerate(["USL", "LSL"], len(data_headers) + 1):
                cell = ws2.cell(row=1, column=col_idx, value=h)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')

        for i in range(len(avgs)):
            r = i + 2
            ws2.cell(row=r, column=1, value=i + 1).border = thin_border
            ws2.cell(row=r, column=2, value=labels[i] if i < len(labels) else "").border = thin_border
            ws2.cell(row=r, column=3, value=dates[i] if i < len(dates) else "").border = thin_border
            cell_avg = ws2.cell(row=r, column=4, value=round(avgs[i], 4))
            cell_avg.border = thin_border
            if avgs[i] > x_ucl or avgs[i] < x_lcl:
                cell_avg.fill = bad_fill
            cell_range = ws2.cell(row=r, column=5, value=round(ranges[i], 4) if i < len(ranges) else "")
            cell_range.border = thin_border
            if i < len(ranges) and ranges[i] > r_ucl:
                cell_range.fill = bad_fill
            # Control limit columns for chart series
            ws2.cell(row=r, column=6, value=round(x_ucl, 4))
            ws2.cell(row=r, column=7, value=round(x_cl, 4))
            ws2.cell(row=r, column=8, value=round(x_lcl, 4))
            ws2.cell(row=r, column=9, value=round(r_ucl, 4))
            ws2.cell(row=r, column=10, value=round(r_cl, 4))

            if has_spec_limits:
                ws2.cell(row=r, column=11, value=round(pc['usl'], 4))
                ws2.cell(row=r, column=12, value=round(pc['lsl'], 4))

        for col_idx in range(1, 13):
            ws2.column_dimensions[get_column_letter(col_idx)].width = 15

        # --- Sheet 3: Histogram Data ---
        all_values = stats_data.get('all_values', [])
        hist_data_rows = 0
        ws3 = None
        if all_values:
            ws3 = wb.create_sheet(title="直方圖數據")
            hist_headers = ["區間", "頻次", "累積百分比"]
            for col_idx, h in enumerate(hist_headers, 1):
                cell = ws3.cell(row=1, column=col_idx, value=h)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')

            arr = np.array(all_values)
            counts, bin_edges = np.histogram(arr, bins='auto')
            total = len(all_values)
            hist_mean = float(np.mean(arr))
            hist_std = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
            hist_bin_width = float(bin_edges[1] - bin_edges[0]) if len(bin_edges) > 1 else 1.0
            cumulative = 0
            hist_data_rows = len(counts)

            # 第 4 欄：常態分佈標頭
            cell_nd = ws3.cell(row=1, column=4, value="常態分佈")
            cell_nd.font = header_font
            cell_nd.fill = header_fill
            cell_nd.border = thin_border
            cell_nd.alignment = Alignment(horizontal='center')

            for i in range(len(counts)):
                label = f"{round(bin_edges[i], 3)} ~ {round(bin_edges[i + 1], 3)}"
                cumulative += counts[i]
                ws3.cell(row=i + 2, column=1, value=label).border = thin_border
                ws3.cell(row=i + 2, column=2, value=int(counts[i])).border = thin_border
                ws3.cell(row=i + 2, column=3, value=f"{round(cumulative / total * 100, 1)}%").border = thin_border
                # 常態 PDF 值（縮放至頻次單位）
                midpoint = float((bin_edges[i] + bin_edges[i + 1]) / 2)
                if hist_std > 0:
                    normal_val = (1 / (hist_std * np.sqrt(2 * np.pi))) * np.exp(
                        -0.5 * ((midpoint - hist_mean) / hist_std) ** 2
                    ) * total * hist_bin_width
                else:
                    normal_val = 0.0
                ws3.cell(row=i + 2, column=4, value=round(float(normal_val), 4)).border = thin_border

            for col_idx in range(1, 5):
                ws3.column_dimensions[get_column_letter(col_idx)].width = 20

        # --- Sheet 4: WECO Violations ---
        ws_weco = wb.create_sheet(title="WECO 異常清單")
        weco_headers = ["序號", "數據標籤", "類型", "量測值/全距", "違規規則"]
        for col_idx, h in enumerate(weco_headers, 1):
            cell = ws_weco.cell(row=1, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal='center')

        # Detect WECO violations for the report
        weco_row = 2
        if len(avgs) > 0:
            x_violations = detect_weco_violations(avgs, x_cl, x_ucl, x_lcl, labels, 'X̄')
            r_violations = detect_weco_violations(ranges, r_cl, r_ucl, 0, labels, 'R')

            for v in x_violations + r_violations:
                ws_weco.cell(row=weco_row, column=1, value=weco_row - 1).border = thin_border
                ws_weco.cell(row=weco_row, column=2, value=v['label']).border = thin_border
                ws_weco.cell(row=weco_row, column=3, value=v['chart_type']).border = thin_border
                ws_weco.cell(row=weco_row, column=4, value=round(v['value'], 4)).border = thin_border
                cell_rules = ws_weco.cell(row=weco_row, column=5, value=', '.join(v['reasons']))
                cell_rules.border = thin_border
                cell_rules.fill = bad_fill
                weco_row += 1

        if weco_row == 2:
            ws_weco.cell(row=2, column=1, value="無異常檢出").font = Font(name="微軟正黑體", size=11, color="28A745")
            ws_weco.merge_cells('A2:E2')

        for col_idx, w in enumerate([8, 15, 8, 15, 40], 1):
            ws_weco.column_dimensions[get_column_letter(col_idx)].width = w

        # ======== Sheet 5: Embedded Charts ========
        if avgs and len(avgs) >= 2:
            ws_chart = wb.create_sheet(title="圖表")
            data_count = len(avgs)

            # --- X-bar Control Chart ---
            xbar_chart = LineChart()
            xbar_chart.title = f"X̄ 平均值管制圖 - {field}"
            xbar_chart.y_axis.title = "量測值"
            xbar_chart.y_axis.delete = False
            xbar_chart.x_axis.delete = False
            xbar_chart.y_axis.numFmt = '0.000'
            xbar_chart.x_axis.tickLblSkip = 1
            xbar_chart.width = 22
            xbar_chart.height = 14
            xbar_chart.style = 10
            xbar_chart.legend.position = 'b'
            xbar_chart.plotArea.layout = Layout(
                manualLayout=ManualLayout(x=0.05, y=0.12, w=0.90, h=0.68)
            )

            cats = Reference(ws2, min_col=1, min_row=2, max_row=data_count + 1)
            avg_data = Reference(ws2, min_col=4, min_row=1, max_row=data_count + 1)
            ucl_data = Reference(ws2, min_col=6, min_row=1, max_row=data_count + 1)
            cl_data = Reference(ws2, min_col=7, min_row=1, max_row=data_count + 1)
            lcl_data = Reference(ws2, min_col=8, min_row=1, max_row=data_count + 1)

            xbar_chart.add_data(avg_data, titles_from_data=True)
            xbar_chart.add_data(ucl_data, titles_from_data=True)
            xbar_chart.add_data(cl_data, titles_from_data=True)
            xbar_chart.add_data(lcl_data, titles_from_data=True)

            # Add USL/LSL if available
            if has_spec_limits:
                usl_data = Reference(ws2, min_col=11, min_row=1, max_row=data_count + 1)
                lsl_data = Reference(ws2, min_col=12, min_row=1, max_row=data_count + 1)
                xbar_chart.add_data(usl_data, titles_from_data=True)
                xbar_chart.add_data(lsl_data, titles_from_data=True)

            xbar_chart.set_categories(cats)

            # Style: Avg=blue, UCL/LCL=red dashed, CL=green
            s_avg = xbar_chart.series[0]
            s_avg.graphicalProperties.line.solidFill = "0D6EFD"
            s_avg.graphicalProperties.line.width = 22000

            s_ucl = xbar_chart.series[1]
            s_ucl.graphicalProperties.line.solidFill = "FF0000"
            s_ucl.graphicalProperties.line.dashStyle = "dash"
            s_ucl.graphicalProperties.line.width = 15000

            s_cl = xbar_chart.series[2]
            s_cl.graphicalProperties.line.solidFill = "00B050"
            s_cl.graphicalProperties.line.width = 15000

            s_lcl = xbar_chart.series[3]
            s_lcl.graphicalProperties.line.solidFill = "FF0000"
            s_lcl.graphicalProperties.line.dashStyle = "dash"
            s_lcl.graphicalProperties.line.width = 15000

            if has_spec_limits:
                s_usl = xbar_chart.series[4]
                s_usl.graphicalProperties.line.solidFill = "E83E8C"
                s_usl.graphicalProperties.line.dashStyle = "lgDash"
                s_usl.graphicalProperties.line.width = 18000

                s_lsl = xbar_chart.series[5]
                s_lsl.graphicalProperties.line.solidFill = "E83E8C"
                s_lsl.graphicalProperties.line.dashStyle = "lgDash"
                s_lsl.graphicalProperties.line.width = 18000

            ws_chart.add_chart(xbar_chart, "A1")

            # --- R Chart ---
            r_chart = LineChart()
            r_chart.title = f"R 全距管制圖 - {field}"
            r_chart.y_axis.title = "全距"
            r_chart.y_axis.delete = False
            r_chart.x_axis.delete = False
            r_chart.y_axis.numFmt = '0.000'
            r_chart.x_axis.tickLblSkip = 1
            r_chart.width = 22
            r_chart.height = 14
            r_chart.style = 10
            r_chart.legend.position = 'b'
            r_chart.plotArea.layout = Layout(
                manualLayout=ManualLayout(x=0.05, y=0.12, w=0.90, h=0.68)
            )

            r_data = Reference(ws2, min_col=5, min_row=1, max_row=data_count + 1)
            r_ucl_ref = Reference(ws2, min_col=9, min_row=1, max_row=data_count + 1)
            r_cl_ref = Reference(ws2, min_col=10, min_row=1, max_row=data_count + 1)

            r_chart.add_data(r_data, titles_from_data=True)
            r_chart.add_data(r_ucl_ref, titles_from_data=True)
            r_chart.add_data(r_cl_ref, titles_from_data=True)
            r_chart.set_categories(cats)

            s_r = r_chart.series[0]
            s_r.graphicalProperties.line.solidFill = "6F42C1"
            s_r.graphicalProperties.line.width = 22000

            s_r_ucl = r_chart.series[1]
            s_r_ucl.graphicalProperties.line.solidFill = "FF0000"
            s_r_ucl.graphicalProperties.line.dashStyle = "dash"
            s_r_ucl.graphicalProperties.line.width = 15000

            s_r_cl = r_chart.series[2]
            s_r_cl.graphicalProperties.line.solidFill = "00B050"
            s_r_cl.graphicalProperties.line.width = 15000

            ws_chart.add_chart(r_chart, "A50")

            # --- Histogram ---
            if hist_data_rows > 0 and ws3 is not None:
                hist_chart = BarChart()
                hist_chart.title = f"量測值分佈直方圖 - {field}"
                hist_chart.y_axis.title = "頻次"
                hist_chart.y_axis.delete = False
                hist_chart.x_axis.delete = False
                hist_chart.width = 22
                hist_chart.height = 14
                hist_chart.style = 10
                hist_chart.type = "col"
                hist_chart.grouping = "clustered"
                hist_chart.legend.position = 'b'
                hist_chart.plotArea.layout = Layout(
                    manualLayout=ManualLayout(x=0.05, y=0.12, w=0.90, h=0.68)
                )

                hist_cats = Reference(ws3, min_col=1, min_row=2, max_row=hist_data_rows + 1)
                hist_vals = Reference(ws3, min_col=2, min_row=1, max_row=hist_data_rows + 1)

                hist_chart.add_data(hist_vals, titles_from_data=True)
                hist_chart.set_categories(hist_cats)

                s_hist = hist_chart.series[0]
                s_hist.graphicalProperties.solidFill = "0D6EFD"

                # 常態分佈曲線（LineChart 疊加）
                normal_chart = LineChart()
                normal_data_ref = Reference(ws3, min_col=4, min_row=1, max_row=hist_data_rows + 1)
                normal_chart.add_data(normal_data_ref, titles_from_data=True)
                normal_chart.smooth = True
                s_normal = normal_chart.series[0]
                s_normal.graphicalProperties.line.solidFill = "DC3545"
                s_normal.graphicalProperties.line.width = 20000
                s_normal.marker.symbol = "none"

                hist_chart += normal_chart

                ws_chart.add_chart(hist_chart, "A100")

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

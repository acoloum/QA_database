import numpy as np
from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, BarChart, Reference
from openpyxl.chart.layout import Layout, ManualLayout


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
                row += 1

        # --- Control Limits ---
        row += 1
        ws.merge_cells(f'A{row}:F{row}')
        ws[f'A{row}'] = "管制界限"
        ws[f'A{row}'].font = Font(name="微軟正黑體", size=12, bold=True)
        row += 1

        cl_items = [
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

        # Column widths
        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 18
        ws.column_dimensions['C'].width = 15

        # --- Sheet 2: Control Chart Data ---
        ws2 = wb.create_sheet(title="管制圖數據")
        # Headers include control limit columns for chart references
        data_headers = ["序號", "標籤", "日期", "平均值 (X̄)", "全距 (R)", "UCL", "CL", "LCL", "R_UCL"]
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
            # Control limit columns for chart series
            ws2.cell(row=r, column=6, value=round(x_ucl, 4))
            ws2.cell(row=r, column=7, value=round(x_cl, 4))
            ws2.cell(row=r, column=8, value=round(x_lcl, 4))
            ws2.cell(row=r, column=9, value=round(r_ucl, 4))

        for col_idx in range(1, 10):
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
            cumulative = 0
            hist_data_rows = len(counts)
            for i in range(len(counts)):
                label = f"{round(bin_edges[i], 3)} ~ {round(bin_edges[i + 1], 3)}"
                cumulative += counts[i]
                ws3.cell(row=i + 2, column=1, value=label).border = thin_border
                ws3.cell(row=i + 2, column=2, value=int(counts[i])).border = thin_border
                ws3.cell(row=i + 2, column=3, value=f"{round(cumulative / total * 100, 1)}%").border = thin_border

            for col_idx in range(1, 4):
                ws3.column_dimensions[get_column_letter(col_idx)].width = 20

        # ======== Sheet 4: Embedded Charts ========
        if avgs and len(avgs) >= 2:
            ws_chart = wb.create_sheet(title="圖表")
            data_count = len(avgs)

            # --- X-bar Control Chart ---
            xbar_chart = LineChart()
            xbar_chart.title = f"X̄ 平均值管制圖 - {field}"
            xbar_chart.y_axis.title = "量測值"
            xbar_chart.y_axis.delete = False
            xbar_chart.x_axis.delete = False
            xbar_chart.y_axis.tickLblPos = "low"
            xbar_chart.x_axis.tickLblPos = "low"
            xbar_chart.y_axis.numFmt = '0.000'
            xbar_chart.x_axis.tickLblSkip = 1
            xbar_chart.width = 40
            xbar_chart.height = 25
            xbar_chart.style = 10
            xbar_chart.legend.position = 'b'
            xbar_chart.legend.layout = Layout(
                manualLayout=ManualLayout(x=0.25, y=0.92, w=0.5, h=0.06)
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

            ws_chart.add_chart(xbar_chart, "A1")

            # --- R Chart ---
            r_chart = LineChart()
            r_chart.title = f"R 全距管制圖 - {field}"
            r_chart.y_axis.title = "全距"
            r_chart.y_axis.delete = False
            r_chart.x_axis.delete = False
            r_chart.y_axis.tickLblPos = "low"
            r_chart.x_axis.tickLblPos = "low"
            r_chart.y_axis.numFmt = '0.000'
            r_chart.x_axis.tickLblSkip = 1
            r_chart.width = 40
            r_chart.height = 25
            r_chart.style = 10
            r_chart.legend.position = 'b'
            r_chart.legend.layout = Layout(
                manualLayout=ManualLayout(x=0.25, y=0.92, w=0.5, h=0.06)
            )

            r_data = Reference(ws2, min_col=5, min_row=1, max_row=data_count + 1)
            r_ucl_ref = Reference(ws2, min_col=9, min_row=1, max_row=data_count + 1)

            r_chart.add_data(r_data, titles_from_data=True)
            r_chart.add_data(r_ucl_ref, titles_from_data=True)
            r_chart.set_categories(cats)

            s_r = r_chart.series[0]
            s_r.graphicalProperties.line.solidFill = "6F42C1"
            s_r.graphicalProperties.line.width = 22000

            s_r_ucl = r_chart.series[1]
            s_r_ucl.graphicalProperties.line.solidFill = "FF0000"
            s_r_ucl.graphicalProperties.line.dashStyle = "dash"
            s_r_ucl.graphicalProperties.line.width = 15000

            ws_chart.add_chart(r_chart, "A50")

            # --- Histogram ---
            if hist_data_rows > 0 and ws3 is not None:
                hist_chart = BarChart()
                hist_chart.title = f"量測值分佈直方圖 - {field}"
                hist_chart.y_axis.title = "頻次"
                hist_chart.y_axis.delete = False
                hist_chart.x_axis.delete = False
                hist_chart.y_axis.tickLblPos = "low"
                hist_chart.x_axis.tickLblPos = "low"
                hist_chart.width = 40
                hist_chart.height = 25
                hist_chart.style = 10
                hist_chart.type = "col"
                hist_chart.grouping = "clustered"
                hist_chart.legend = None

                hist_cats = Reference(ws3, min_col=1, min_row=2, max_row=hist_data_rows + 1)
                hist_vals = Reference(ws3, min_col=2, min_row=1, max_row=hist_data_rows + 1)

                hist_chart.add_data(hist_vals, titles_from_data=True)
                hist_chart.set_categories(hist_cats)

                s_hist = hist_chart.series[0]
                s_hist.graphicalProperties.solidFill = "0D6EFD"

                ws_chart.add_chart(hist_chart, "A100")

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output

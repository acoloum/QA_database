import datetime as dt

from sqlalchemy import event

from backend.extensions import db
from backend.models import CorrectiveAction, CustomerComplaint, NCMR, ShippingData, Vendor
from backend.services.quality_analytics_service import QualityAnalyticsService


def _make_ncmr(number, date, category, detail, vendor='供應商A', material='6061', product='管材'):
    return NCMR(
        ncmr_number=number,
        date=date,
        source='出貨',
        vendor=vendor,
        material=material,
        product_info=product,
        defect_quantity=1,
        defect_category=category,
        defect_detail=detail,
        status='待處理',
    )


def test_pareto_returns_sorted_counts_and_cumulative_percentage(app, db_session):
    """Pareto 應依件數排序，並計算累積百分比。"""
    with app.app_context():
        db_session.add_all([
            _make_ncmr('NCMR-P1', dt.date(2026, 5, 1), '尺寸', '外徑過大'),
            _make_ncmr('NCMR-P2', dt.date(2026, 5, 2), '尺寸', '內徑過小'),
            _make_ncmr('NCMR-P3', dt.date(2026, 5, 3), '外觀', '刮傷'),
            _make_ncmr('NCMR-P4', dt.date(2026, 4, 1), '包裝', '標籤錯誤'),
        ])
        db_session.commit()

        result = QualityAnalyticsService.pareto(
            source='ncmr',
            field='category',
            date_from=dt.date(2026, 5, 1),
            date_to=dt.date(2026, 5, 31),
        )

        assert result['total'] == 3
        assert result['items'][0]['label'] == '尺寸'
        assert result['items'][0]['count'] == 2
        assert result['items'][0]['cumulative_pct'] == 66.7
        assert result['items'][1]['label'] == '外觀'
        assert result['items'][1]['cumulative_pct'] == 100.0


def test_pareto_translates_ncmr_category_codes_to_readable_labels(app, db_session):
    """Pareto 橫座標應顯示不良大類文字，而不是只顯示代碼。"""
    with app.app_context():
        db_session.add_all([
            _make_ncmr('NCMR-C1', dt.date(2026, 5, 1), 'M', 'M-01: 鋁錠成分不符'),
            _make_ncmr('NCMR-C2', dt.date(2026, 5, 2), 'M', 'M-02: 鋁棒尺寸超差'),
        ])
        db_session.commit()

        result = QualityAnalyticsService.pareto(source='ncmr', field='category')

        assert result['items'][0]['label'] == 'M - 鋁材原料'


def test_defect_trends_returns_monthly_counts_by_top_categories(app, db_session):
    """分類趨勢應回傳月份序列與 Top 類別資料集。"""
    with app.app_context():
        db_session.add_all([
            _make_ncmr('NCMR-T1', dt.date(2026, 4, 10), '尺寸', '外徑過大'),
            _make_ncmr('NCMR-T2', dt.date(2026, 5, 10), '尺寸', '外徑過大'),
            _make_ncmr('NCMR-T3', dt.date(2026, 5, 11), '外觀', '刮傷'),
        ])
        db_session.commit()

        result = QualityAnalyticsService.defect_trends(
            source='ncmr',
            date_from=dt.date(2026, 4, 1),
            date_to=dt.date(2026, 5, 31),
            top_n=2,
        )

        assert result['months'] == ['2026-04', '2026-05']
        size_series = next(s for s in result['series'] if s['label'] == '尺寸')
        assert size_series['data'] == [1, 1]
        appearance_series = next(s for s in result['series'] if s['label'] == '外觀')
        assert appearance_series['data'] == [0, 1]


def test_capa_aging_buckets_open_items_and_average_close_days(app, db_session):
    """CAPA aging 應區分未結案桶、逾期清單與平均結案天數。"""
    with app.app_context():
        today = dt.date(2026, 5, 30)
        db_session.add_all([
            CorrectiveAction(
                eight_d_number='CAPA-A1',
                status='進行中',
                created_at=dt.datetime(2026, 5, 25, tzinfo=dt.timezone.utc),
                d0_deadline=dt.date(2026, 5, 29),
            ),
            CorrectiveAction(
                eight_d_number='CAPA-A2',
                status='進行中',
                created_at=dt.datetime(2026, 5, 12, tzinfo=dt.timezone.utc),
                d0_deadline=dt.date(2026, 6, 5),
            ),
            CorrectiveAction(
                eight_d_number='CAPA-A3',
                status='已結案',
                created_at=dt.datetime(2026, 5, 1, tzinfo=dt.timezone.utc),
                d8_close_date=dt.date(2026, 5, 11),
            ),
        ])
        db_session.commit()

        result = QualityAnalyticsService.capa_aging(today=today)

        assert result['buckets'] == {'0-7': 1, '8-14': 0, '15-30': 1, '31+': 0}
        assert result['open_count'] == 2
        assert result['overdue_count'] == 1
        assert result['overdue_items'][0]['number'] == 'CAPA-A1'
        assert result['avg_close_days'] == 10.0


def test_repeat_issues_groups_ncmr_by_vendor_material_product_and_category(app, db_session):
    """重複問題應依廠商、材質、產品與不良類別聚合。"""
    with app.app_context():
        db_session.add_all([
            _make_ncmr('NCMR-R1', dt.date(2026, 5, 1), '尺寸', '外徑過大'),
            _make_ncmr('NCMR-R2', dt.date(2026, 5, 3), '尺寸', '外徑過大'),
            _make_ncmr('NCMR-R3', dt.date(2026, 5, 5), '外觀', '刮傷'),
            CustomerComplaint(
                complaint_no='CC-R1',
                customer='客戶A',
                complaint_date=dt.date(2026, 5, 4),
                description='重複客訴',
                is_repeat=True,
                defect_category='尺寸',
            ),
        ])
        db_session.commit()

        result = QualityAnalyticsService.repeat_issues(
            date_from=dt.date(2026, 5, 1),
            date_to=dt.date(2026, 5, 31),
        )

        assert result['ncmr'][0]['count'] == 2
        assert result['ncmr'][0]['vendor'] == '供應商A'
        assert result['complaints'][0]['complaint_no'] == 'CC-R1'


def test_vendor_ranking_orders_worst_vendor_first(app, db_session):
    """供應商排名應依績效分數由低到高排序。"""
    with app.app_context():
        vendor_a = Vendor(name='供應商A')
        vendor_b = Vendor(name='供應商B')
        db_session.add_all([vendor_a, vendor_b])
        db_session.flush()
        db_session.add_all([
            ShippingData(date=dt.date(2026, 5, 1), vendor_id=vendor_a.id, material='6061', spec='10*2', is_ng=True),
            ShippingData(date=dt.date(2026, 5, 2), vendor_id=vendor_a.id, material='6061', spec='10*2', is_ng=True),
            ShippingData(date=dt.date(2026, 5, 3), vendor_id=vendor_b.id, material='6061', spec='10*2', is_ng=False),
        ])
        db_session.commit()

        result = QualityAnalyticsService.vendor_ranking(period='2026-05', limit=2)

        assert result[0]['vendor_name'] == '供應商A'
        assert result[0]['defect_rate'] == 100.0
        assert result[1]['vendor_name'] == '供應商B'


def _capture_sql(db_session):
    """註冊 before_cursor_execute 監聽，回傳收集到的 SQL 清單與 listener。"""
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_session.get_bind(), "before_cursor_execute", capture)
    return statements, capture


def test_pareto_aggregates_in_sql_with_group_by(app, db_session):
    """Pareto 應以 SQL GROUP BY 聚合，且不得 SELECT 整列實體（不得拉回『不良描述』）。"""
    with app.app_context():
        db_session.add_all([
            _make_ncmr('NCMR-S1', dt.date(2026, 5, 1), '尺寸', '外徑過大'),
            _make_ncmr('NCMR-S2', dt.date(2026, 5, 2), '尺寸', '內徑過小'),
            _make_ncmr('NCMR-S3', dt.date(2026, 5, 3), '外觀', '刮傷'),
        ])
        db_session.commit()

        statements, capture = _capture_sql(db_session)
        try:
            result = QualityAnalyticsService.pareto(
                source='ncmr',
                field='category',
                date_from=dt.date(2026, 5, 1),
                date_to=dt.date(2026, 5, 31),
                limit=10,
            )
        finally:
            event.remove(db_session.get_bind(), "before_cursor_execute", capture)

        # 結果等價
        assert result['total'] == 3
        assert result['items'][0]['label'] == '尺寸'
        assert result['items'][0]['count'] == 2
        # SQL 層面：聚合必須下推資料庫
        assert any('GROUP BY' in s.upper() for s in statements)
        # 欄位級聚合：不得 SELECT 整列實體（『不良描述』為 NCMR.description 欄位名）
        assert all('不良描述' not in s for s in statements)


def test_defect_trends_buckets_by_month_in_sql(app, db_session):
    """趨勢應以 SQL 月份函數分桶（sqlite strftime / postgres to_char），而非 Python strftime。"""
    with app.app_context():
        db_session.add_all([
            _make_ncmr('NCMR-B1', dt.date(2026, 4, 10), '尺寸', '外徑過大'),
            _make_ncmr('NCMR-B2', dt.date(2026, 5, 10), '尺寸', '外徑過大'),
            _make_ncmr('NCMR-B3', dt.date(2026, 5, 11), '外觀', '刮傷'),
        ])
        db_session.commit()

        statements, capture = _capture_sql(db_session)
        try:
            result = QualityAnalyticsService.defect_trends(
                source='ncmr',
                date_from=dt.date(2026, 4, 1),
                date_to=dt.date(2026, 5, 31),
                top_n=2,
            )
        finally:
            event.remove(db_session.get_bind(), "before_cursor_execute", capture)

        assert result['months'] == ['2026-04', '2026-05']
        size_series = next(s for s in result['series'] if s['label'] == '尺寸')
        assert size_series['data'] == [1, 1]
        # SQL 層面：月份分桶必須在資料庫執行
        assert any('strftime' in s.lower() or 'to_char' in s.lower() for s in statements)


def test_capa_aging_respects_overdue_limit(app, db_session):
    """capa_aging 應支援 overdue_limit 上限，逾期清單不得超過指定筆數。"""
    with app.app_context():
        today = dt.date(2026, 5, 30)
        db_session.add_all([
            CorrectiveAction(
                eight_d_number=f'CAPA-O{i}',
                status='進行中',
                created_at=dt.datetime(2026, 5, 1, tzinfo=dt.timezone.utc),
                d0_deadline=dt.date(2026, 5, 10),
            )
            for i in range(1, 4)
        ])
        db_session.commit()

        result = QualityAnalyticsService.capa_aging(today=today, overdue_limit=2)

        assert result['overdue_count'] == 3
        assert len(result['overdue_items']) == 2


def test_repeat_issues_selects_grouped_columns_only(app, db_session):
    """重複問題 NCMR 聚合不應 SELECT 整列實體（SQL 不得含『不良描述』欄位）。"""
    with app.app_context():
        db_session.add_all([
            _make_ncmr('NCMR-RR1', dt.date(2026, 5, 1), '尺寸', '外徑過大'),
            _make_ncmr('NCMR-RR2', dt.date(2026, 5, 3), '尺寸', '外徑過大'),
        ])
        db_session.commit()

        statements, capture = _capture_sql(db_session)
        try:
            result = QualityAnalyticsService.repeat_issues(
                date_from=dt.date(2026, 5, 1),
                date_to=dt.date(2026, 5, 31),
            )
        finally:
            event.remove(db_session.get_bind(), "before_cursor_execute", capture)

        assert result['ncmr'][0]['count'] == 2
        assert all('不良描述' not in s for s in statements)

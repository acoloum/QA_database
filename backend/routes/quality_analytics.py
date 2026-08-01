"""品質分析 API"""
from datetime import date

from flask import Blueprint, request

from ..services.quality_analytics_service import QualityAnalyticsService
from ..utils import (
    api_success,
    auth_required,
    bounded_int,
    parse_optional_date,
    require_permission,
)

quality_analytics_bp = Blueprint('quality_analytics', __name__)

# 參數邊界：top_n/limit 1..50、overdue_limit 1..100、日期範圍最多 366 天
_TOP_N_BOUNDS = (1, 50)
_LIMIT_BOUNDS = (1, 50)
_OVERDUE_LIMIT_BOUNDS = (1, 100)
_MAX_WINDOW_DAYS = 366


def _date_window():
    """解析並驗證 date_from/date_to 參數；格式或跨度錯誤拋 ValueError（由全域 handler 轉 400）。"""
    date_from = parse_optional_date(request.args.get('date_from'), 'date_from')
    date_to = parse_optional_date(request.args.get('date_to'), 'date_to')
    if date_from and date_to and (date_to - date_from).days + 1 > _MAX_WINDOW_DAYS:
        raise ValueError(f'日期範圍不得超過 {_MAX_WINDOW_DAYS} 天')
    return date_from, date_to


@quality_analytics_bp.route('/api/quality-analytics/pareto', methods=['GET'])
@auth_required
@require_permission('analytics.view')
def pareto(current_user):
    date_from, date_to = _date_window()
    data = QualityAnalyticsService.pareto(
        source=request.args.get('source', 'ncmr'),
        field=request.args.get('field', 'category'),
        date_from=date_from,
        date_to=date_to,
        limit=bounded_int(request.args.get('limit'), 10, *_LIMIT_BOUNDS),
    )
    return api_success(data)


@quality_analytics_bp.route('/api/quality-analytics/defect-trends', methods=['GET'])
@auth_required
@require_permission('analytics.view')
def defect_trends(current_user):
    date_from, date_to = _date_window()
    data = QualityAnalyticsService.defect_trends(
        source=request.args.get('source', 'ncmr'),
        date_from=date_from,
        date_to=date_to,
        top_n=bounded_int(request.args.get('top_n'), 5, *_TOP_N_BOUNDS),
    )
    return api_success(data)


@quality_analytics_bp.route('/api/quality-analytics/capa-aging', methods=['GET'])
@auth_required
@require_permission('analytics.view')
def capa_aging(current_user):
    return api_success(QualityAnalyticsService.capa_aging(
        overdue_limit=bounded_int(request.args.get('overdue_limit'), 10, *_OVERDUE_LIMIT_BOUNDS),
    ))


@quality_analytics_bp.route('/api/quality-analytics/repeat-issues', methods=['GET'])
@auth_required
@require_permission('analytics.view')
def repeat_issues(current_user):
    date_from, date_to = _date_window()
    data = QualityAnalyticsService.repeat_issues(
        date_from=date_from,
        date_to=date_to,
        limit=bounded_int(request.args.get('limit'), 10, *_LIMIT_BOUNDS),
    )
    return api_success(data)


@quality_analytics_bp.route('/api/quality-analytics/vendor-ranking', methods=['GET'])
@auth_required
@require_permission('analytics.view')
def vendor_ranking(current_user):
    period = request.args.get('period', date.today().strftime('%Y-%m'))
    limit = bounded_int(request.args.get('limit'), 10, *_LIMIT_BOUNDS)
    return api_success(QualityAnalyticsService.vendor_ranking(period, limit))

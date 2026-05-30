"""品質分析 API"""
from datetime import date, datetime

from flask import Blueprint, request

from ..services.quality_analytics_service import QualityAnalyticsService
from ..utils import api_error, api_success, auth_required

quality_analytics_bp = Blueprint('quality_analytics', __name__)


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    return datetime.strptime(raw, '%Y-%m-%d').date()


@quality_analytics_bp.route('/api/quality-analytics/pareto', methods=['GET'])
@auth_required
def pareto(current_user):
    try:
        data = QualityAnalyticsService.pareto(
            source=request.args.get('source', 'ncmr'),
            field=request.args.get('field', 'category'),
            date_from=_parse_date(request.args.get('date_from')),
            date_to=_parse_date(request.args.get('date_to')),
            limit=request.args.get('limit', 10, type=int),
        )
        return api_success(data)
    except Exception as e:
        return api_error(str(e), 400)


@quality_analytics_bp.route('/api/quality-analytics/defect-trends', methods=['GET'])
@auth_required
def defect_trends(current_user):
    try:
        data = QualityAnalyticsService.defect_trends(
            source=request.args.get('source', 'ncmr'),
            date_from=_parse_date(request.args.get('date_from')),
            date_to=_parse_date(request.args.get('date_to')),
            top_n=request.args.get('top_n', 5, type=int),
        )
        return api_success(data)
    except Exception as e:
        return api_error(str(e), 400)


@quality_analytics_bp.route('/api/quality-analytics/capa-aging', methods=['GET'])
@auth_required
def capa_aging(current_user):
    try:
        return api_success(QualityAnalyticsService.capa_aging())
    except Exception as e:
        return api_error(str(e), 400)


@quality_analytics_bp.route('/api/quality-analytics/repeat-issues', methods=['GET'])
@auth_required
def repeat_issues(current_user):
    try:
        data = QualityAnalyticsService.repeat_issues(
            date_from=_parse_date(request.args.get('date_from')),
            date_to=_parse_date(request.args.get('date_to')),
            limit=request.args.get('limit', 10, type=int),
        )
        return api_success(data)
    except Exception as e:
        return api_error(str(e), 400)


@quality_analytics_bp.route('/api/quality-analytics/vendor-ranking', methods=['GET'])
@auth_required
def vendor_ranking(current_user):
    try:
        period = request.args.get('period', date.today().strftime('%Y-%m'))
        limit = request.args.get('limit', 10, type=int)
        return api_success(QualityAnalyticsService.vendor_ranking(period, limit))
    except Exception as e:
        return api_error(str(e), 400)

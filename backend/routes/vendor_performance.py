"""廠商績效路由"""
from flask import Blueprint, request
from datetime import date

from ..services.vendor_performance_service import VendorPerformanceService
from ..utils import auth_required, api_success, api_error

vendor_perf_bp = Blueprint('vendor_performance', __name__)


@vendor_perf_bp.route('/api/vendor-performance', methods=['GET'])
@auth_required
def list_vendor_performance(current_user):
    """GET /api/vendor-performance?period=YYYY-MM"""
    period = request.args.get('period', date.today().strftime('%Y-%m'))
    try:
        data = VendorPerformanceService.list_by_period(period)
        return api_success(data)
    except Exception as e:
        return api_error(str(e), 500)


@vendor_perf_bp.route('/api/vendor-performance/<int:vendor_id>/history', methods=['GET'])
@auth_required
def vendor_history(current_user, vendor_id: int):
    """GET /api/vendor-performance/<vendor_id>/history?months=6"""
    months = int(request.args.get('months', 6))
    try:
        data = VendorPerformanceService.history(vendor_id, months)
        return api_success(data)
    except Exception as e:
        return api_error(str(e), 500)

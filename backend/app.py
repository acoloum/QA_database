import logging
import os
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, send_from_directory, abort
from flask_cors import CORS
from flasgger import Swagger
from datetime import datetime
from .config import SECRET_KEY, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS, SQLALCHEMY_ENGINE_OPTIONS, ALLOWED_ORIGINS
from .extensions import db, limiter
from .routes.auth import auth_bp
from .routes.admin import admin_bp
from .routes.shipping import shipping_bp
from .routes.patrol import patrol_bp
from .routes.rework import rework_bp
from .routes.ncmr import ncmr_bp
from .routes.tolerance import tolerance_bp
from .routes.extrusion_tolerance import extrusion_tolerance_bp
from .routes.attachment import attachment_bp
from .routes.task import task_bp
from .routes.complaint import complaint_bp
from .routes.capa import capa_bp
from .routes.vendor_performance import vendor_perf_bp
from .routes.quality_analytics import quality_analytics_bp
from .routes.pyrometry import pyrometry_bp
from .storage import create_storage_backend

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = SQLALCHEMY_ENGINE_OPTIONS
app.config['SWAGGER'] = {
    'title': 'QA Database API',
    'uiversion': 3,
    'version': '1.0.0',
    'description': 'API documentation for QA Database System',
    'specs_route': '/apidocs/'
}

Swagger(app)

# 非 debug 模式才啟用 rotating file handler（dev 環境直接看 console）
if not app.debug:
    os.makedirs('logs', exist_ok=True)
    file_handler = RotatingFileHandler('logs/error.log', maxBytes=10 * 1024 * 1024, backupCount=10)
    file_handler.setLevel(logging.ERROR)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.ERROR)

db.init_app(app)
limiter.init_app(app)

# 初始化儲存後端（可透過 STORAGE_BACKEND_TYPE / UPLOAD_FOLDER 環境變數切換）
app.config['STORAGE'] = create_storage_backend(app.config)

# Configure CORS — 明確指定允許來源，避免任意來源攜帶憑證
CORS(app, supports_credentials=True, origins=ALLOWED_ORIGINS)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(shipping_bp)
app.register_blueprint(patrol_bp)
app.register_blueprint(rework_bp)
app.register_blueprint(ncmr_bp)
app.register_blueprint(tolerance_bp)
app.register_blueprint(extrusion_tolerance_bp)
app.register_blueprint(attachment_bp)
app.register_blueprint(task_bp)
app.register_blueprint(complaint_bp)
app.register_blueprint(capa_bp)
app.register_blueprint(vendor_perf_bp)
app.register_blueprint(quality_analytics_bp)
app.register_blueprint(pyrometry_bp)

# ============================================================
# 前端 SPA 服務（生產：waitress 單一程序同時服務前端與 /api）
# 前端執行 `npm run build` 後產生 src_frontend/dist；此處直接由 Flask 服務，
# 與 /api 同源，故前端無需 proxy、也不會有 CORS 問題。
# ============================================================
FRONTEND_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src_frontend', 'dist'))


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """服務前端 SPA：實體靜態檔直接回傳，其餘路徑一律回 index.html 交由前端路由處理。

    註：/api/* 由各 blueprint 處理（路由較精確，會優先匹配）；
    未定義的 /api/* 在此回 404，避免回傳 HTML 混淆 API 呼叫端。
    """
    if path.startswith('api/'):
        abort(404)
    target = os.path.join(FRONTEND_DIST, path)
    if path and os.path.isfile(target):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, 'index.html')


# Global Error Handler (Optional but recommended)
# Global Error Handler
from .errors import APIError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

@app.errorhandler(APIError)
def handle_api_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

@app.errorhandler(HTTPException)
def handle_http_exception(error):
    """Handle standard Flask/Werkzeug HTTP exceptions (404, 405, etc.)"""
    response = jsonify({
        "success": False,
        "error": {
            "code": error.name.upper().replace(" ", "_"),
            "message": error.description,
        }
    })
    response.status_code = error.code
    return response

@app.errorhandler(ValueError)
def handle_value_error(error):
    """Handle ValueError as 400 Bad Request"""
    response = jsonify({
        "success": False,
        "error": {
            "code": "VALIDATION_ERROR",
            "message": str(error)
        }
    })
    response.status_code = 400
    return response

@app.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    """Handle Database errors"""
    from .utils import handle_db_error as utils_handle_db_error

    app.logger.exception("DB_ERROR: %s", str(error))

    # utils_handle_db_error 回傳 {"message": str, "field"?: str}，需攤平避免
    # message 變成巢狀物件（前端會顯示成 [object Object] 且無法定位欄位）
    info = utils_handle_db_error(error)

    response = jsonify({
        "success": False,
        "error": {
            "code": "DB_ERROR",
            "message": info["message"],
            "field": info.get("field"),
            "details": str(error) if app.debug else None
        }
    })
    response.status_code = 500
    return response

@app.errorhandler(Exception)
def handle_generic_error(error):
    """Handle unexpected errors"""
    app.logger.exception("INTERNAL_ERROR: %s", str(error))

    response = jsonify({
        "success": False,
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "伺服器發生未預期的錯誤",
            "details": str(error) if app.debug else None
        }
    })
    response.status_code = 500
    return response

if __name__ == '__main__':
    # Use waitress for production-like performance if available, else Flask default
    try:
        from waitress import serve
        print("=" * 60)
        print("Starting QC System Backend (Modular)")
        print("Listening on http://0.0.0.0:5001")
        print("=" * 60)
        serve(app, host='0.0.0.0', port=5001, threads=8)
    except ImportError:
        print("Waitress not found, using Flask development server")
        app.run(host='0.0.0.0', port=5001, debug=True)

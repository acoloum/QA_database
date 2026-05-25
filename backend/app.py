import logging
import os
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify
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
from .routes.cara import cara_bp

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
app.register_blueprint(cara_bp)

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

    friendly_message = utils_handle_db_error(error)

    response = jsonify({
        "success": False,
        "error": {
            "code": "DB_ERROR",
            "message": friendly_message,
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

from flask import Flask
from flask_cors import CORS
from .config import SECRET_KEY
from .routes.auth import auth_bp
from .routes.admin import admin_bp
from .routes.shipping import shipping_bp
from .routes.patrol import patrol_bp
from .routes.rework import rework_bp
from .routes.ncmr import ncmr_bp
from .routes.tolerance import tolerance_bp

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Configure CORS
CORS(app, supports_credentials=True)

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(shipping_bp)
app.register_blueprint(patrol_bp)
app.register_blueprint(rework_bp)
app.register_blueprint(ncmr_bp)
app.register_blueprint(tolerance_bp)

# Global Error Handler (Optional but recommended)
@app.errorhandler(500)
def internal_error(error):
    return {"error": "Internal Server Error"}, 500

if __name__ == '__main__':
    # Use waitress for production-like performance if available, else Flask default
    try:
        from waitress import serve
        print("=" * 60)
        print("Starting QC System Backend (Modular)")
        print("Listening on http://0.0.0.0:5001")
        print("=" * 60)
        serve(app, host='0.0.0.0', port=5001)
    except ImportError:
        print("Waitress not found, using Flask development server")
        app.run(host='0.0.0.0', port=5001, debug=True)

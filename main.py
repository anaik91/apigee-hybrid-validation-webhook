import os
import logging
import json
import sys
# --- IMPORTANT: Import timezone from datetime ---
from datetime import datetime, timezone

from flask import Flask, request, jsonify

# --- Custom JSON Log Formatter (Corrected) ---
class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Create a timezone-aware datetime object directly. This is the modern, correct way.
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        log_record = {
            "timestamp": timestamp,
            "severity": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "json_fields"):
            log_record.update(record.json_fields)
        return json.dumps(log_record)

# --- Centralized Logging Setup (No changes needed) ---
def setup_logging():
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(log_level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.handlers.clear()
    logger.addHandler(handler)
    return logger

logger = setup_logging()

# --- Application Factory ---
def create_app():
    """Creates and configures the Flask application."""
    app = Flask(__name__)

    @app.route('/healthz')
    def healthz():
        return jsonify({"status": "healthy"}), 200

    @app.route('/validate', methods=['POST'])
    def validate_pod():
        try:
            review_data = request.get_json()
            if not review_data:
                logger.warning("Received empty or invalid request body.")
                return jsonify({"error": "Invalid request body"}), 400
        except Exception as e:
            logger.error(f"Could not parse request JSON: {e}", exc_info=True)
            return jsonify({"error": "Invalid JSON received"}), 400

        request_info = review_data.get("request", {})
        uid = request_info.get("uid")
        pod = request_info.get("object", {})

        if not uid:
            logger.error("Request is missing required 'request.uid' field.", extra={"json_fields": review_data})
            return jsonify({"error": "Invalid AdmissionReview: missing uid"}), 400

        logger.info(f"Received validation request for UID: {uid}")

        pod_labels = pod.get("metadata", {}).get("labels", {})
        allowed = False
        message = "Pod rejected: Must include the label 'hello: world'."
        
        if pod_labels.get("hello") == "world":
            allowed = True
            message = "Pod allowed: Label 'hello: world' is present."

        logger.info(
            f"Validation decision for Pod '{pod.get('metadata', {}).get('name')}'",
            extra={"json_fields": {"uid": uid, "allowed": allowed, "decision_message": message}}
        )

        admission_response = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {"uid": uid, "allowed": allowed}
        }
        if not allowed:
            admission_response["response"]["status"] = {"code": 403, "message": message}

        return jsonify(admission_response)

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        logger.critical(f"An unhandled exception occurred: {e}", exc_info=True)
        return jsonify({"error": "An internal server error occurred."}), 500
        
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=True)
import os
import logging
import json
import sys
from datetime import datetime, timezone

from flask import Flask, request, jsonify

class JsonFormatter(logging.Formatter):
    """
    Custom log formatter that outputs log records as a JSON string.
    This format is automatically parsed by Google Cloud Logging as structured data.
    """
    def format(self, record):
        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        log_record = {
            "timestamp": timestamp,
            "severity": record.levelname,
            "message": record.getMessage(),
        }
        if hasattr(record, "json_fields"):
            log_record.update(record.json_fields)
        return json.dumps(log_record)

def setup_logging():
    """
    Sets up the root logger to output structured JSON to standard output.
    The log level is configurable via the LOG_LEVEL environment variable.
    """
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

def create_app():
    """Creates and configures the Flask application and its endpoints."""
    app = Flask(__name__)

    @app.route('/healthz')
    def healthz():
        """A simple health check endpoint for liveness probes."""
        return jsonify({"status": "healthy"}), 200

    @app.route('/validate', methods=['POST'])
    def audit_resource_change():
        """
        Intercepts Kubernetes AdmissionReview requests, logs the entire request
        for auditing purposes, and always allows the operation to proceed.
        """
        uid_for_response = "unknown-uid-on-error"
        try:
            admission_review_payload = request.get_json()
            if not admission_review_payload:
                logger.warning("Received empty or invalid request body.")
                return jsonify({"error": "Invalid request body"}), 400
            
            request_info = admission_review_payload.get("request", {})
            
            uid = request_info.get("uid")
            if not uid:
                logger.error("AdmissionReview is missing required 'request.uid' field.", extra={"json_fields": {"invalid_payload": admission_review_payload}})
                return jsonify({"error": "Invalid AdmissionReview: missing uid"}), 400
            
            uid_for_response = uid

            operation = request_info.get("operation", "UNKNOWN")
            user = request_info.get("userInfo", {}).get("username", "unknown_user")
            kind = request_info.get("kind", {}).get("kind", "UnknownKind")
            name = request_info.get("object", {}).get("metadata", {}).get("name", "unknown_name")

            summary_message = f"Audit: {operation} on {kind} '{name}' by user '{user}'"
            
            logger.info(
                summary_message,
                extra={"json_fields": {"admission_request": request_info}}
            )

        except Exception as e:
            logger.critical(
                f"Failed to process audit event for UID '{uid_for_response}', but allowing request to proceed. Error: {e}",
                exc_info=True
            )

        admission_response = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {"uid": uid_for_response, "allowed": True}
        }
        return jsonify(admission_response)

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        """
        Global error handler to catch any unhandled exceptions, preventing the app from
        crashing and ensuring a valid 'allow' response is sent if possible.
        """
        logger.critical(f"An unhandled exception occurred: {e}", exc_info=True)
        
        try:
            uid = request.get_json().get("request", {}).get("uid", "unknown-uid-on-crash")
            response_payload = {"uid": uid, "allowed": True, "status": {"message": "Webhook encountered a critical error but allowed the request."}}
            return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": response_payload})
        except:
             return jsonify({"error": "A critical internal server error occurred."}), 500
        
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=True)
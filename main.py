import os
import logging
import json
import sys
from datetime import datetime, timezone

from flask import Flask, request, jsonify

# --- Custom JSON Log Formatter (No changes needed) ---
class JsonFormatter(logging.Formatter):
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
    def validate_apigee_change():
        try:
            review_data = request.get_json()
            if not review_data:
                logger.warning("Received empty or invalid request body.")
                return jsonify({"error": "Invalid request body"}), 400
        except Exception as e:
            logger.error(f"Could not parse request JSON: {e}", exc_info=True)
            return jsonify({"error": "Invalid JSON received"}), 400

        # --- CORE AUDITING LOGIC ---
        try:
            request_info = review_data.get("request", {})
            uid = request_info.get("uid")

            if not uid:
                logger.error("Request is missing 'request.uid' field.", extra={"json_fields": review_data})
                return jsonify({"error": "Invalid AdmissionReview: missing uid"}), 400

            # Extract details for the audit log
            resource = request_info.get("resource", {})
            user_info = request_info.get("userInfo", {})
            obj = request_info.get("object", {})
            metadata = obj.get("metadata", {})
            
            # Create a structured log entry with all relevant details
            audit_details = {
                "uid": uid,
                "user": user_info.get("username"),
                "groups": user_info.get("groups"),
                "operation": request_info.get("operation"),
                "resource": {
                    "group": resource.get("group"),
                    "version": resource.get("version"),
                    "kind": request_info.get("kind", {}).get("kind"),
                    "name": metadata.get("name"),
                    "namespace": metadata.get("namespace"),
                    "spec": resource.get("spec")
                }
            }

            # The main log message for easy searching
            logger.info(
                f"Apigee resource change detected: {audit_details['operation']} on {audit_details['resource']['kind']} '{audit_details['resource']['name']}' by '{audit_details['user']}'",
                extra={"json_fields": {"audit_event": audit_details}}
            )

        except Exception as e:
            # If logging fails, we still allow the request but log the internal error
            logger.critical(f"Failed to process audit event, but allowing request. Error: {e}", exc_info=True)
            # Ensure we can still get the UID if possible
            uid = review_data.get("request", {}).get("uid", "unknown-uid")
            
        # --- ALWAYS ALLOW THE REQUEST ---
        # This makes the webhook a non-blocking auditor.
        admission_response = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {"uid": uid, "allowed": True}
        }
        return jsonify(admission_response)

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        logger.critical(f"An unhandled exception occurred: {e}", exc_info=True)
        # In a pure audit webhook, it might be safer to allow on failure
        # rather than blocking a legitimate change.
        try:
            uid = request.get_json().get("request", {}).get("uid", "unknown-uid-on-crash")
            response = {"uid": uid, "allowed": True, "status": {"message": "Webhook failed but allowed request."}}
            return jsonify({"apiVersion": "admission.k8s.io/v1", "kind": "AdmissionReview", "response": response})
        except:
             # If we can't even parse the request to get a UID, we can't form a valid response.
             # This will cause the API server request to fail, which is a safe default.
             return jsonify({"error": "A critical internal server error occurred."}), 500
        
    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)), debug=True)
import os
from flask import Flask, request, jsonify
import logging
import google.cloud.logging # Imports the Cloud Logging client library

# === Setup Google Cloud's structured logging ===
# Instantiates a client
client = google.cloud.logging.Client()

# Retrieves a Cloud Logging handler based on the environment
# (this will appropriately format logs for Cloud Run)
handler = client.get_default_handler()

# The flask logger
cloud_logger = logging.getLogger("cloudLogger")
cloud_logger.setLevel(logging.INFO)
cloud_logger.addHandler(handler)
# === End of logging setup ===

app = Flask(__name__)

@app.route('/', methods=['POST'])
def validate_pod():
    try:
        admission_review_req = request.json
        uid = admission_review_req["request"]["uid"]

        # Log the entire incoming request as a structured JSON payload
        cloud_logger.info(
            f"Received AdmissionReview request for UID: {uid}", 
            extra={"json_fields": admission_review_req}
        )

    except Exception as e:
        cloud_logger.error(f"Failed to parse request: {e}")
        return jsonify({"error": f"Failed to parse request: {e}"}), 400

    req = admission_review_req["request"]
    pod = req.get("object", {})
    pod_labels = pod.get("metadata", {}).get("labels", {})

    allowed = False
    message = "Pod rejected: Must include the label 'hello: world'."

    if pod_labels.get("hello") == "world":
        allowed = True
        message = "Pod allowed: Label 'hello: world' is present."

    # Log the result with key-value pairs that will become searchable fields
    cloud_logger.info(
        f"Validation result for {uid}", 
        extra={
            "json_fields": {
                "uid": uid,
                "allowed": allowed,
                "message": message,
                "pod_name": pod.get("metadata", {}).get("name")
            }
        }
    )

    admission_review_resp = {
        "apiVersion": "admission.k8s.io/v1",
        "kind": "AdmissionReview",
        "response": {
            "uid": uid,
            "allowed": allowed,
        }
    }

    if not allowed:
        admission_review_resp["response"]["status"] = {
            "code": 403,
            "message": message
        }

    return jsonify(admission_review_resp), 200

# This part is only for local testing and won't be used in Cloud Run
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
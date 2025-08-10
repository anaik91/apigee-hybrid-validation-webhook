#!/bin/bash

# --- CONFIGURATION ---
export PROJECT_ID="apigee-hybrid-378710"
export REGION="us-central1"

# The "folder" for our images
export REPOSITORY_NAME="k8s-webhooks" 

# The name of this specific image
export IMAGE_NAME="hello-world-validator"

# The name for our Cloud Run service
export SERVICE_NAME="k8s-admission-webhook"
# --- END CONFIGURATION ---

# Set the project for the gcloud CLI
gcloud config set project ${PROJECT_ID}

gcloud builds submit . \
  --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:latest"

# Deploy the container to Cloud Run
gcloud run deploy ${SERVICE_NAME} \
    --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:latest" \
    --region=${REGION} \
    --platform managed \
    --allow-unauthenticated

WEBHOOK_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')
export WEBHOOK_URL 
echo "Webhook URL: ${WEBHOOK_URL}"

curl -s https://pki.goog/roots.pem > roots.pem
CA_BUNDLE=$(cat roots.pem | base64 -w 0)
export CA_BUNDLE 

cat > web_hook.yaml << EOF
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  # The name of this configuration object
  name: demo-cloudrun-validation-webhook
webhooks:
  - name: helloworld.example.com # A unique name for your webhook
    namespaceSelector:
      matchLabels:
        pod-validation: enabled
    clientConfig:
      # This section tells the API server how to connect to your service
      url: $WEBHOOK_URL/validate
      caBundle: $CA_BUNDLE
    rules:
      # This section defines which requests to intercept
      - operations: ["CREATE"]
        apiGroups: [""]
        apiVersions: ["v1"]
        resources: ["pods"]
    # If the webhook fails to respond, the request will be rejected.
    failurePolicy: Fail
    # This webhook only intercepts requests; it doesn't modify them.
    sideEffects: None
    # The API version for the AdmissionReview object sent to your webhook.
    admissionReviewVersions: ["v1"]
EOF

kubectl apply -f web_hook.yaml

kubectl get validatingwebhookconfiguration demo-cloudrun-validation-webhook
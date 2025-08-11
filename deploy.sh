#!/bin/bash

SCRIPTPATH="$(
    cd "$(dirname "$0")" || exit >/dev/null 2>&1
    pwd -P
)"

# shellcheck disable=SC1091
source "$SCRIPTPATH/env.sh"

gcloud builds submit . \
  --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:latest"

# Deploy the container to Cloud Run
gcloud run deploy "${SERVICE_NAME}" \
    --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:latest" \
    --region="${REGION}" \
    --platform managed \
    --allow-unauthenticated

WEBHOOK_URL=$(gcloud run services describe \
  "${SERVICE_NAME}" --platform managed \
  --region "${REGION}" --format 'value(status.url)')

export WEBHOOK_URL 
echo "Webhook URL: ${WEBHOOK_URL}"

curl -s https://pki.goog/roots.pem > roots.pem
CA_BUNDLE=$(cat roots.pem | base64 -w 0)
export CA_BUNDLE 

cat > web_hook.yaml << EOF
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  # A more descriptive name for the webhook's purpose
  name: $WEBHOOK_NAME
webhooks:
  - name: apigee-auditor.example.com
    # Optional: If you want this to apply cluster-wide, remove the namespaceSelector.
    # If you only want it for specific Apigee namespaces, keep it.
    namespaceSelector:
      matchLabels:
        apigee-runtime: "true" # Example label: you must label your Apigee namespace
    clientConfig:
      url: $WEBHOOK_URL/validate
      caBundle: $CA_BUNDLE
    
    # --- THIS IS THE KEY CHANGE ---
    # These rules tell the API server which resources to send to the webhook.
    rules:
      - operations: ["CREATE", "UPDATE"]
        apiGroups: ["apigee.cloud.google.com"]
        apiVersions: ["v1alpha1", "v1alpha2", "v1alpha3"]
        resources:
          # v1alpha1 resources
          - apigeeredis
          - apigeedatastores
          - apigeeissues
          - apigeerouteconfigs
          - cassandradatareplications
          - secretrotations
          # v1alpha2 resources
          - apigeeorganizations
          - apigeeenvironments
          - apigeeroutes
          - apigeetelemetries
          # v1alpha3 resources
          # - apigeedeployments
    # --- END OF KEY CHANGE ---

    # It's critical to set failurePolicy to Ignore for a non-blocking audit webhook.
    # This ensures that if your webhook service goes down, it doesn't block Apigee changes.
    failurePolicy: Ignore
    sideEffects: None
    admissionReviewVersions: ["v1"]
EOF

kubectl apply -f web_hook.yaml

kubectl get validatingwebhookconfiguration "$WEBHOOK_NAME"
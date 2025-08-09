# Kubernetes Validating Webhook on Google Cloud Run

This project is a "Hello World" example of a Kubernetes [Validating Admission Webhook](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/) implemented in Python with Flask and deployed as a serverless function on **Google Cloud Run**.

## What It Does

The webhook intercepts `CREATE` requests for Pods in any namespace that has the label `pod-validation=enabled`.

It will **REJECT** any Pod that does not have the label `hello: world`.

### Architecture

1.  A user runs `kubectl apply -f pod.yaml`.
2.  The Kubernetes API Server checks its `ValidatingWebhookConfiguration`.
3.  If the request matches the rules (a Pod creation in a labeled namespace), the API server sends an `AdmissionReview` request to the public URL of our Cloud Run service.
4.  The Python Flask app on Cloud Run inspects the request.
5.  It sends back an `AdmissionReview` response indicating `allowed: true` or `allowed: false`.
6.  The Kubernetes API Server enforces the decision.

## Prerequisites

*   `gcloud` CLI installed and authenticated.
*   `kubectl` CLI installed and configured to point to a Kubernetes cluster.
*   A Google Cloud project with billing enabled.
*   The following Google Cloud APIs enabled in your project:
    *   Cloud Build API (`cloudbuild.googleapis.com`)
    *   Artifact Registry API (`artifactregistry.googleapis.com`)
    *   Cloud Run API (`run.googleapis.com`)

## Deployment Steps

#### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd <your-repo-directory>
```

#### 2. Configure Environment Variables

Set the following environment variables in your terminal. These will be used in subsequent commands.

```bash
# --- CONFIGURE THESE VALUES ---
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1" # e.g., us-central1
# --- END CONFIGURATION ---

# The name for the Artifact Registry "folder"
export REPOSITORY_NAME="k8s-webhooks"

# The name for this specific container image
export IMAGE_NAME="hello-world-validator"

# The name for our Cloud Run service
export SERVICE_NAME="k8s-admission-webhook"

# Set gcloud to use your project
gcloud config set project ${PROJECT_ID}
```

#### 3. Create the Artifact Registry Repository

This is a one-time setup step to create a "folder" to store your container images.

```bash
gcloud artifacts repositories create ${REPOSITORY_NAME} \
    --repository-format=docker \
    --location=${REGION} \
    --description="Repository for Kubernetes webhook images"
```

#### 4. Build and Deploy to Cloud Run

This single command builds your container image using Cloud Build and deploys it to Cloud Run.

```bash
# Build and push the image
gcloud builds submit . --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:latest"

# Deploy the service
gcloud run deploy ${SERVICE_NAME} \
    --image "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY_NAME}/${IMAGE_NAME}:latest" \
    --region=${REGION} \
    --allow-unauthenticated
```

#### 5. Configure Kubernetes

Now we will tell Kubernetes about our new webhook.

**A. Label the target namespace:**

The webhook will only apply to namespaces with this label.
```bash
# Create a namespace to test in
kubectl create namespace production-apps

# Add the required label
kubectl label namespace production-apps pod-validation=enabled
```

**B. Get the required values for the webhook configuration:**

```bash
# Get the Cloud Run URL
export WEBHOOK_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')

# Download Google's root CA certificates
curl -s https://pki.goog/roots.pem > roots.pem

# Base64-encode the CA bundle
export CA_BUNDLE=$(cat roots.pem | base64 -w 0) # Use `base64 -b 0` on macOS
```

**C. Apply the ValidatingWebhookConfiguration:**

This command substitutes the placeholders in the template YAML and applies it to your cluster.
```bash
# Create a temporary copy
cp webhook-config.yaml webhook-config-final.yaml

# Replace placeholders
sed -i.bak "s|WEBHOOK_URL_PLACEHOLDER|${WEBHOOK_URL}|g" webhook-config-final.yaml
sed -i.bak "s|CA_BUNDLE_PLACEHOLDER|${CA_BUNDLE}|g" webhook-config-final.yaml

# Apply the final configuration
kubectl apply -f webhook-config-final.yaml
```

## Testing the Webhook

#### Test 1: Rejected Pod

Try to create a Pod without the required label in the `production-apps` namespace. This should **fail**.

```bash
kubectl apply -f pod-fail.yaml -n production-apps
```
**Expected Output:**
```
Error from server: error when creating "pod-fail.yaml": admission webhook "helloworld.example.com" denied the request: Pod rejected: Must include the label 'hello: world'.
```

#### Test 2: Allowed Pod

Try to create a Pod *with* the required label. This should **succeed**.
```bash
kubectl apply -f pod-success.yaml -n production-apps
```
**Expected Output:**
```
pod/pod-with-label created
```

## Logging and Debugging

To see the logs from your Python application, check the Cloud Run logs:
```bash
gcloud run services logs tail ${SERVICE_NAME} --region=${REGION}
```

## Cleanup

To remove all the resources created in this demo, run the following commands:
```bash
# Delete Kubernetes resources
kubectl delete validatingwebhookconfiguration demo-cloudrun-validation-webhook
kubectl delete namespace production-apps

# Delete Google Cloud resources
gcloud run services delete ${SERVICE_NAME} --region=${REGION}
gcloud artifacts repositories delete ${REPOSITORY_NAME} --location=${REGION}
```
#!/bin/bash

# --- CONFIGURATION ---
export PROJECT_ID="apigee-hybrid-378710"
export REGION="us-central1"

# The "folder" for our images
export REPOSITORY_NAME="k8s-webhooks" 

# The name of this specific image
export IMAGE_NAME="hello-world-validator"

# The name for our Cloud Run service
export SERVICE_NAME="k8s-admission-webhook-v1"

export WEBHOOK_NAME="apigee-change-auditor-webhook"
# --- END CONFIGURATION ---

# Set the project for the gcloud CLI
gcloud config set project ${PROJECT_ID}
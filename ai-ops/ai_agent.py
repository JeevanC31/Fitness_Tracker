#!/usr/bin/env python3
"""
FitTrack AI SRE Operations Agent
This script scans log files, identifies issues (such as MongoDB connection failures,
out-of-memory errors, invalid secrets, etc.), explains the issues, and automatically
generates a Shell recovery script or Kubernetes patch to resolve the issue.
"""

import sys
import os
import re
import argparse

# Common offline heuristics for DevOps/Kubernetes troubleshooting
HEURISTICS = [
    {
        "pattern": r"(MongoDB connection error|MongooseServerSelectionError|failed to connect to server|Database connection failed)",
        "name": "Database Connectivity Issue",
        "description": "The application is unable to reach the MongoDB database. This usually means the MongoDB service is down, the connection string in MONGODB_URI is misconfigured, or there is a network policy blocking communication.",
        "remediation": "1. Verify MongoDB deployment state.\n2. Verify MongoDB ClusterIP service name aligns with MONGODB_URI.\n3. Verify network policies allow communication between namespaces.",
        "script": """#!/bin/bash
echo "=== Diagnosing MongoDB Service ==="
kubectl get pods -n fitness-tracker -l app=mongodb
kubectl get svc -n fitness-tracker mongodb-service

echo "=== Restarting MongoDB Deployment ==="
kubectl rollout restart deployment/mongodb -n fitness-tracker
kubectl rollout status deployment/mongodb -n fitness-tracker
"""
    },
    {
        "pattern": r"(JWT_SECRET is required|must provide JWT_SECRET|JWT_SECRET is missing|invalid jwt key)",
        "name": "Missing Authentication Configuration",
        "description": "The JWT_SECRET environment variable is either empty, missing, or failed to inject from the Secret manifest.",
        "remediation": "1. Check if the 'fitness-secrets' Secret resource exists.\n2. Confirm the key name maps to 'JWT_SECRET'.\n3. Verify EnvRef binding in the deployment manifest.",
        "script": """#!/bin/bash
echo "=== Checking Secrets ==="
kubectl get secret fitness-secrets -n fitness-tracker -o yaml

echo "=== Verifying Deployment Secrets Binding ==="
kubectl describe deployment/fitness-tracker-app -n fitness-tracker | grep JWT_SECRET
"""
    },
    {
        "pattern": r"(JavaScript heap out of memory|Fatal error in V8: Garbage collection|OOM|Exit Code 137)",
        "name": "Out Of Memory (OOM) Crash",
        "description": "The Node.js container exceeded its allocated memory limits (e.g. limits.memory in the deployment) or hit the V8 default heap size.",
        "remediation": "1. Increase the container memory limits inside app-deployment.yaml.\n2. Set standard environment variable Node parameter '--max-old-space-size=450'.",
        "script": """#!/bin/bash
echo "=== Patching Application Memory Limits ==="
kubectl patch deployment fitness-tracker-app -n fitness-tracker --type='json' -p='[
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "1Gi"},
  {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "256Mi"}
]'
kubectl rollout status deployment/fitness-tracker-app -n fitness-tracker
"""
    },
    {
        "pattern": r"(EADDRINUSE|port already in use|bind failed)",
        "name": "Port Collision Error",
        "description": "The port 5000 is already bound by another container, service, or server running on the host system.",
        "remediation": "1. Identify the process utilizing the port.\n2. Kill the conflicting process or change the port inside configmap.yaml.",
        "script": """#!/bin/bash
echo "=== Checking port 5000 usage ==="
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
  netstat -ano | findstr :5000
else
  sudo lsof -i :5000
fi
"""
    }
]

def analyze_logs(log_content):
    print("AI Operations Agent: Starting Analysis...\n")
    found_issue = False
    
    for issue in HEURISTICS:
        if re.search(issue["pattern"], log_content, re.IGNORECASE):
            found_issue = True
            print(f"[DETECTED ISSUE] {issue['name']}")
            print("=" * 50)
            print(f"Description:\n{issue['description']}\n")
            print(f"Remediation Steps:\n{issue['remediation']}\n")
            
            # Write out recovery script
            script_filename = "auto_recover.sh"
            with open(script_filename, "w") as f:
                f.write(issue["script"])
            os.chmod(script_filename, 0o755)
            
            print(f"Automated Recovery Script Generated: ./{script_filename}")
            print("=" * 50)
            break
            
    if not found_issue:
        print("[OK] Analysis Complete: No known system errors detected in the logs.")
        # Create standard cluster status diagnosis script
        script_filename = "cluster_diag.sh"
        diag_script = """#!/bin/bash
echo "=== Running Kubernetes Cluster Diagnostics ==="
kubectl get nodes
kubectl get namespaces
kubectl get all -A
"""
        with open(script_filename, "w") as f:
            f.write(diag_script)
        os.chmod(script_filename, 0o755)
        print(f"Diagnostic Script Generated: ./{script_filename}")

def main():
    parser = argparse.ArgumentParser(description="AI SRE Agent for EKS troubleshooting.")
    parser.add_argument("--log-file", help="Path to the application log file to analyze")
    parser.add_argument("--raw-log", help="Raw text of logs to analyze directly")
    
    args = parser.parse_args()
    
    content = ""
    if args.log_file:
        if os.path.exists(args.log_file):
            with open(args.log_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        else:
            print(f"Error: log file {args.log_file} does not exist.")
            sys.exit(1)
    elif args.raw_log:
        content = args.raw_log
    else:
        # Check standard input
        if not sys.stdin.isatty():
            content = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(1)
            
    if content.strip():
        analyze_logs(content)
    else:
        print("Error: No log input provided.")
        sys.exit(1)

if __name__ == "__main__":
    main()

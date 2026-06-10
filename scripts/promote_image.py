#!/usr/bin/env python3
"""
Docker Image Promotion Automation Script
This script promotes a Docker image from a source repository/tag to a target repository/tag.
It facilitates deploying the exact same tested binary between environments (e.g., dev -> staging -> prod) without rebuilding.
"""

import sys
import os
import subprocess
import argparse
from datetime import datetime

# Setup log file
LOG_FILE = "promotion.log"

def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] [{level}] {message}"
    print(formatted_msg)
    with open(LOG_FILE, "a") as f:
        f.write(formatted_msg + "\n")

def run_command(cmd, shell=False):
    log(f"Running command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.stdout:
            log(f"Command Output:\n{result.stdout.strip()}", "DEBUG")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Command failed with exit code {e.returncode}", "ERROR")
        log(f"Stderr:\n{e.stderr.strip()}", "ERROR")
        return False

def promote(source_repo, target_repo, tag, target_tag=None, registry_user=None, registry_pass=None):
    if not target_tag:
        target_tag = tag

    full_source = f"{source_repo}:{tag}"
    full_target = f"{target_repo}:{target_tag}"

    log(f"Starting promotion flow: {full_source} -> {full_target}")

    # Optional Login to target registry
    if registry_user and registry_pass:
        log("Logging into registry...")
        login_cmd = ["docker", "login", "-u", registry_user, "-p", registry_pass]
        if not run_command(login_cmd):
            log("Authentication failed. Aborting.", "ERROR")
            return False

    # Step 1: Pull source image
    log(f"Pulling source image: {full_source}")
    pull_cmd = ["docker", "pull", full_source]
    if not run_command(pull_cmd):
        log("Failed to pull source image.", "ERROR")
        return False

    # Step 2: Tag image
    log(f"Re-tagging image to: {full_target}")
    tag_cmd = ["docker", "tag", full_source, full_target]
    if not run_command(tag_cmd):
        log("Failed to tag image.", "ERROR")
        return False

    # Step 3: Push target image
    log(f"Pushing promoted image: {full_target}")
    push_cmd = ["docker", "push", full_target]
    if not run_command(push_cmd):
        log("Failed to push image to target repository.", "ERROR")
        return False

    # Step 4: Validate promotion
    log("Validating promotion...")
    inspect_cmd = ["docker", "image", "inspect", full_target]
    if not run_command(inspect_cmd):
        log("Validation check failed: Promoted image cannot be inspected locally.", "WARNING")
    else:
        log("Validation check passed successfully.", "INFO")

    log(f"Promotion completed successfully for {full_target}!", "SUCCESS")
    return True

def main():
    parser = argparse.ArgumentParser(description="Promote a Docker image from dev to staging/prod without rebuilding.")
    parser.add_argument("--source-repo", required=True, help="Source repository (e.g., <ecr-registry>/fitness-tracker-app)")
    parser.add_argument("--target-repo", required=True, help="Target repository (e.g., <ecr-registry>/fitness-tracker-app)")
    parser.add_argument("--tag", required=True, help="Source image tag (e.g., develop)")
    parser.add_argument("--target-tag", help="Target tag (defaults to source tag if not specified)")
    parser.add_argument("--user", help="Docker registry username (optional)")
    parser.add_argument("--password", help="Docker registry password (optional)")

    args = parser.parse_args()

    success = promote(
        source_repo=args.source_repo,
        target_repo=args.target_repo,
        tag=args.tag,
        target_tag=args.target_tag,
        registry_user=args.user,
        registry_pass=args.password
    )

    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()

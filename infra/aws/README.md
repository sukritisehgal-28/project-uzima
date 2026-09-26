# AWS

- EKS: agent sandboxes (one Job per hospital, `infra/k8s/agent-job-template.yaml`), orchestrator, collector, handoff.
- Separate node group or cluster for the Twilio synchronizer.
- DynamoDB table `marco-polo` (`dynamodb-table.json`): events (EMTALA log), bed memory with 30-min TTL, encrypted twins.
- AWS Location Service: a route calculator for road drive times (replaces the straight-line estimates in data/hospitals.json) and a map for the dashboard.
- Fallback: `apprunner.yaml` runs the same container without Kubernetes.
- Secrets from `.env.example` go into the `marco-polo-secrets` Kubernetes secret.

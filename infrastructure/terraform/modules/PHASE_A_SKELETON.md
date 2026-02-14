# Phase A/B Serverless Module Status

Phase A delivered module scaffolding. Phase B now adds concrete resources with feature flags.

Modules added:
- `static_web`: planned S3/CloudFront/Route53/ACM frontend hosting.
- `api_gateway`: planned API Gateway HTTP API resources.
- `lambda_api`: planned synchronous Lambda API handlers.
- `lambda_workers`: planned async/background Lambda workers.
- `queues`: planned SQS queues for reconciliation/invoice/meter jobs.
- `storage`: planned S3 buckets for uploads/exports.

Serverless wiring flag:

```hcl
enable_serverless_phase_a = false
```

Phase B creation flags:

```hcl
enable_serverless_phase_b = true
create_lambda_functions   = false # set true after lambda artifacts are uploaded
```

Notes:
1. S3, SQS, API Gateway, and CloudFront resources are created when `enable_serverless_phase_b = true`.
2. Lambda functions require valid S3 artifact keys and `create_lambda_functions = true`.
3. ECS path remains intact for parallel cutover.

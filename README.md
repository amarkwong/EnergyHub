# EnergyHub

Energy management and invoice reconciliation platform for the Australian National Electricity Market (NEM).

## Features

- **NEM12 Parser**: Process and analyze NEM12 metering data files
- **Invoice Calculator**: Calculate expected charges based on consumption and tariffs
- **Invoice Parser**: Extract data from PDF invoices using OCR (Tesseract)
- **Reconciliation Engine**: Compare invoiced vs calculated values line-by-line
- **Tariff Database**: Access network tariffs from Australian distributors
- **Consumption Charts**: Visualize energy usage patterns

## Supported Network Providers

| State | Providers |
|-------|-----------|
| NSW | Ausgrid, Endeavour Energy, Essential Energy |
| QLD | Energex, Ergon Energy |
| VIC | AusNet Services, CitiPower, Jemena, Powercor, United Energy |
| ACT | Evoenergy |
| TAS | TasNetworks |

## Tech Stack

- **Backend**: Python (FastAPI), Julia (NEM12 processing)
- **Frontend**: React, TypeScript, Tailwind CSS, Recharts
- **Infrastructure**: Docker, AWS (ECS, RDS, ECR), Terraform
- **CI/CD**: GitHub Actions

## Project Structure

```
EnergyHub/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── services/     # Business logic
│   │   ├── schemas/      # Pydantic models
│   │   └── core/         # Configuration
│   └── tests/            # Backend tests
├── frontend/
│   ├── src/
│   │   ├── components/   # React components
│   │   ├── pages/        # Page components
│   │   ├── api/          # API client
│   │   └── types/        # TypeScript types
│   └── e2e/              # E2E tests
├── server/
│   └── nem12loader.jl    # Julia NEM12 parser
├── infrastructure/
│   ├── docker/           # Docker configuration
│   └── terraform/        # Infrastructure as Code
└── .github/
    └── workflows/        # CI/CD pipelines
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- (Optional) Julia 1.9+ for NEM12 processing

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/energyhub.git
   cd energyhub
   ```

2. **Start with Docker Compose**
   ```bash
   cd infrastructure/docker
   docker compose up -d
   ```

   This starts:
   - Backend API at http://localhost:8000
   - Frontend at http://localhost:3000
   - PostgreSQL database

3. **Or run services separately**

   Backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

   Frontend:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

### Running Tests

Backend:
```bash
cd backend
pytest
```

Frontend:
```bash
cd frontend
npm test
npm run test:e2e
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/nem12/upload` | Upload NEM12 file |
| `GET /api/nem12/{id}/summary` | Get consumption summary |
| `POST /api/invoices/upload` | Upload invoice PDF |
| `POST /api/invoices/calculate` | Calculate expected invoice |
| `GET /api/tariffs/network/{provider}` | Get network tariffs |
| `POST /api/reconciliation/run` | Run invoice reconciliation |

## Deployment

### AWS Deployment

1. Configure AWS credentials
2. Initialize Terraform:
   ```bash
   cd infrastructure/terraform
   terraform init
   terraform plan
   terraform apply
   ```

3. Push images to ECR and deploy via GitHub Actions

## Privacy Considerations

- NEM12 data is considered private user data
- Files are processed locally and not shared
- For production, implement proper authentication and data encryption

## License

Proprietary - All rights reserved

# AIGYM Codebase Documentation

## System Overview

AIGYM is a learning system for AI agents with a modular architecture designed for scalability and extensibility. The system enables AI agents to learn progressively through task execution, evaluation, and reflection.

## Architecture

```mermaid
graph TD
    subgraph Client
        UI[User Interface]
    end

    subgraph "API Layer"
        API[Main API]
        SRA[Solution Runner API]
    end

    subgraph "Processing Layer"
        Judge[Task Judge]
        Worker[Celery Worker]
        Trainer[Model Trainer]
    end

    subgraph "Storage Layer"
        DB[(PostgreSQL)]
        Redis[(Redis)]
        VS[(Qdrant Vector Store)]
    end

    subgraph "Execution Layer"
        SR[Docker Runner]
        Containers[Solution Containers]
    end

    UI --> API
    API --> Judge
    API --> Worker
    API --> DB
    API --> Redis
    API --> VS

    Judge --> SRA
    SRA --> SR
    SR --> Containers

    Worker --> DB
    Worker --> VS
    Worker --> Redis

    Trainer --> DB
    Trainer --> Redis

    classDef api fill:#bbf,stroke:#333,stroke-width:2px;
    classDef storage fill:#f9f,stroke:#333,stroke-width:2px;
    classDef processing fill:#bfb,stroke:#333,stroke-width:2px;
    classDef execution fill:#fbb,stroke:#333,stroke-width:2px;

    class API,SRA api;
    class DB,Redis,VS storage;
    class Judge,Worker,Trainer processing;
    class SR,Containers execution;
```

## Component Details

### API Layer

#### Main API (`api/main.py`)
- **Purpose**: Main entry point for client interactions
- **Technologies**: FastAPI, Pydantic
- **Endpoints**:
  - `/episodes` - Managing learning episodes
  - `/solutions` - Submitting and evaluating code solutions
  - `/healthz` - Health check endpoint

#### Solution Runner API (`solution_runner_api.py`)
- **Purpose**: Isolates Docker operations for running code
- **Technologies**: FastAPI, Docker SDK
- **Endpoints**:
  - `/solutions` - Run code in isolated containers
  - `/health` - Docker connectivity check

### Processing Layer

#### Judge (`simulation/judge.py`)
- **Purpose**: Evaluates solutions against task rubrics
- **Technologies**: Pydantic for task specs, YAML for configuration
- **Functions**:
  - Task loading and parsing
  - Solution evaluation
  - Feedback generation

#### Celery Worker (`workers/celery_app.py`)
- **Purpose**: Handles asynchronous tasks
- **Technologies**: Celery, Redis
- **Tasks**:
  - Embedding generation
  - Background processing

#### Trainer (`workers/trainer_service.py`)
- **Purpose**: Manages model training and updates
- **Technologies**: HuggingFace, PyTorch
- **Functions**:
  - Model fine-tuning
  - Model serving

### Storage Layer

#### PostgreSQL Database
- **Purpose**: Primary data store for episodic memory
- **Schema**:
  - `episodes` - Learning interactions
  - `feedback` - Evaluation results
  - `solutions` - Submitted code/solutions

#### Redis
- **Purpose**: Task queue and caching
- **Usage**:
  - Celery broker
  - Temporary storage
  - Pub/sub messaging

#### Qdrant Vector Store
- **Purpose**: Semantic search via embeddings
- **Collections**:
  - `episodes` - Embedded episode content
  - `concepts` - Semantic concepts

### Execution Layer

#### Docker Runner (Docker-in-Docker)
- **Purpose**: Securely executes untrusted code
- **Technologies**: Docker, Docker-in-Docker (DinD)
- **Features**:
  - Resource limits
  - Network isolation
  - Multiple language support

## Data Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as Main API
    participant Judge
    participant SolutionAPI as Solution Runner API
    participant Docker as Docker Runner
    participant DB as PostgreSQL

    Client->>API: Submit solution
    API->>DB: Store submission
    API->>Judge: Request evaluation
    Judge->>SolutionAPI: Execute solution
    SolutionAPI->>Docker: Run in container
    Docker-->>SolutionAPI: Execution results
    SolutionAPI-->>Judge: Code output
    Judge->>DB: Store evaluation
    Judge-->>API: Evaluation results
    API-->>Client: Feedback
```

## Environment Configuration

### Docker Compose Services Network

```mermaid
graph LR
    subgraph "Public-Facing"
        API[aigym-api:8000]
        SRA[aigym-solution-runner-api:8080]
    end

    subgraph "Storage Services"
        PG[aigym-postgres:5432]
        RD[aigym-redis:6379]
        QD[aigym-qdrant:6333]
    end

    subgraph "Worker Services"
        WK[aigym-worker]
        TR[aigym-trainer]
        JG[aigym-judge]
    end

    subgraph "Execution Service"
        SR[aigym-solution-runner]
    end

    API --> PG & RD & QD
    API --> JG
    API --> SRA

    WK --> PG & RD & QD
    
    JG --> PG & RD
    JG --> SRA
    
    SRA --> SR
    
    TR --> PG & RD
```

## Key Environment Variables

```mermaid
graph TD
    subgraph "Configuration System"
        ENV[".env file"]
        DC["docker-compose.yml"]
        PS["Pydantic Settings"]
    end

    ENV --> DC
    DC --> PS

    subgraph "Key Variables"
        DATABASE_URL
        REDIS_URL
        VECTOR_BACKEND
        VECTOR_HOST
        SOLUTION_RUNNER_API_URL
        OPENAI_API_KEY
        DOCKER_HOST
        PREPULL_IMAGES
    end
```

## Technical Workflow

```mermaid
flowchart TD
    A[User Submits Solution] --> B{API Endpoint}
    B --> C[Create Episode Record]
    C --> D[Judge Evaluates Solution]
    D --> E[Solution Runner API]
    E --> F[Create Docker Container]
    F --> G[Execute Code]
    G --> H[Collect Results]
    H --> I[Apply Rubric]
    I --> J[Store Feedback]
    J --> K[Return Results to User]
    
    L[Embedding Worker] -.-> C
    L -.-> M[Generate Vectors]
    M -.-> N[Store in Qdrant]
```

## Codebase Structure

```mermaid
graph LR
    subgraph "Source Code"
        src["src/"]
        api["api/"]
        db["db/"]
        memory["memory/"]
        models["models/"]
        simulation["simulation/"]
        workers["workers/"]
    end
    
    src --> api & db & memory & models & simulation & workers
    src --> solution_runner_api["solution_runner_api.py"]
    
    api --> main["main.py"] & solutions["solutions.py"]
    simulation --> judge["judge.py"] & judge_client["judge_client.py"]
    workers --> celery_app["celery_app.py"] & embeddings["embeddings.py"]
```
```

When you save this file, you'll be able to view the Mermaid diagrams in any Markdown viewer that supports Mermaid (like GitHub, VS Code with appropriate extensions, or specialized Markdown editors).
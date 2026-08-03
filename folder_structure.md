# Pipeline-2 Folder Structure Reference (Phase 5.8 Frozen Baseline)

```
Pipeline-2/
├── .env.example                       # Environment configuration template
├── pyproject.toml                     # Project dependencies and configuration
├── README.md                          # Repository overview
├── project_context.md                 # Project architecture freeze status
├── architecture.md                    # High-level architecture documentation
├── api_contracts.md                   # REST API contract definitions
├── workflow_contracts.md              # State machine and routing contracts
├── folder_structure.md                # Repository layout guide
├── development_rules.md               # Architectural invariant rules
│
├── agents/                            # Agent domain implementations
│   ├── agent6/                        # Agent 6 (Interview Invitation Agent)
│   │   ├── agent.py                   # Agent facade wrapping LangGraph
│   │   └── graph/                     # Agent 6 LangGraph engine (state, nodes, edges, builder)
│   ├── agent7/                        # Agent 7 (Technical Evaluation Agent)
│   │   ├── agent.py                   # Agent facade wrapping LangGraph
│   │   └── graph/                     # Agent 7 LangGraph engine (state, nodes, edges, builder)
│   ├── agent8/                        # Agent 8 (HR Assessment Agent)
│   │   ├── agent.py                   # Agent facade wrapping LangGraph
│   │   └── graph/                     # Agent 8 LangGraph engine (state, nodes, edges, builder)
│   └── master/                        # Master Agent Orchestrator
│       ├── master_agent.py            # Master facade & event listener
│       ├── dispatcher.py              # HTTP Dispatcher to worker services
│       ├── router.py                  # State machine transition routing engine
│       ├── state_manager.py           # Workflow state DB persistence
│       └── graph/                     # Master LangGraph orchestrator (checkpoints, interrupts)
│
├── services/                          # Process-isolated FastAPI Microservices
│   ├── master_api/                    # Master FastAPI service (:8000)
│   ├── agent6_api/                    # Agent 6 FastAPI service (:8001)
│   ├── agent7_api/                    # Agent 7 FastAPI service (:8002)
│   └── agent8_api/                    # Agent 8 FastAPI service (:8003)
│
├── mcp/                               # Model Context Protocol clients
│   ├── calendar/                      # Calendar MCP client
│   ├── database/                      # Database MCP client
│   ├── document/                      # Document MCP client
│   ├── meet/                          # Meet MCP client
│   ├── notification/                  # Notification MCP client
│   ├── resume/                        # Resume MCP client
│   └── smtp/                          # SMTP MCP client
│
├── schemas/                           # Shared Pydantic data schemas
├── shared/                            # Shared utilities and core configuration
│   ├── clients/                       # HTTP Client adapters (AgentServiceClient)
│   ├── config/                        # Settings (settings.py) & Constants (constants.py)
│   ├── context/                       # WorkflowContext & CandidateContext
│   ├── events/                        # EventBus & BaseEvent definitions
│   ├── interfaces/                    # Base Agent & MCP client interfaces
│   ├── logger/                        # Structured JSON workflow loggers
│   └── registry/                      # Dynamic ToolRegistry & AgentRegistry
│
├── scripts/                           # Operational CLI scripts
│   └── smoke_test_4services.py        # Live 4-process network smoke test script
│
└── tests/                             # Automated Test Suite
    ├── test_architecture_invariants.py # AST checks for Master & sub-agent isolation
    ├── test_distributed_e2e.py         # Full pipeline end-to-end integration test
    ├── test_distributed_failures.py    # Cross-service failure & recovery tests
    ├── test_master_http_dispatch.py    # Master HTTP dispatch test cases
    ├── test_master_graph.py           # Master LangGraph checkpointing tests
    ├── test_master_api.py             # Master FastAPI endpoint tests
    ├── test_agent6_graph.py           # Agent 6 LangGraph tests
    ├── test_agent6_api.py             # Agent 6 FastAPI service tests
    ├── test_agent7_graph.py           # Agent 7 LangGraph tests
    ├── test_agent7_api.py             # Agent 7 FastAPI service tests
    ├── test_agent8_graph.py           # Agent 8 LangGraph tests
    ├── test_agent8_api.py             # Agent 8 FastAPI service tests
    ├── test_agent_client.py           # HTTP client adapter unit tests
    ├── test_contracts.py              # State machine and validator contract tests
    └── test_agent6.py                 # Agent 6 domain unit tests
```

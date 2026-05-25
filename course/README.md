# 🤖 Develop & Deploy AI Agents on Azure with LangChain, Python and Foundry

> A hands-on Udemy course. **15 modules**, end-to-end, from "what is an agent?" to a logged, observable, multi-agent system running on Azure.

---

## 🎯 Who this course is for

* Python developers who want to add **autonomous AI agents** to their apps.
* Architects designing the next generation of **AI-native services** on Azure.
* DevOps / platform engineers who need to **operate** agents in production.

You should be comfortable with Python, Git and the Azure portal. No prior LangChain or AI-agent experience is required.

---

## 🛠️ Tech stack

| Layer            | Tooling                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| Language model   | **Azure AI Foundry** *and* **Gemma 3** self-hosted on **ACA + GPU**     |
| Orchestration    | **LangChain** + **LangGraph** + `azure-ai-agents`                       |
| Tools            | `@tool` functions, **MCP** servers, **Dynamic Sessions** (Python & Bash)|
| Memory           | LangGraph checkpointers + **Azure Cosmos DB**                           |
| Multi-agent      | Sub-agent pattern + **A2A protocol**                                    |
| Observability    | **OpenTelemetry** → **Application Insights** + **LangSmith**            |
| Infrastructure   | **Terraform** (all `.tf` files in `./infra`)                            |

---

## 📚 Course outline

| # | Module                                                 | Notebook                                          |
| -: | ----------------------------------------------------- | ------------------------------------------------- |
|  1 | What is an AI Agent?                                  | [01_what_is_an_ai_agent.ipynb](01_what_is_an_ai_agent.ipynb) |
| 2a | Preparing the LLM — Azure AI Foundry                  | [02a_llm_model_in_foundry.ipynb](02a_llm_model_in_foundry.ipynb) |
| 2b | Preparing the LLM — Container Apps with GPU           | [02b_llm_model_in_aca_gpu.ipynb](02b_llm_model_in_aca_gpu.ipynb) |
|  3 | First simple AI agent with LangChain                  | [03_first_agent_with_langchain.ipynb](03_first_agent_with_langchain.ipynb) |
|  4 | First simple AI agent in Foundry (Persistent Agents)  | [04_first_agent_in_foundry.ipynb](04_first_agent_in_foundry.ipynb) |
|  5 | Adding tools to an AI agent                           | [05_adding_tools_to_an_agent.ipynb](05_adding_tools_to_an_agent.ipynb) |
|  6 | Working with MCP servers                              | [06_working_with_mcp_servers.ipynb](06_working_with_mcp_servers.ipynb) |
|  7 | Deploying an MCP server into Container Apps           | [07_deploying_mcp_server_to_aca.ipynb](07_deploying_mcp_server_to_aca.ipynb) |
|  8 | Adding an MCP server to an AI agent                   | [08_adding_mcp_to_an_agent.ipynb](08_adding_mcp_to_an_agent.ipynb) |
|  9 | Adding a Python dynamic session to an AI agent        | [09_python_dynamic_session.ipynb](09_python_dynamic_session.ipynb) |
| 10 | Adding a Shell dynamic session to an AI agent         | [10_shell_dynamic_session.ipynb](10_shell_dynamic_session.ipynb) |
| 11 | Adding memory to an AI agent                          | [11_adding_memory_to_an_agent.ipynb](11_adding_memory_to_an_agent.ipynb) |
| 12 | The sub-agent pattern                                 | [12_sub_agent_pattern.ipynb](12_sub_agent_pattern.ipynb) |
| 13 | Multi-agents with the A2A protocol                    | [13_multiagents_with_a2a.ipynb](13_multiagents_with_a2a.ipynb) |
| 14 | Logging & observability for AI agents                 | [14_logging_ai_agents.ipynb](14_logging_ai_agents.ipynb) |
| 15 | Closeout & next steps                                 | [15_closeout.ipynb](15_closeout.ipynb) |

### Bonus material

The `extras/` folder contains alternative explorations that did not fit the main path:

| Notebook                                          | What it shows                                                |
| ------------------------------------------------- | ------------------------------------------------------------ |
| `extras/agent_framework.ipynb`                    | Same agent, written with the **Microsoft Agent Framework**.  |
| `extras/langchain_before_after_model.ipynb`       | LangGraph **middleware** (pre/post-model hooks).             |
| `extras/claude.ipynb`                             | Quick test of an Anthropic Claude model.                     |
| `extras/ollama.ipynb`                             | Running Ollama locally as an alternative LLM backend.        |

---

## 🚀 Get started

### 1. Provision the lab

```powershell
cd infra
terraform init
terraform apply -auto-approve
```

This creates: resource group, VNet, ACA environment, log analytics, storage account, Foundry project & model deployment, Cosmos DB, the GPU-backed Gemma container apps, the dynamic-session pools and the MCP server container app.

### 2. Create the Python venv

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
```

The first cell of each notebook installs the libraries it needs — keep things modular and reproducible.

### 3. Authenticate

```powershell
az login
```

The dynamic-session and Foundry modules use `AzureCliCredential` / `DefaultAzureCredential` to pick up your CLI login.

### 4. Open Module 1

Open `01_what_is_an_ai_agent.ipynb` in VS Code, select the `.venv` kernel, and start the journey.

---

## 🧹 Tear down

```powershell
terraform -chdir=./infra destroy -auto-approve
```

GPU containers and Cosmos DB **cost real money** — destroy when not in use.

---

## 📄 License

Course materials © 2026 — for personal learning. Re-distribution, please contact the author.

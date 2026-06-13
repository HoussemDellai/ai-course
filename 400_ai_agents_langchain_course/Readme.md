# Building AI Agents with Langchain and Azure AI Foundry

This repository contains the code and infrastructure for the "Building AI Agents with Langchain and Azure AI Foundry" course. The course covers how to create intelligent agents using the Langchain framework and deploy them on Azure.

## Course Outline

The course is organized as a series of hands-on Jupyter notebooks, each is independant from the previous one.

1. **[Langchain Fundamentals](010_langchain_fundamentals.ipynb)** — Deploy an LLM in Azure AI Foundry with Terraform, retrieve the endpoint and API key, configure the model client, and build your first ReAct agent.
2. **[Tools & Function Calling](020_langchain_tools.ipynb)** — Define custom tools, bind them to the model, control when tool calls are triggered, and run a ReAct agent that decides which tool to use.
3. **[MCP Server — Microsoft Learn Docs](030_langchain_mcp_server_ms_doc.ipynb)** — Connect an agent to the Microsoft Learn MCP server, discover its tools, and query Microsoft documentation through the Model Context Protocol.
4. **[MCP Server — Web Search](040_langchain_mcp_server_web_search.ipynb)** — Use a remote MCP server over Streamable HTTP for web search, invoke tools directly, add interceptors and error handling, and combine it with a custom webpage-fetching tool.
5. **[Dynamic Sessions — Python & Shell](050_langchain_dynamic_session_python_shell.ipynb)** — Give agents a sandboxed code interpreter using Azure Container Apps dynamic sessions, with a Python REPL and Bash/Shell tools, plus file upload and download.
6. **[Memory with Azure Cosmos DB](060_langchain_memory.ipynb)** — Add short-term memory to LangGraph agents using a Cosmos DB checkpointer, manage multi-turn conversations and thread isolation, and summarize long conversations.
7. **[Human-in-the-Loop](070_langchain_human_in_the_loop.ipynb)** — Pause agents for human review with `HumanInTheLoopMiddleware`, then approve, edit, or reject tool calls before they execute.
8. **[Before & After Model Hooks](080_langchain_before_after_model.ipynb)** — Run custom logic before and after each model call to inspect, modify, or guard agent behavior using middleware.
9. **[Sub-Agents & Orchestration](100_langchain_sub_agents.ipynb)** — Compose multi-agent systems where a main agent delegates work to specialized sub-agents equipped with MCP tools.
10. **[Logging & Observability with LangSmith](200_langchain_logging_langsmith.ipynb)** — Enable LangSmith tracing to gain full visibility into agent runs, model calls, tool calls, and sub-agent invocations.
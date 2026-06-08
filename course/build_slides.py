"""
Build the Udemy course PowerPoint deck.

Run from the repo root:
    python course/build_slides.py
"""
from __future__ import annotations

from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

# ---------- design tokens ----------
AZURE_BLUE = RGBColor(0x00, 0x78, 0xD4)
DARK_NAVY  = RGBColor(0x10, 0x2A, 0x43)
LIGHT_GRAY = RGBColor(0xF3, 0xF4, 0xF6)
ACCENT     = RGBColor(0xFF, 0xB9, 0x00)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
TEXT_DARK  = RGBColor(0x1F, 0x2D, 0x3D)
MUTED      = RGBColor(0x55, 0x65, 0x75)

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)  # 16:9


# ---------- helpers ----------
def add_bg(slide, color=WHITE):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H)
    bg.line.fill.background()
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.shadow.inherit = False
    return bg


def add_band(slide, top, height, color):
    band = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, top, SLIDE_W, height)
    band.line.fill.background()
    band.fill.solid()
    band.fill.fore_color.rgb = color
    return band


def add_text(slide, left, top, width, height, text, *,
             size=18, bold=False, color=TEXT_DARK, align=PP_ALIGN.LEFT,
             font="Segoe UI"):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return tb


def add_bullets(slide, left, top, width, height, items, *,
                size=18, color=TEXT_DARK, bullet="•"):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_after = Pt(6)
        run = p.add_run()
        run.text = f"{bullet}  {item}"
        run.font.name = "Segoe UI"
        run.font.size = Pt(size)
        run.font.color.rgb = color
    return tb


def add_footer(slide, module_label):
    add_band(slide, Inches(7.05), Inches(0.45), DARK_NAVY)
    add_text(slide, Inches(0.4), Inches(7.1), Inches(8), Inches(0.35),
             "Develop & Deploy AI Agents on Azure  ·  LangChain · Python · Foundry",
             size=10, color=WHITE)
    add_text(slide, Inches(10.5), Inches(7.1), Inches(2.5), Inches(0.35),
             module_label, size=10, color=ACCENT, align=PP_ALIGN.RIGHT, bold=True)


def add_pill(slide, left, top, label, color=AZURE_BLUE):
    pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                  left, top, Inches(2.6), Inches(0.5))
    pill.line.fill.background()
    pill.fill.solid()
    pill.fill.fore_color.rgb = color
    tf = pill.text_frame
    tf.margin_left = tf.margin_right = Inches(0.1)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name = "Segoe UI"
    r.font.size = Pt(14)
    r.font.bold = True
    r.font.color.rgb = WHITE
    return pill


def add_table(slide, left, top, width, height, headers, rows,
              header_color=AZURE_BLUE, alt=LIGHT_GRAY):
    tbl_shape = slide.shapes.add_table(rows=len(rows) + 1, cols=len(headers),
                                       left=left, top=top,
                                       width=width, height=height)
    tbl = tbl_shape.table

    for i, h in enumerate(headers):
        cell = tbl.cell(0, i)
        cell.fill.solid()
        cell.fill.fore_color.rgb = header_color
        tf = cell.text_frame
        tf.text = ""
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.LEFT
        r = p.add_run()
        r.text = h
        r.font.bold = True
        r.font.color.rgb = WHITE
        r.font.size = Pt(13)
        r.font.name = "Segoe UI"

    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = alt if ri % 2 == 0 else WHITE
            tf = cell.text_frame
            tf.text = ""
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT
            r = p.add_run()
            r.text = str(val)
            r.font.size = Pt(12)
            r.font.name = "Segoe UI"
            r.font.color.rgb = TEXT_DARK
    return tbl


# ---------- slide builders ----------
def new_blank(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    add_bg(slide)
    return slide


def title_slide(prs):
    s = new_blank(prs)
    # left band
    band = slide_left_band = s.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, Inches(4.3), SLIDE_H)
    band.line.fill.background()
    band.fill.solid()
    band.fill.fore_color.rgb = DARK_NAVY

    add_text(s, Inches(0.5), Inches(0.6), Inches(3.5), Inches(0.5),
             "UDEMY COURSE", size=14, bold=True, color=ACCENT)
    add_text(s, Inches(0.5), Inches(1.2), Inches(3.6), Inches(2.5),
             "Develop & Deploy AI Agents on Azure",
             size=30, bold=True, color=WHITE)
    add_text(s, Inches(0.5), Inches(3.6), Inches(3.6), Inches(2),
             "with LangChain, Python\nand Azure AI Foundry",
             size=20, color=LIGHT_GRAY)

    # right pane
    add_text(s, Inches(5), Inches(1.4), Inches(7.8), Inches(0.6),
             "From zero to a production multi-agent system",
             size=22, bold=True, color=DARK_NAVY)
    add_bullets(s, Inches(5), Inches(2.1), Inches(7.8), Inches(4),
                ["15 modules · 16 hands-on notebooks",
                 "Infrastructure as code (Terraform)",
                 "Foundry-hosted AND self-hosted GPU LLMs",
                 "Tools · MCP · Dynamic Sessions · Memory",
                 "Multi-agent with sub-agents and A2A",
                 "Observability with OpenTelemetry"],
                size=18, color=TEXT_DARK)
    add_text(s, Inches(5), Inches(6.2), Inches(7.8), Inches(0.6),
             "© 2026  ·  Hands-on Azure AI Agents course",
             size=12, color=MUTED)
    return s


def divider_slide(prs, num, title, subtitle):
    s = new_blank(prs)
    add_band(s, 0, SLIDE_H, DARK_NAVY)
    add_text(s, Inches(1), Inches(1.5), Inches(11), Inches(1),
             f"MODULE {num}", size=20, bold=True, color=ACCENT)
    add_text(s, Inches(1), Inches(2.3), Inches(11.5), Inches(2),
             title, size=44, bold=True, color=WHITE)
    add_text(s, Inches(1), Inches(4.8), Inches(11.5), Inches(2),
             subtitle, size=20, color=LIGHT_GRAY)
    return s


def content_slide(prs, module_label, header, body_fn):
    s = new_blank(prs)
    # header band
    add_band(s, 0, Inches(0.9), AZURE_BLUE)
    add_text(s, Inches(0.5), Inches(0.18), Inches(11.5), Inches(0.6),
             header, size=24, bold=True, color=WHITE)
    add_text(s, Inches(11.8), Inches(0.25), Inches(1.4), Inches(0.4),
             module_label, size=12, bold=True, color=ACCENT, align=PP_ALIGN.RIGHT)

    body_fn(s)
    add_footer(s, module_label)
    return s


def toc_slide(prs):
    s = new_blank(prs)
    add_band(s, 0, Inches(0.9), AZURE_BLUE)
    add_text(s, Inches(0.5), Inches(0.18), Inches(12), Inches(0.6),
             "Course Outline", size=26, bold=True, color=WHITE)

    rows_left = [
        ("1",  "What is an AI Agent?"),
        ("2a", "LLM model in Azure AI Foundry"),
        ("2b", "LLM model in Container Apps with GPU"),
        ("3",  "First agent with LangChain"),
        ("4",  "First agent in Foundry"),
        ("5",  "Adding tools to an agent"),
        ("6",  "Working with MCP servers"),
        ("7",  "Deploying an MCP server to ACA"),
    ]
    rows_right = [
        ("8",  "Adding MCP to an agent"),
        ("9",  "Python dynamic session"),
        ("10", "Shell dynamic session"),
        ("11", "Adding memory to an agent"),
        ("12", "Sub-agent pattern"),
        ("13", "Multi-agents with A2A"),
        ("14", "Logging AI agents"),
        ("15", "Closeout & next steps"),
    ]

    def render(rows, x):
        tb = s.shapes.add_textbox(x, Inches(1.3), Inches(6.2), Inches(5.5))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, (n, t) in enumerate(rows):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(8)
            r1 = p.add_run(); r1.text = f"{n:>3}   "
            r1.font.name = "Consolas"; r1.font.size = Pt(16)
            r1.font.bold = True; r1.font.color.rgb = AZURE_BLUE
            r2 = p.add_run(); r2.text = t
            r2.font.name = "Segoe UI"; r2.font.size = Pt(16)
            r2.font.color.rgb = TEXT_DARK

    render(rows_left, Inches(0.6))
    render(rows_right, Inches(7.0))
    add_footer(s, "OUTLINE")
    return s


# ---------- module content blocks ----------
def goals_bullets(slide, items):
    add_text(slide, Inches(0.5), Inches(1.15), Inches(8), Inches(0.5),
             "🎯  Learning objectives", size=18, bold=True, color=DARK_NAVY)
    add_bullets(slide, Inches(0.7), Inches(1.7), Inches(12), Inches(5),
                items, size=18, color=TEXT_DARK)


def concepts_table(slide, rows, title="🧠  Key concepts"):
    add_text(slide, Inches(0.5), Inches(1.15), Inches(8), Inches(0.5),
             title, size=18, bold=True, color=DARK_NAVY)
    add_table(slide, Inches(0.5), Inches(1.75), Inches(12.3), Inches(0.4),
              ["Concept", "What it means"], rows)


def two_col(slide, left_title, left_items, right_title, right_items):
    add_text(slide, Inches(0.5), Inches(1.15), Inches(6), Inches(0.4),
             left_title, size=18, bold=True, color=DARK_NAVY)
    add_text(slide, Inches(7), Inches(1.15), Inches(6), Inches(0.4),
             right_title, size=18, bold=True, color=DARK_NAVY)
    add_bullets(slide, Inches(0.7), Inches(1.7), Inches(6),  Inches(5),
                left_items, size=16, color=TEXT_DARK)
    add_bullets(slide, Inches(7.2), Inches(1.7), Inches(5.8), Inches(5),
                right_items, size=16, color=TEXT_DARK)


def code_block(slide, top, code, height=Inches(2.3)):
    box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                 Inches(0.5), top, Inches(12.3), height)
    box.line.fill.background()
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0x1B, 0x1F, 0x27)
    tf = box.text_frame
    tf.margin_left = tf.margin_right = Inches(0.2)
    tf.margin_top = tf.margin_bottom = Inches(0.1)
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = code
    r.font.name = "Consolas"
    r.font.size = Pt(13)
    r.font.color.rgb = RGBColor(0xE6, 0xE6, 0xE6)


# ============================================================
# MODULE DEFINITIONS — each entry adds: divider + content slides
# ============================================================

def m01(prs):
    divider_slide(prs, "1", "What is an AI Agent?",
                  "The mental model behind everything you'll build")
    # slide 1 - definition
    content_slide(prs, "MODULE 1", "Definition", lambda s: (
        add_text(s, Inches(0.5), Inches(1.2), Inches(12.3), Inches(2),
                 "An AI agent is a software system where an LLM autonomously decides — step by step — which tools to call, with which arguments, until a user's goal is reached.",
                 size=22, bold=True, color=DARK_NAVY),
        add_bullets(s, Inches(0.7), Inches(3.5), Inches(12), Inches(3),
                    ["autonomously  →  no hard-coded flow chart",
                     "tools         →  functions, APIs, MCP servers, sub-agents",
                     "step by step  →  the LLM runs in a loop, feeding tool results back",
                     "An LLM can think. An agent can act."],
                    size=18, color=TEXT_DARK),
    ))
    # slide 2 - loop
    content_slide(prs, "MODULE 1", "The agent loop", lambda s: (
        code_block(s, Inches(1.2),
                   "user ─►  System prompt + conversation + tool descriptions\n"
                   "             │\n"
                   "             ▼\n"
                   "          ┌──────────────┐\n"
                   "          │     LLM      │  ◄────── tool result\n"
                   "          └──────┬───────┘             │\n"
                   "                 │ \"call X(args)\"      │\n"
                   "                 ▼                     │\n"
                   "         ┌───────────────┐             │\n"
                   "         │  Tool runtime │ ────────────┘\n"
                   "         └───────────────┘",
                   height=Inches(3.7)),
        add_text(s, Inches(0.5), Inches(5.2), Inches(12.3), Inches(1.5),
                 "The loop stops when the LLM emits a final assistant message — or when a max-step guardrail fires.",
                 size=16, color=MUTED),
    ))
    # slide 3 - building blocks
    content_slide(prs, "MODULE 1", "The 5 building blocks", lambda s: (
        concepts_table(s, [
            ["1. Model",         "Foundry  OR  Gemma on ACA + GPU (modules 2a/2b)"],
            ["2. Orchestration", "LangChain · LangGraph · create_agent (module 3)"],
            ["3. Tools",         "@tool functions · MCP · Dynamic Sessions (5–10)"],
            ["4. Memory",        "Checkpointers + Cosmos DB (module 11)"],
            ["5. Observability", "OpenTelemetry · App Insights · LangSmith (14)"],
        ]),
        add_text(s, Inches(0.5), Inches(5.8), Inches(12), Inches(1),
                 "Add multi-agent on top (modules 12 & 13) and you have a production architecture.",
                 size=16, color=MUTED),
    ))
    # slide 4 - patterns comparison
    content_slide(prs, "MODULE 1", "Agents vs chatbots vs RAG vs workflows", lambda s: (
        concepts_table(s, [
            ["Chatbot",   "Single LLM call · Q&A on training data"],
            ["RAG",       "Hard-coded pipeline · Q&A on YOUR docs · cheap, deterministic"],
            ["Workflow",  "You define the DAG · Repeatable business processes"],
            ["AI Agent",  "The LLM picks the next step · Open-ended tasks · branching"],
        ], title="Pick the simplest pattern that works"),
        add_text(s, Inches(0.5), Inches(5.6), Inches(12.3), Inches(1.5),
                 "Rule of thumb: use an agent only when you really need autonomy.",
                 size=18, bold=True, color=AZURE_BLUE),
    ))


def m02a(prs):
    divider_slide(prs, "2a", "LLM model in Azure AI Foundry",
                  "Managed model deployment, OpenAI-compatible endpoint")
    content_slide(prs, "MODULE 2a", "Learning objectives", lambda s: goals_bullets(s, [
        "Create an Azure AI Foundry project with Terraform",
        "Deploy a chat model (GPT-class)",
        "Retrieve the endpoint and API key",
        "Call the model from Python via the OpenAI-compatible API",
        "Understand the difference between a raw LLM call and an agent call",
    ]))
    content_slide(prs, "MODULE 2a", "Key concepts", lambda s: concepts_table(s, [
        ["Azure AI Foundry",  "Managed Azure service hosting foundation models"],
        ["Project",           "Workspace grouping models · datasets · agents"],
        ["Model deployment",  "A specific model version exposed with a quota"],
        ["OpenAI-compatible", "Foundry exposes /openai/v1/...  → ChatOpenAI just works"],
    ]))
    content_slide(prs, "MODULE 2a", "Call the model in 4 lines", lambda s: code_block(s, Inches(1.5),
        "from langchain_openai import ChatOpenAI\n\n"
        "model = ChatOpenAI(\n"
        "    base_url=f\"{foundry_endpoint}/openai/v1\",\n"
        "    api_key=foundry_api_key,\n"
        "    model=llm_model_deployment_name,\n"
        ")\n"
        "model.invoke(\"Tell me about yourself.\")",
        height=Inches(4)))


def m02b(prs):
    divider_slide(prs, "2b", "LLM in Container Apps with Serverless GPU",
                  "Self-host Gemma 3 on Azure — scale to zero")
    content_slide(prs, "MODULE 2b", "Learning objectives", lambda s: goals_bullets(s, [
        "Deploy Gemma 3 on ACA with a T4 or A100 serverless GPU",
        "Mount Azure Files for persistent model weights",
        "Expose an OpenAI-compatible endpoint via vLLM",
        "Understand cost trade-offs vs Foundry-hosted",
    ]))
    content_slide(prs, "MODULE 2b", "Cost: serverless GPU on Azure", lambda s: (
        add_text(s, Inches(0.5), Inches(1.1), Inches(12), Inches(0.5),
                 "💰  Why self-host? Pay only for the seconds the container actually runs.",
                 size=18, bold=True, color=DARK_NAVY),
        add_table(s, Inches(0.5), Inches(1.9), Inches(12.3), Inches(0.4),
                  ["VM SKU", "VM Regular / mo", "VM Spot / mo", "ACA Serverless / mo"],
                  [["NC8as_T4_v3",      "$610",   "$183",   "$362 – $1,179"],
                   ["NC24ads_A100_v4",  "$3,388", "$610",   "$1,836 – $4,987"],
                   ["NC40ads_H100_v5",  "$6,531", "$4,703", "N.A."]]),
        add_text(s, Inches(0.5), Inches(5.5), Inches(12.3), Inches(1.5),
                 "⚠  Gemma 3 4B (E4B) weights exceed T4 (16 GB) → use A100 for the 4B model.",
                 size=14, color=MUTED),
    ))
    content_slide(prs, "MODULE 2b", "Architecture", lambda s: code_block(s, Inches(1.4),
        "┌────────────────┐    pull weights    ┌──────────────┐\n"
        "│  ACA container │ ─────────────────► │ Azure Files  │\n"
        "│   (vLLM)       │ ◄───────────────── │ (50 GB share)│\n"
        "└────────┬───────┘                    └──────────────┘\n"
        "         │  OpenAI-compatible /v1\n"
        "         ▼\n"
        "    your LangChain agent",
        height=Inches(3.6)))


def m03(prs):
    divider_slide(prs, "3", "First agent with LangChain",
                  "create_agent + ChatOpenAI = your first agent in 10 lines")
    content_slide(prs, "MODULE 3", "Learning objectives", lambda s: goals_bullets(s, [
        "Install langchain · langchain-openai · langgraph",
        "Wrap any OpenAI-compatible endpoint as ChatOpenAI",
        "Build the simplest possible agent with create_agent",
        "Stream responses token by token",
        "Inspect the message list (Human / AI / System)",
    ]))
    content_slide(prs, "MODULE 3", "The simplest agent", lambda s: code_block(s, Inches(1.2),
        "from langchain.agents import create_agent\n"
        "from langchain_openai import ChatOpenAI\n\n"
        "model = ChatOpenAI(base_url=..., api_key=..., model=...)\n"
        "agent = create_agent(model=model, tools=[])\n\n"
        "result = agent.invoke(\n"
        "    {\"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}\n"
        ")\n"
        "print(result[\"messages\"][-1].content)",
        height=Inches(4.5)))


def m04(prs):
    divider_slide(prs, "4", "First agent in Azure AI Foundry",
                  "Persistent Agents — let Azure host the agent for you")
    content_slide(prs, "MODULE 4", "Learning objectives", lambda s: goals_bullets(s, [
        "Understand Persistent Agents in Foundry",
        "Create an agent declaratively with azure-ai-agents",
        "Start a thread, send messages, stream a run",
        "Inspect the server-side trace in the Foundry portal",
        "Decide: Foundry-hosted vs LangChain-hosted",
    ]))
    content_slide(prs, "MODULE 4", "LangChain agent  vs  Foundry agent", lambda s: concepts_table(s, [
        ["Where it runs",     "Your process / container  ·  Managed Azure service"],
        ["State / memory",    "You manage it             ·  Threads stored automatically"],
        ["Built-in tools",    "None — you wire them      ·  Code Interpreter · Bing · Logic Apps"],
        ["Tracing",           "LangSmith / OTel          ·  Built-in in the Foundry portal"],
        ["Portability",       "Run anywhere Python runs  ·  Azure-only"],
    ], title="Two valid choices — often combined"))
    content_slide(prs, "MODULE 4", "Create an agent in 6 lines", lambda s: code_block(s, Inches(1.3),
        "from azure.ai.agents import AgentsClient\n"
        "from azure.identity import DefaultAzureCredential\n\n"
        "client = AgentsClient(endpoint=project_endpoint,\n"
        "                      credential=DefaultAzureCredential())\n\n"
        "agent = client.create_agent(\n"
        "    model=\"gpt-4o-mini\",\n"
        "    name=\"course-agent\",\n"
        "    instructions=\"You are a friendly Azure expert.\",\n"
        ")",
        height=Inches(4.2)))


def m05(prs):
    divider_slide(prs, "5", "Adding tools to an AI agent",
                  "Make the LLM act, not just talk")
    content_slide(prs, "MODULE 5", "Learning objectives", lambda s: goals_bullets(s, [
        "Define a tool from a Python function with @tool",
        "Bind multiple tools and let the LLM choose",
        "Read the tool-call trace (debugging)",
        "Handle errors inside tools without crashing the agent",
    ]))
    content_slide(prs, "MODULE 5", "The expanded agent loop", lambda s: code_block(s, Inches(0.7),
        "User: \"Weather in Paris in Fahrenheit?\"\n"
        "       │\n"
        "       ▼\n"
        "   LLM ─► call get_weather(\"Paris\")\n"
        "             │\n"
        "             ▼   ToolMessage(\"12°C\")\n"
        "   LLM ─► call celsius_to_fahrenheit(12)\n"
        "             │\n"
        "             ▼   ToolMessage(\"53.6°F\")\n"
        "   LLM ─► \"It's 53.6°F in Paris.\"",
        height=Inches(4.8)))
    content_slide(prs, "MODULE 5", "Best practices for writing tools", lambda s: add_bullets(s,
        Inches(0.7), Inches(1.4), Inches(12), Inches(5.5), [
        "One clear purpose per tool — the LLM must choose between them",
        "Type hints + docstring → become the JSON schema the LLM sees",
        "Return plain text or simple JSON, not giant nested objects",
        "Catch your own errors and return a string the LLM can understand",
        "Keep tool count manageable (≤ ~15 in one agent — beyond that, use sub-agents)",
    ], size=18))


def m06(prs):
    divider_slide(prs, "6", "Working with MCP servers",
                  "Model Context Protocol — USB for AI tools")
    content_slide(prs, "MODULE 6", "What is MCP?", lambda s: (
        add_text(s, Inches(0.5), Inches(1.3), Inches(12.3), Inches(2),
                 "MCP is a JSON-RPC protocol that lets an LLM application discover and call tools, read resources and use prompts from a separate process.",
                 size=20, bold=True, color=DARK_NAVY),
        add_text(s, Inches(0.5), Inches(3.5), Inches(12.3), Inches(1),
                 "MCP is to AI agents what USB is to peripherals.",
                 size=18, color=AZURE_BLUE, bold=True),
        code_block(s, Inches(4.5),
                   "┌──────────────┐  list_tools  ┌──────────────┐\n"
                   "│  LLM client  │ ───────────► │  MCP server  │\n"
                   "│   (agent)    │ ◄─────────── │              │\n"
                   "└──────────────┘  call_tool   └──────────────┘",
                   height=Inches(2.4)),
    ))
    content_slide(prs, "MODULE 6", "Primitives and transports", lambda s: (
        concepts_table(s, [
            ["Tool",      "A function the LLM can call"],
            ["Resource",  "A blob of context the LLM reads"],
            ["Prompt",    "A reusable prompt template"],
        ], title="🧩  Three primitives"),
        add_text(s, Inches(0.5), Inches(4.5), Inches(12), Inches(0.4),
                 "🚚  Transports", size=18, bold=True, color=DARK_NAVY),
        add_bullets(s, Inches(0.7), Inches(5.0), Inches(12), Inches(2),
                    ["stdio          → same machine; great for demos",
                     "HTTP+SSE       → legacy remote transport",
                     "Streamable HTTP → recommended (one /mcp endpoint)"],
                    size=16),
    ))
    content_slide(prs, "MODULE 6", "A 10-line MCP server with FastMCP", lambda s: code_block(s, Inches(1.3),
        "from fastmcp import FastMCP\n\n"
        "mcp = FastMCP(\"mini-demo\")\n\n"
        "@mcp.tool\n"
        "def add(a: int, b: int) -> int:\n"
        "    \"\"\"Return the sum of a and b.\"\"\"\n"
        "    return a + b\n\n"
        "if __name__ == \"__main__\":\n"
        "    mcp.run()  # stdio by default",
        height=Inches(4.4)))


def m07(prs):
    divider_slide(prs, "7", "Deploying an MCP server to Container Apps",
                  "Production-ready remote tools, with serverless ingress")
    content_slide(prs, "MODULE 7", "Learning objectives", lambda s: goals_bullets(s, [
        "Anatomy of an MCP server (transport, tools, resources)",
        "Read the Terraform module aca_mcp_server_web_search.tf",
        "Build & push the container image",
        "Verify the /mcp endpoint with curl",
        "Wire identity, ingress and secrets in ACA",
    ]))
    content_slide(prs, "MODULE 7", "Architecture", lambda s: code_block(s, Inches(0.7),
        "┌──────────────────────┐    HTTPS /mcp     ┌──────────────────────┐\n"
        "│  LangChain Agent     │ ────────────────► │  ACA MCP Server      │\n"
        "│  (your laptop / app) │ ◄──────────────── │  (Streamable HTTP)   │\n"
        "└──────────────────────┘   SSE stream      └──────────┬───────────┘\n"
        "                                                      │\n"
        "                                                      ▼\n"
        "                                            External APIs (Bing, …)",
        height=Inches(3.8)))


def m08(prs):
    divider_slide(prs, "8", "Adding an MCP server to an agent",
                  "One agent · many MCP servers · zero glue code")
    content_slide(prs, "MODULE 8", "Learning objectives", lambda s: goals_bullets(s, [
        "Connect to the public Microsoft Docs MCP server",
        "Connect to the MCP server you deployed in module 7",
        "Use langchain-mcp-adapters to convert MCP tools to LangChain tools",
        "Pass them to create_agent like any other tool",
        "Streamable HTTP vs stdio — when to use which",
    ]))
    content_slide(prs, "MODULE 8", "Mental model", lambda s: code_block(s, Inches(0.7),
        "                  ┌──────────────────────────┐\n"
        "                  │  Microsoft Learn MCP     │\n"
        "       ┌── tools─►│  (public)                │\n"
        "       │          └──────────────────────────┘\n"
        " ┌─────┴───┐\n"
        " │  Agent  │\n"
        " └─────┬───┘      ┌──────────────────────────┐\n"
        "       │          │  YOUR MCP Server         │\n"
        "       └── tools─►│  (Container Apps)        │\n"
        "                  └──────────────────────────┘",
        height=Inches(4.4)))


def m09(prs):
    divider_slide(prs, "9", "Python dynamic session",
                  "A sandboxed code interpreter for your agent")
    content_slide(prs, "MODULE 9", "Learning objectives", lambda s: goals_bullets(s, [
        "Why agents need sandboxed code execution",
        "Provision an ACA Dynamic Sessions pool (PythonLTS)",
        "Use SessionsPythonREPLTool as an agent tool",
        "Upload files · run code · download results",
        "Reason about session lifetime, isolation and cost",
    ]))
    content_slide(prs, "MODULE 9", "Why NOT just exec() locally?", lambda s: concepts_table(s, [
        ["Risk",                 "Local exec  vs  Dynamic Session"],
        ["Malicious code",       "Runs on YOUR machine  ❌    →   Sandboxed Hyper-V VM  ✅"],
        ["Package pollution",    "Pollutes your env             →   Fresh container per session"],
        ["Resource hogging",     "Crashes your laptop           →   Sandbox killed at idle TTL"],
        ["Multi-tenant",         "Impossible                    →   One session per user / chat"],
    ], title="🔐  Dynamic Sessions = Hyper-V isolation on demand"))
    content_slide(prs, "MODULE 9", "Using it in code", lambda s: code_block(s, Inches(1.3),
        "from langchain_azure_dynamic_sessions.tools import SessionsPythonREPLTool\n"
        "from azure.identity import AzureCliCredential\n\n"
        "tool = SessionsPythonREPLTool(\n"
        "    pool_management_endpoint=sessionpool_endpoint,\n"
        "    access_token_provider=lambda: cred.get_token(\n"
        "        \"https://dynamicsessions.io/.default\").token,\n"
        ")\n"
        "agent = create_agent(model=model, tools=[tool])",
        height=Inches(4)))


def m10(prs):
    divider_slide(prs, "10", "Shell dynamic session",
                  "The agent gets a full Linux box — and you stay safe")
    content_slide(prs, "MODULE 10", "Learning objectives", lambda s: goals_bullets(s, [
        "Provision a Custom-image Dynamic Sessions pool (Bash)",
        "Use SessionsBashTool as an agent tool",
        "Let the agent install packages, run Flask, fetch URLs",
        "Download generated files back to your laptop",
        "Differences vs the Python session — more freedom, more risk",
    ]))
    content_slide(prs, "MODULE 10", "Power vs Safety — production checklist", lambda s: add_bullets(s,
        Inches(0.7), Inches(1.4), Inches(12), Inches(5.5), [
        "Scope the Managed Identity tightly",
        "Place the pool in a private subnet with NSG egress controls",
        "Short idle TTL on the pool — cheaper AND safer",
        "Prompt-level guardrails (system message: \"do not …\")",
        "Audit the bash transcripts (App Insights — see module 14)",
    ], size=18))


def m11(prs):
    divider_slide(prs, "11", "Adding memory to an agent",
                  "Short-term threads, long-term user memory, durable in Cosmos DB")
    content_slide(prs, "MODULE 11", "Learning objectives", lambda s: goals_bullets(s, [
        "Difference between short-term (thread) and long-term memory",
        "Add an in-memory MemorySaver checkpointer",
        "Persist conversation state to Azure Cosmos DB",
        "Use thread_id to switch between concurrent conversations",
        "Summarize old messages to control prompt size & cost",
    ]))
    content_slide(prs, "MODULE 11", "Two flavors of memory", lambda s: concepts_table(s, [
        ["Short-term (thread)",      "Lives inside one conversation, keyed by thread_id, stored by the Checkpointer"],
        ["Long-term (user memory)",  "\"User likes responses in French\", company = Contoso, … stored by the Store (vector DB / KV)"],
    ]))
    content_slide(prs, "MODULE 11", "Plug a checkpointer into the agent", lambda s: code_block(s, Inches(1.3),
        "from langgraph.checkpoint.memory import MemorySaver\n\n"
        "agent = create_agent(model=model, tools=[...],\n"
        "                     checkpointer=MemorySaver())\n\n"
        "config = {\"configurable\": {\"thread_id\": \"alice-1\"}}\n"
        "agent.invoke({\"messages\": [...]}, config=config)\n\n"
        "# Same thread_id → remembers. New thread_id → fresh chat.",
        height=Inches(4)))


def m12(prs):
    divider_slide(prs, "12", "The sub-agent pattern",
                  "Decompose one big agent into a supervisor + specialists")
    content_slide(prs, "MODULE 12", "Learning objectives", lambda s: goals_bullets(s, [
        "Recognize when one agent is too big (too many tools)",
        "Refactor into a supervisor + specialist sub-agents",
        "Expose each sub-agent as a @tool of the supervisor",
        "Pass state between supervisor and sub-agents",
        "Reason about tokens, latency and cost",
    ]))
    content_slide(prs, "MODULE 12", "Mental model", lambda s: code_block(s, Inches(0.7),
        "                       ┌─────────────────────┐\n"
        "                       │  Supervisor agent   │\n"
        "                       │  (router LLM)       │\n"
        "                       └──┬───────────┬──────┘\n"
        "                          │           │\n"
        "             call_research│           │call_coder\n"
        "                          ▼           ▼\n"
        "                ┌────────────┐  ┌────────────┐\n"
        "                │ Researcher │  │ Coder      │\n"
        "                │ sub-agent  │  │ sub-agent  │\n"
        "                │ + web tool │  │ + Python   │\n"
        "                │            │  │   session  │\n"
        "                └────────────┘  └────────────┘",
        height=Inches(4.8)))


def m13(prs):
    divider_slide(prs, "13", "Multi-agents with A2A",
                  "Cross-process · cross-language · cross-team agent ecosystems")
    content_slide(prs, "MODULE 13", "Learning objectives", lambda s: goals_bullets(s, [
        "What A2A is and how it complements MCP",
        "Read an agent card at /.well-known/agent.json",
        "Expose a LangChain agent as an A2A server",
        "Call a remote agent using the a2a Python SDK",
        "Pick A2A vs MCP vs sub-agent for your topology",
    ]))
    content_slide(prs, "MODULE 13", "MCP  vs  A2A — they are not competitors", lambda s: concepts_table(s, [
        ["Who's on the other side?", "Tool server (no autonomy)   ·   Another AGENT (own loop)"],
        ["Protocol shape",           "JSON-RPC                    ·   HTTP tasks/send · tasks/get"],
        ["Discovery",                "Configured client-side      ·   /.well-known/agent.json"],
        ["Stateful?",                "No                          ·   Yes (tasks have status)"],
    ]))
    content_slide(prs, "MODULE 13", "An agent card", lambda s: code_block(s, Inches(1.3),
        "{\n"
        "  \"name\": \"web-research-agent\",\n"
        "  \"description\": \"Researches a topic and returns a summary.\",\n"
        "  \"url\": \"https://research.contoso.com\",\n"
        "  \"capabilities\": { \"streaming\": true },\n"
        "  \"skills\": [\n"
        "    { \"id\": \"research\", \"name\": \"Web research\" }\n"
        "  ]\n"
        "}",
        height=Inches(4.2)))


def m14(prs):
    divider_slide(prs, "14", "Logging & observability",
                  "See what your agents do — in real time and in production")
    content_slide(prs, "MODULE 14", "The three observability layers", lambda s: concepts_table(s, [
        ["Logs",     "Free-form text events   →   print · logging · ACA log stream"],
        ["Metrics",  "Numeric counters        →   Azure Monitor · Prometheus"],
        ["Traces",   "Spans linked into a tree →  OpenTelemetry → App Insights / LangSmith"],
    ], title="🪜  For agents, traces are king"))
    content_slide(prs, "MODULE 14", "App Insights setup in two lines", lambda s: code_block(s, Inches(1.3),
        "from azure.monitor.opentelemetry import configure_azure_monitor\n"
        "from opentelemetry.instrumentation.langchain import LangchainInstrumentor\n\n"
        "configure_azure_monitor(enable_live_metrics=True)\n"
        "LangchainInstrumentor().instrument()\n\n"
        "# Every LangChain run now appears in App Insights\n"
        "# → Transaction Search · End-to-end transaction view",
        height=Inches(4)))
    content_slide(prs, "MODULE 14", "Agent KPIs to track in production", lambda s: add_bullets(s,
        Inches(0.7), Inches(1.4), Inches(12), Inches(5.5), [
        "Task success rate — did the user actually get what they asked for?",
        "Steps per task — outliers reveal the LLM looping",
        "Tool error rate — alert if > 5 % for 10 minutes",
        "Tokens per task — direct $ cost (cost guardrails)",
        "p95 latency — user experience",
        "Refusal rate — safety filter too aggressive?",
    ], size=18))


def m15(prs):
    divider_slide(prs, "15", "Closeout & next steps",
                  "What you built, what to build next, how to tear down")
    content_slide(prs, "MODULE 15", "What you can now build", lambda s: add_bullets(s,
        Inches(0.7), Inches(1.4), Inches(12), Inches(5.5), [
        "A LangChain agent calling Foundry or your self-hosted Gemma",
        "Foundry Persistent Agents with managed threads & tools",
        "Local @tool functions AND remote MCP servers",
        "An agent that writes and runs code in a sandboxed Linux box",
        "Conversation memory in Cosmos DB",
        "A supervisor agent orchestrating sub-agents (local) and A2A peers (remote)",
        "All of it logged in App Insights & LangSmith",
    ], size=18))
    content_slide(prs, "MODULE 15", "Suggested next projects", lambda s: add_bullets(s,
        Inches(0.7), Inches(1.4), Inches(12), Inches(5.5), [
        "Knowledge-base agent  →  MCP + Azure AI Search + memory",
        "Junior-dev agent      →  Shell session + GitHub MCP",
        "Customer-support orchestrator  →  3 A2A peers + a router",
        "DevOps agent          →  ARM/Bicep tools + Azure Monitor metrics",
    ], size=18))
    content_slide(prs, "MODULE 15", "Tear down the lab", lambda s: (
        code_block(s, Inches(2.0),
                   "terraform -chdir=./infra destroy -auto-approve",
                   height=Inches(1.2)),
        add_text(s, Inches(0.5), Inches(4.0), Inches(12.3), Inches(2),
                 "GPU containers and Cosmos DB cost real money.\nDestroy when not in use — rebuild later with terraform apply.",
                 size=20, color=DARK_NAVY, align=PP_ALIGN.CENTER),
        add_text(s, Inches(0.5), Inches(6.2), Inches(12.3), Inches(0.6),
                 "🙏  Thank you — please rate the course on Udemy!",
                 size=22, bold=True, color=ACCENT, align=PP_ALIGN.CENTER),
    ))


# ============================================================
# MAIN
# ============================================================
def main():
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    title_slide(prs)
    toc_slide(prs)

    for builder in [m01, m02a, m02b, m03, m04, m05, m06, m07,
                    m08, m09, m10, m11, m12, m13, m14, m15]:
        builder(prs)

    out = Path(__file__).parent / "AI_Agents_on_Azure_Course.pptx"
    prs.save(out)
    print(f"✅  Wrote {out}  ({out.stat().st_size // 1024} KB, "
          f"{len(prs.slides)} slides)")


if __name__ == "__main__":
    main()

educational_runtime    = true
education_drawio_image = "jgraph/drawio-mcp:1.0.6@sha256:4ad6be7215bec6d266337fe7037cfdaa250a01db11c9783708b885b395350828"

education_environment = {
  EDUCATION_TEXT_MODELS  = "gpt-6-astra"
  EDUCATION_SEARCH_MODEL = "gpt-6-astra"
  DRAWIO_MCP_URL         = "http://localhost:3001/mcp"
  DRAWIO_EXPORT_COMMAND  = "[\"python\",\"/app/drawio_runtime/export_native.py\"]"
  COMFY_IMAGE_WORKFLOW   = "/app/video_platform/comfy_workflows/qwen_image_t2i.json"
  EDUCATION_FONT         = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
}

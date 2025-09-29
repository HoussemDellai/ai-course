# The following example shows how to issue an HTTP GET request supplying
# an optional request header.
data "http" "http-request-apim-openai" {
  url    = "${azurerm_api_management.apim.gateway_url}/openai/deployments/gpt-4o/chat/completions?api-version=2024-10-21"
  method = "POST"
  # Optional request headers
  request_headers = {
    Accept  = "application/json"
    api-key = "133c3dbbe1224537a28366d079b0fd65" # "${azurerm_api_management_subscription.apim-api-subscription-openai.primary_key}"
  }

  request_body = <<EOF
  {
    "messages":[
      {"role": "system", "content": "You are a sarcastic unhelpful assistant."},
      {"role": "user", "content": "Can you tell me the time, please?"}
  ]}
EOF

#   lifecycle {
#     postcondition {
#       condition     = contains([201, 204], self.status_code)
#       error_message = "Status code invalid"
#     }
#   }
}

output "http-apim-request-response" {
  value = data.http.http-request-apim-openai.response_body
}
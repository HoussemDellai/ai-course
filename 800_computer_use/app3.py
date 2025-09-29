import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

#from openai import OpenAI
token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

client = OpenAI(  
  base_url = "https://ai-services-09302-400007.openai.azure.com/openai/v1/",  
  api_key="85zmoNWFsDies9jIjC3LOoAy4xcmubFNA9Om1Bg3XDDHcTFI14IGJQQJ99BIACfhMk5XJ3w3AAAAACOG0Nyi" # token_provider,
)

response = client.responses.create(
    model="computer-use-preview-swc", # set this to your model deployment name
    tools=[{
        "type": "computer_use_preview",
        "display_width": 1024,
        "display_height": 768,
        "environment": "browser" # other possible values: "mac", "windows", "ubuntu"
    }],
    input=[
        {
            "role": "user",
            "content": "Check the latest AI news on bing.com."
        }
    ],
    truncation="auto"
)

print(response.output)

## response.output is the previous response from the model
computer_calls = [item for item in response.output if item.type == "computer_call"]
if not computer_calls:
    print("No computer call found. Output from model:")
    for item in response.output:
        print(item)

computer_call = computer_calls[0]
last_call_id = computer_call.call_id
action = computer_call.action

# Your application would now perform the action suggested by the model
# And create a screenshot of the updated state of the environment before sending another response

# response_2 = client.responses.create(
#     model="computer-use-preview",
#     previous_response_id=response.id,
#     tools=[{
#         "type": "computer_use_preview",
#         "display_width": 1024,
#         "display_height": 768,
#         "environment": "browser" # other possible values: "mac", "windows", "ubuntu"
#     }],
#     input=[
#         {
#             "call_id": last_call_id,
#             "type": "computer_call_output",
#             "output": {
#                 "type": "input_image",
#                 # Image should be in base64
#                 "image_url": f"data:image/png;base64,{<base64_string>}"
#             }
#         }
#     ],
#     truncation="auto"
# )
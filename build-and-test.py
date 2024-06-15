from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:5272/v1/",
    api_key="x" # required by API but not used
)

chat_completion = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": "what is the golden ratio?",
        }
    ],
    model="Phi-3-mini-4k-cpu-int4-rtn-block-32-acc-level-4-onnx" # "Phi-3-mini-4k-directml-int4-awq-block-128-onnx",
)

print(chat_completion.choices[0].message.content)
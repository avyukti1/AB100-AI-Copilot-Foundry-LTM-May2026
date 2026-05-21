from openai import OpenAI

endpoint = "https://ltmaifoundry111.openai.azure.com/openai/v1"
deployment_name = "abhishek-gpt-4o"
api_key = "C3vkiWsNPcQc1iohPaQPpsiAdnoyxJcYen89LHzt1hcw9j18ba7gJQQJ99CEACYeBjFXJ3w3AAAAACOGyxk1"

client = OpenAI(
    base_url=endpoint,
    api_key=api_key
)

completion = client.chat.completions.create(
    model=deployment_name,
    messages=[
        {
            "role": "user",
            "content": "What is the capital of France?",
        }
    ],
)

print(completion.choices[0].message)
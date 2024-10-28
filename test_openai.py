import requests

# Replace with your Hugging Face API key
API_URL = "https://api-inference.huggingface.co/models/gpt2"
headers = {"Authorization": f"Bearer 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"}

def query(payload):
    response = requests.post(API_URL, headers=headers, json=payload)
    return response.json()

def gpt_generate_response(user_input):
    try:
        data = query({"inputs": user_input})
        return data[0]['generated_text']  # Hugging Face response format
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    user_input = input("Enter your prompt: ")
    print(gpt_generate_response(user_input))

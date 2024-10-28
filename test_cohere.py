import cohere

# Replace with your Cohere API key
co = cohere.Client("9K4WKP7kbXPQGvLclv3BZrtAbgzl7M3hR9zwfv5X")

def gpt_generate_response(user_input):
    try:
        response = co.generate(
            model='command-xlarge-nightly',  # or use 'xlarge' for a more general model
            prompt=user_input,
            max_tokens=150,
            temperature=0.7
        )
        return response.generations[0].text.strip()
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    user_input = input("Enter your prompt: ")
    print(gpt_generate_response(user_input))

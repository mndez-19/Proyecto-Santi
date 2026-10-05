<<<<<<< HEAD
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

for model in client.models.list():
=======
import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

for model in client.models.list():
>>>>>>> 16dc2c55da859f5eeb7c3e1686c13c82337e82a6
    print(model.name) 
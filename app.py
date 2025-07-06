from flask import Flask, request, jsonify
import openai
import base64
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS so your frontend can call this backend

# Use your real OpenAI API key in a secure environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route("/analyze", methods=["POST"])
def analyze():
    if 'image' not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image = request.files['image']
    base64_image = base64.b64encode(image.read()).decode('utf-8')

    # 🔍 STEP 1: Vision API analyzes curl traits
    vision_response = openai.ChatCompletion.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Please analyze this photo of curly hair. Identify:\n"
                            "- Curl type (1A to 4C)\n"
                            "- Porosity (low, med, high)\n"
                            "- Frizz level\n"
                            "- Volume/density\n"
                            "- Overall hair health"
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        max_tokens=500
    )

    analysis = vision_response['choices'][0]['message']['content']

    # 🧴 STEP 2: GPT-4 creates care routine + DIY recipes
    prompt = f"""
    Based on this hair analysis: {analysis}, generate a personalized curly hair care routine for a 15-year-old girl. Include:

    1. A care routine:
       - Wash frequency
       - Product types (moisturizers, leave-ins, stylers)
       - Styling methods
       - Sleep protection

    2. A list of 2–3 DIY hair product recipes made with common home ingredients.
       For each DIY product, include:
       - Name
       - Purpose (e.g. deep conditioning, curl definition)
       - Ingredients
       - Instructions
       - How often to use it
       - One-sentence scientific justification (e.g. “Aloe vera contains mucilage, which enhances moisture retention.”)
    """

    routine_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            { "role": "user", "content": prompt }
        ],
        max_tokens=1000
    )

    routine = routine_response['choices'][0]['message']['content']

    return jsonify({
        "curl_analysis": analysis,
        "result": routine
    })

# Optional: health check
@app.route("/")
def home():
    return "Curlwise backend is live!"

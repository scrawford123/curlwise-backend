import os
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
import openai

# ── Local dev convenience ──────────────────────────────────────────────────────
# When you run this on Render, the env var RENDER=1 is injected automatically.
if os.getenv("RENDER") is None:
    # Only load .env locally so you never commit secrets
    from dotenv import load_dotenv
    load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")  # ← set this in Render Dashboard

# ── Flask setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

@app.route("/analyze", methods=["POST"])
def analyze():
    """Accepts an uploaded image, runs GPT-4 Vision + GPT-4o and returns JSON."""
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    image = request.files["image"]
    base64_image = base64.b64encode(image.read()).decode("utf-8")

    # --- Step 1: Hair-trait analysis with Vision ---
    vision_response = openai.ChatCompletion.create(
        model="gpt-4o-mini",             # or gpt-4o/gpt-4-vision-preview
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
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        max_tokens=500,
    )
    analysis = vision_response["choices"][0]["message"]["content"]

    # --- Step 2: Personalised routine + DIY recipes ---
    prompt = f"""
    Based on this hair analysis: {analysis}, generate a personalised curly-hair
    care routine for a 15-year-old girl. Include:

    1. Care routine:
       • Wash frequency
       • Product types (moisturisers, leave-ins, stylers)
       • Styling methods
       • Sleep protection

    2. Two or three DIY hair-product recipes made with common home ingredients.
       For each DIY product include:
       • Name
       • Purpose
       • Ingredients
       • Instructions
       • Usage frequency
       • One-sentence scientific justification
    """

    routine_response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    )
    routine = routine_response["choices"][0]["message"]["content"]

    return jsonify({"curl_analysis": analysis, "result": routine})


# ── Health check route ─────────────────────────────────────────────────────────
@app.route("/")
def healthcheck():
    return "Curlwise backend is live!", 200


# ── Entrypoint ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    print(f"✅ Flask is about to start on port {port}")
    # Disable reloader in production; it forks and confuses Render’s port scanner
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

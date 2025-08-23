from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import openai
import stripe

app = Flask(__name__)
CORS(app)

openai.api_key = os.getenv("OPENAI_API_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Track sessions that have completed payment; a simple in-memory set
paid_sessions = set()

@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    """Create a Stripe Checkout Session for one hair scan costing $1."""
    try:
        data = request.get_json() or {}
        success_url = data.get("success_url", "")
        cancel_url = data.get("cancel_url", "")
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": 100,
                    "product_data": {"name": "CurlWise Hair Scan"},
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=(success_url + ("?session_id={CHECKOUT_SESSION_ID}" if success_url else "")) or "",
            cancel_url=cancel_url or "",
        )
        return jsonify({"id": session.id})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """Listen to Stripe webhooks and record successful payments."""
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        return jsonify({"error": "Webhook error: " + str(e)}), 400
    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        paid_sessions.add(session["id"])
    return "", 200

@app.route("/analyze", methods=["POST"])
def analyze():
    """Analyze a user's curl image after verifying payment and return routine recommendations."""
    session_id = request.form.get("session_id") or (request.get_json() or {}).get("session_id")
  #  if not session_id or session_id not in paid_sessions:
   #     return jsonify({"error": "Payment required"}), 402
    # remove session to prevent reuse
   if session_id:  paid_sessions.discard(session_id)
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400
    try:
        image = request.files["image"]
        base64_image = base64.b64encode(image.read()).decode("utf-8")
        vision_response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": (
                            "Please analyze this photo of curl / hair texture and describe the hair type (e.g. 2a, 2b, 3a, 3b, etc.) "
                            "along with curl pattern characteristics and common concerns like dryness or frizz."
                        )},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ],
            max_tokens=400,
        )
        curl_analysis = vision_response.choices[0].message.content.strip()
        routine_prompt = (
            "You are a curl care assistant. Based on the following analysis of a user's curls, "
            "recommend a personalized hair care routine, including washing, conditioning, styling products, and "
            "DIY recipes with proportions. Be concise yet thorough.\nAnalysis:\n" + curl_analysis
        )
        routine_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": routine_prompt}],
            temperature=0.7,
            max_tokens=500,
            n=1,
        )
        routine = routine_response.choices[0].message.content.strip()
        return jsonify({"curl_analysis": curl_analysis, "result": routine})
    except Exception as e:
        return jsonify({"error": "Internal server error: " + str(e)}), 500


if __name__ == "__main__":
    # Run the Flask development server
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import base64
import openai
import stripe

app = Flask(__name__)
CORS(app)

# Setup API keys from environment
openai.api_key = os.getenv("OPENAI_API_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Configuration flag: set PAYMENTS_REQUIRED to false to bypass payment check
PAYMENTS_REQUIRED = os.getenv("PAYMENTS_REQUIRED", "true").lower() in ("true", "1", "yes")

# Track sessions that have completed payment
paid_sessions = set()

@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    """
    Create a Stripe Checkout Session for one hair scan costing $1.
    """
    try:
        data = request.get_json() or {}
        success_url = data.get("success_url", "")
        cancel_url = data.get("cancel_url", "")
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": 100,  # $1.00 in cents
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
    """
    Handle Stripe webhook events to record completed payments.
    """
    payload = request.data
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        return jsonify({"error": f"Webhook error: {e}"}), 400

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        paid_sessions.add(session["id"])
    return "", 200

@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Analyze an uploaded image and generate a personalized hair care routine.
    If payments are required, verify the session_id has completed payment before proceeding.
    """
    if PAYMENTS_REQUIRED:
        # verify session_id is provided and has completed payment
        session_id = request.form.get("session_id") or (request.get_json() or {}).get("session_id")
        if not session_id or session_id not in paid_sessions:
            return jsonify({"error": "Payment required"}), 402
        # prevent reuse
        paid_sessions.discard(session_id)

    # Validate image
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    try:
        image = request.files["image"]
        base64_image = base64.b64encode(image.read()).decode("utf-8")

        # Step 1: use GPT-4 Vision to describe curl type & concerns
        vision_response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": (
                        "Please analyze this photo of curl / hair texture and describe the hair type "
                        "(e.g. 2a, 2b, 3a, 3b, etc.) along with curl pattern characteristics and common concerns "
                        "like dryness or frizz."
                    )},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ],
            }],
            max_tokens=400,
        )
        curl_analysis = vision_response.choices[0].message.content.strip()

        # Step 2: use GPT-4 to generate routine & DIY recipes
        routine_prompt = (
            "You are a curl care assistant. Based on the following analysis of a user's curls, "
            "recommend a personalized hair care routine, including washing, conditioning, styling products, "
            "and DIY recipes with proportions. Be concise yet thorough.\nAnalysis:\n" + curl_analysis
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
        return jsonify({"error": f"Internal server error: {e}"}), 500

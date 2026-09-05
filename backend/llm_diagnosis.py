import os
import json

from anthropic import Anthropic


MODEL = os.getenv(
    "RECOVERYOS_LLM_MODEL",
    "claude-sonnet-5"
)


def deterministic_fallback(payment):
    """
    Safe fallback when no Claude API key is configured.

    This keeps the application functional during development.
    """

    mapping = {
        "BANK_TIMEOUT":
            "Temporary bank timeout; delayed retry may be effective.",

        "NETWORK_ERROR":
            "Transient network failure; retrying later may be effective.",

        "GATEWAY_TIMEOUT":
            "Gateway timeout; verify status before retrying.",

        "INSUFFICIENT_FUNDS":
            "Insufficient funds; an alternate payment path is preferable.",

        "CARD_EXPIRED":
            "Expired card; use an alternate payment method.",

        "EXPIRED_CARD":
            "Expired card; use an alternate payment method.",

        "AUTH_FAILED":
            "Authentication failure; customer authentication may be required.",

        "BANK_DECLINED":
            "Bank declined the transaction; an alternate payment method may help.",

        "LIMIT_EXCEEDED":
            "Payment limit exceeded; an alternate payment method may be required.",
    }

    return {
        "source": "deterministic_fallback",
        "diagnosis": mapping.get(
            payment["failure_code"],
            "Unknown payment failure; human review recommended.",
        ),
        "severity": "medium",
        "customer_context": (
            "Customer context unavailable from deterministic rules."
        ),
        "reasoning_summary": (
            "Fallback diagnosis used because the LLM service "
            "was unavailable."
        ),
    }


def diagnose_with_claude(payment):

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        return deterministic_fallback(payment)

    client = Anthropic(
        api_key=api_key
    )

    payment_context = {
        "amount": payment["amount"],
        "payment_method": payment["payment_method"],
        "failure_code": payment["failure_code"],
        "successful_payments": payment["successful_payments"],
        "previous_retries": payment["previous_retries"],
        "customer_tenure_days": payment["customer_tenure_days"],
        "transaction_hour": payment["transaction_hour"],
        "merchant_category": payment["merchant_category"],
        "days_since_last_success": payment["days_since_last_success"],
        "customer_avg_amount": payment["customer_avg_amount"],
    }

    system_prompt = """
You are the diagnosis component of a fintech revenue-recovery system.

Your job is to analyze a failed payment and explain the likely
failure context.

You DO NOT authorize payments.
You DO NOT execute financial actions.
You DO NOT decide whether money should be moved.

Return ONLY valid JSON with these fields:

{
  "diagnosis": "...",
  "severity": "low|medium|high",
  "customer_context": "...",
  "reasoning_summary": "..."
}

Be concise, factual, and avoid inventing information.
Base the analysis only on the supplied payment context.
"""

    user_prompt = f"""
Analyze this failed payment:

{json.dumps(payment_context, indent=2)}
"""

    try:

        response = client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )

        text = next(
            block.text
            for block in response.content
            if block.type == "text"
        )

        result = json.loads(text)

        return {
            "source": "claude",
            "diagnosis": result.get(
                "diagnosis",
                "Unable to determine diagnosis.",
            ),
            "severity": result.get(
                "severity",
                "medium",
            ),
            "customer_context": result.get(
                "customer_context",
                "",
            ),
            "reasoning_summary": result.get(
                "reasoning_summary",
                "",
            ),
        }

    except Exception as error:

        fallback = deterministic_fallback(payment)

        fallback["llm_error"] = str(error)

        return fallback
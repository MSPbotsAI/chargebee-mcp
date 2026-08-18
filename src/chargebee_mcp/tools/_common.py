from .._json import error_envelope

NO_CREDS = error_envelope(
    "not_configured",
    "No Chargebee credentials configured. Send the X-Chargebee-Site and "
    "X-Chargebee-Api-Key headers.",
    False,
)
